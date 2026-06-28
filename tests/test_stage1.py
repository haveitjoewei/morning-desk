import json
import os
import struct
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from content.schema import BriefingContent, PriorityItem
from config.runtime_env import load_environment
from connectors.calendar_google import (
    fetch_calendar,
    parse_calendar_events,
    parse_google_events,
)
from connectors.airbnb_gmail import fetch_airbnb_messages
from connectors.va_inbox import fetch_va_messages
from connectors import _gmail
from connectors.weather import (
    FALLBACK_WEATHER,
    build_open_meteo_url,
    fetch_weather,
    parse_open_meteo,
)
from ai.generate_briefing import generate_briefing
from ai.generate_outfit import generate_outfit
from orchestrator.run_morning_job import build_content, write_content
from scripts.morning import run_morning
from scripts.install_launchd import build_plists
from scripts.status import collect_status
from renderer.render import attention_text, load_layout, render, slot_text
from server.app import create_handler
from wardrobe.analyze_photos import image_content_block, merge_analysis
from wardrobe.catalog import load_wardrobe
from wardrobe.import_photos import import_photos


class StageOneTest(unittest.TestCase):
    def test_content_keeps_only_today_and_urgent_priority_items(self):
        content = BriefingContent.from_parts(
            priority_items=[
                PriorityItem("Visible today", "airbnb", "today", "Needs reply", "Reply"),
                PriorityItem("Visible urgent", "va", "urgent", "Blocking", "Approve"),
                PriorityItem("Hidden low", "email", "low", "FYI", "Read later"),
                PriorityItem("Hidden ignore", "email", "ignore", "Noise", "Ignore"),
            ]
        )

        self.assertEqual(
            [item["title"] for item in content.to_dict()["priority_items"]],
            ["Visible today", "Visible urgent"],
        )

    def test_morning_job_writes_the_content_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "latest.json"

            content = write_content(build_content(), output)

            saved = json.loads(output.read_text())
            self.assertEqual(saved["date_label"], content["date_label"])
            self.assertIn("weather", saved)
            self.assertIn("priority_items", saved)
            self.assertEqual(set(saved["outfit"]), {"headline", "items", "reason"})
            self.assertGreaterEqual(len(saved["outfit"]["items"]), 3)
            self.assertTrue(
                all(item["urgency"] in {"today", "urgent"} for item in saved["priority_items"])
            )

    def test_layout_yaml_renders_a_png(self):
        root = Path(__file__).resolve().parents[1]
        layout = load_layout(root / "renderer" / "layout.yaml")

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "latest.png"

            render(build_content(), layout, output)

            self.assertEqual(output.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(output.stat().st_size, 1000)
            width, height = struct.unpack(">II", output.read_bytes()[16:24])
            self.assertEqual(
                (width, height),
                (
                    layout["canvas"]["width"],
                    layout["canvas"]["height"],
                ),
            )

    def test_layout_has_living_room_design_anchors(self):
        root = Path(__file__).resolve().parents[1]
        layout = load_layout(root / "renderer" / "layout.yaml")
        slots = {slot["id"]: slot for slot in layout["slots"]}

        self.assertEqual(slots["attention"]["type"], "attention")
        self.assertEqual(slots["attention"]["style"]["chrome"], "solid")
        self.assertEqual(slots["wear"]["label"], "WEAR")
        self.assertEqual(
            slots["wear"]["fields"],
            ["headline", "items", "reason"],
        )
        self.assertGreaterEqual(slots["hero"]["style"]["font_size"], 30)

    def test_structured_outfit_renders_as_title_items_and_reason(self):
        text = slot_text(
            {
                "headline": "Rain-ready casual",
                "items": ["navy rain shell", "grey tee", "black jeans"],
                "reason": "Rain later, casual calendar.",
            },
            ["headline", "items", "reason"],
        )

        self.assertIn("Rain-ready casual", text)
        self.assertIn("navy rain shell", text)
        self.assertIn("grey tee", text)
        self.assertIn("Rain later, casual calendar.", text)

    def test_empty_attention_uses_calm_clear_state(self):
        text = attention_text([])
        self.assertIn("ALL CLEAR", text)
        self.assertNotIn("0 THINGS NEED ATTENTION", text)

    def test_wardrobe_photo_import_creates_editable_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            inbox = root / "wardrobe" / "inbox"
            images = root / "wardrobe" / "images"
            drafts = root / "wardrobe" / "drafts.json"
            inbox.mkdir(parents=True)
            (inbox / "Navy Rain Shell.JPG").write_bytes(b"fake image")
            (inbox / "receipt.txt").write_text("not clothing")

            records = import_photos(inbox, images, drafts)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["id"], "navy-rain-shell")
            self.assertEqual(records[0]["category"], "outerwear")
            self.assertEqual(records[0]["colors"], ["navy"])
            self.assertTrue(records[0]["rain_ok"])
            self.assertEqual(records[0]["image"], "wardrobe/images/navy-rain-shell.jpg")
            self.assertEqual(records[0]["material_guess"], "unknown")
            self.assertEqual(records[0]["texture"], "unknown")
            self.assertEqual(records[0]["thickness"], "unknown")
            self.assertEqual(records[0]["fit"], "unknown")
            self.assertEqual(records[0]["best_for"], [])
            self.assertEqual(records[0]["avoid_for"], [])
            self.assertEqual(records[0]["review_status"], "needs_review")
            self.assertEqual(records[0]["confidence"], "low")
            self.assertEqual(records[0]["correction_history"], [])
            self.assertTrue((images / "navy-rain-shell.jpg").exists())
            self.assertEqual(json.loads(drafts.read_text()), records)

    def test_wardrobe_catalog_applies_local_corrections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            items = root / "items.json"
            corrections = root / "corrections.json"
            items.write_text(
                json.dumps(
                    [
                        {
                            "name": "navy chore coat",
                            "category": "outerwear",
                            "style_tags": ["casual"],
                            "best_for": ["office"],
                            "warmth": "medium",
                        }
                    ]
                )
            )
            corrections.write_text(
                json.dumps(
                    [
                        {
                            "name": "navy chore coat",
                            "set": {
                                "fit": "boxy but cropped",
                                "warmth": "light",
                            },
                            "add": {
                                "style_tags": ["dress_to_impress"],
                                "best_for": ["nice dinner"],
                            },
                            "note": "Looks longer in one photo than it fits.",
                        }
                    ]
                )
            )

            wardrobe = load_wardrobe(items, corrections)

            self.assertEqual(wardrobe[0]["fit"], "boxy but cropped")
            self.assertEqual(wardrobe[0]["warmth"], "light")
            self.assertEqual(
                wardrobe[0]["style_tags"],
                ["casual", "dress_to_impress"],
            )
            self.assertEqual(wardrobe[0]["best_for"], ["office", "nice dinner"])
            self.assertEqual(
                wardrobe[0]["correction_history"],
                ["Looks longer in one photo than it fits."],
            )

    def test_wardrobe_analyzer_builds_base64_image_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "shirt.jpg"
            image.write_bytes(b"fake image bytes")

            block = image_content_block(image)

            self.assertEqual(block["type"], "image")
            self.assertEqual(block["source"]["type"], "base64")
            self.assertEqual(block["source"]["media_type"], "image/jpeg")
            self.assertEqual(block["source"]["data"], "ZmFrZSBpbWFnZSBieXRlcw==")

    def test_wardrobe_analyzer_merges_only_allowed_fields(self):
        record = {
            "name": "img 6443",
            "category": "unknown",
            "style_tags": ["needs_review"],
            "best_for": [],
        }

        merged = merge_analysis(
            record,
            {
                "name": "blue linen shirt",
                "category": "top",
                "colors": ["blue"],
                "material_guess": "linen",
                "texture": "slubby",
                "thickness": "light",
                "fit": "relaxed",
                "best_for": ["office"],
                "avoid_for": ["heavy rain"],
                "style_tags": ["dress_to_impress"],
                "confidence": "medium",
                "made_up_field": "ignored",
            },
        )

        self.assertEqual(merged["name"], "blue linen shirt")
        self.assertEqual(merged["category"], "top")
        self.assertEqual(merged["material_guess"], "linen")
        self.assertEqual(merged["style_tags"], ["dress_to_impress"])
        self.assertEqual(merged["best_for"], ["office"])
        self.assertNotIn("made_up_field", merged)

    def test_open_meteo_response_maps_to_weather_contract(self):
        weather = parse_open_meteo(
            {
                "current": {
                    "temperature_2m": 17.6,
                    "weather_code": 61,
                    "precipitation": 0.2,
                },
                "daily": {
                    "temperature_2m_max": [20.2],
                    "temperature_2m_min": [11.4],
                    "precipitation_probability_max": [80],
                    "precipitation_sum": [5.1],
                    "weather_code": [61],
                },
            }
        )

        self.assertEqual(weather["summary"], "18C, rain likely")
        self.assertEqual(weather["high"], 20)
        self.assertEqual(weather["low"], 11)
        self.assertEqual(weather["condition"], "rain_likely")
        self.assertEqual(weather["precipitation_probability"], 80)

    def test_open_meteo_url_uses_location_config(self):
        url = build_open_meteo_url(
            {
                "latitude": -33.8688,
                "longitude": 151.2093,
                "timezone": "Australia/Sydney",
            }
        )

        self.assertIn("latitude=-33.8688", url)
        self.assertIn("longitude=151.2093", url)
        self.assertIn("timezone=Australia%2FSydney", url)
        self.assertIn("current=temperature_2m%2Cweather_code%2Cprecipitation", url)
        self.assertIn("daily=temperature_2m_max%2Ctemperature_2m_min", url)

    def test_offline_mode_never_calls_weather_network(self):
        with (
            patch.dict("os.environ", {"MD_OFFLINE": "1"}),
            patch(
                "connectors.weather.fetch_open_meteo",
                side_effect=AssertionError("network should not be called"),
            ),
        ):
            self.assertEqual(fetch_weather(), FALLBACK_WEATHER)

    def test_outfit_reason_matches_non_rain_weather(self):
        outfit = generate_outfit(
            {"condition": "cloudy", "high": 16, "low": 8},
            [
                {"name": "olive overshirt", "category": "midlayer", "rain_ok": False},
                {"name": "grey tee", "category": "top", "rain_ok": False},
                {"name": "black jeans", "category": "bottom", "rain_ok": False},
                {"name": "black sneakers", "category": "shoes", "rain_ok": False},
            ],
        )

        self.assertEqual(outfit["headline"], "Easy casual layers")
        self.assertIn("cloudy", outfit["reason"].lower())
        self.assertNotIn("Rain later", outfit["reason"])

    def test_outfit_respects_smart_casual_calendar(self):
        outfit = generate_outfit(
            {"condition": "cloudy", "high": 18, "low": 10},
            [
                {"name": "grey tee", "category": "top", "formality": "casual", "rain_ok": False},
                {"name": "oxford shirt", "category": "top", "formality": "smart casual", "rain_ok": False},
                {"name": "black jeans", "category": "bottom", "formality": "casual", "rain_ok": False},
                {"name": "wool trousers", "category": "bottom", "formality": "smart casual", "rain_ok": False},
                {"name": "black sneakers", "category": "shoes", "formality": "casual", "rain_ok": False},
                {"name": "leather loafers", "category": "shoes", "formality": "smart casual", "rain_ok": False},
            ],
            [{"title": "Lunch", "dress_code": "smart casual"}],
        )

        self.assertEqual(outfit["headline"], "Smart casual layers")
        self.assertIn("oxford shirt", outfit["items"])
        self.assertIn("wool trousers", outfit["items"])
        self.assertIn("smart casual", outfit["reason"].lower())

    def test_outfit_uses_dress_to_impress_items_for_office_days(self):
        outfit = generate_outfit(
            {"condition": "cloudy", "high": 20, "low": 13},
            [
                {
                    "name": "soft grey tee",
                    "category": "top",
                    "formality": "casual",
                    "style_tags": ["basic"],
                    "rain_ok": False,
                },
                {
                    "name": "white textured shirt",
                    "category": "top",
                    "formality": "smart casual",
                    "style_tags": ["dress_to_impress"],
                    "rain_ok": False,
                },
                {
                    "name": "black jeans",
                    "category": "bottom",
                    "formality": "casual",
                    "style_tags": ["basic"],
                    "rain_ok": False,
                },
                {
                    "name": "charcoal trousers",
                    "category": "bottom",
                    "formality": "smart casual",
                    "style_tags": ["dress_to_impress"],
                    "rain_ok": False,
                },
                {
                    "name": "black sneakers",
                    "category": "shoes",
                    "formality": "casual",
                    "rain_ok": False,
                },
                {
                    "name": "black loafers",
                    "category": "shoes",
                    "formality": "smart casual",
                    "style_tags": ["dress_to_impress"],
                    "rain_ok": False,
                },
            ],
            context={"work_mode": "office", "intent": "dress_to_impress"},
        )

        self.assertEqual(outfit["headline"], "Office polish")
        self.assertIn("white textured shirt", outfit["items"])
        self.assertIn("charcoal trousers", outfit["items"])
        self.assertIn("dress to impress", outfit["reason"].lower())

    def test_outfit_uses_rain_layer_when_rain_is_likely(self):
        outfit = generate_outfit(
            {"condition": "rain_likely", "high": 16, "low": 8},
            [
                {"name": "rain shell", "category": "outerwear", "formality": "casual", "rain_ok": True},
                {"name": "grey tee", "category": "top", "formality": "casual", "rain_ok": False},
                {"name": "black jeans", "category": "bottom", "formality": "casual", "rain_ok": False},
                {"name": "waterproof sneakers", "category": "shoes", "formality": "casual", "rain_ok": True},
            ],
        )

        self.assertIn("rain shell", outfit["items"])
        self.assertIn("waterproof sneakers", outfit["items"])

    def test_outfit_avoids_athletic_shorts_for_rainy_casual_day(self):
        outfit = generate_outfit(
            {"condition": "rain_later", "high": 18, "low": 12},
            [
                {
                    "name": "hooded softshell jacket",
                    "category": "outerwear",
                    "formality": ["casual"],
                    "rain_ok": True,
                    "warmth": 3,
                },
                {
                    "name": "white waffle henley",
                    "category": "top",
                    "formality": ["casual", "smart casual"],
                    "rain_ok": False,
                    "warmth": 2,
                },
                {
                    "name": "grey mesh athletic shorts",
                    "category": "bottom",
                    "formality": ["athletic"],
                    "rain_ok": False,
                    "warmth": 1,
                    "subtype": "athletic shorts",
                },
                {
                    "name": "black slim jeans",
                    "category": "bottom",
                    "formality": ["casual", "smart casual"],
                    "rain_ok": False,
                    "warmth": 3,
                    "subtype": "jeans",
                },
                {
                    "name": "white leather sneakers",
                    "category": "shoes",
                    "formality": ["casual", "smart casual"],
                    "rain_ok": True,
                    "warmth": 2,
                },
            ],
        )

        self.assertIn("black slim jeans", outfit["items"])
        self.assertNotIn("grey mesh athletic shorts", outfit["items"])

    def test_outfit_calls_out_athletic_event_separately(self):
        outfit = generate_outfit(
            {"condition": "clear", "high": 22, "low": 14},
            [
                {"name": "grey tee", "category": "top", "formality": "casual", "rain_ok": False},
                {"name": "black jeans", "category": "bottom", "formality": "casual", "rain_ok": False},
                {"name": "black sneakers", "category": "shoes", "formality": "casual", "rain_ok": False},
            ],
            [{"title": "Badminton", "dress_code": "athletic"}],
        )

        self.assertIn("Bring athletic kit for Badminton.", outfit["reason"])

    def test_briefing_uses_weather_calendar_and_priorities(self):
        briefing = generate_briefing(
            {"condition": "rain_likely", "summary": "18C, rain likely"},
            [
                {"time": "09:30", "title": "Standup"},
                {"time": "12:00", "title": "Lunch"},
            ],
            [
                {"title": "Approve pest quote", "urgency": "urgent"},
                {"title": "Reply to guest", "urgency": "today"},
            ],
        )

        self.assertIn("2 things need attention", briefing)
        self.assertIn("Standup at 09:30", briefing)
        self.assertIn("Rain is likely", briefing)

    def test_briefing_handles_clear_empty_day(self):
        briefing = generate_briefing(
            {"condition": "clear", "summary": "22C, clear"},
            [],
            [],
        )

        self.assertIn("No scheduled events", briefing)
        self.assertIn("nothing urgent", briefing)

    def test_briefing_uses_claude_when_configured(self):
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="A focused morning with rain after lunch.")]
        )
        fake_client = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **kwargs: response)
        )

        with (
            patch("ai.generate_briefing.available", return_value=True),
            patch("ai.generate_briefing.client", return_value=fake_client),
        ):
            briefing = generate_briefing(
                {"condition": "rain_likely"},
                [{"time": "09:30", "title": "Standup"}],
                [],
            )

        self.assertEqual(briefing, "A focused morning with rain after lunch.")

    def test_outfit_rejects_hallucinated_claude_items(self):
        response = SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="text",
                    text=json.dumps(
                        {
                            "headline": "Invented look",
                            "items": ["imaginary cashmere coat"],
                            "reason": "Looks good.",
                        }
                    ),
                )
            ]
        )
        fake_client = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **kwargs: response)
        )
        wardrobe = [
            {
                "name": "grey tee",
                "category": "top",
                "formality": "casual",
                "rain_ok": False,
            },
            {
                "name": "black jeans",
                "category": "bottom",
                "formality": "casual",
                "rain_ok": False,
            },
            {
                "name": "black sneakers",
                "category": "shoes",
                "formality": "casual",
                "rain_ok": False,
            },
        ]

        with (
            patch("ai.generate_outfit.available", return_value=True),
            patch("ai.generate_outfit.client", return_value=fake_client),
        ):
            outfit = generate_outfit(
                {"condition": "clear", "high": 22, "low": 14},
                wardrobe,
                [],
            )

        self.assertNotIn("imaginary cashmere coat", outfit["items"])
        self.assertEqual(outfit["headline"], "Easy casual layers")

    def test_morning_command_builds_content_and_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def build():
                return {
                    "weather": {"summary": "18C, clear"},
                    "outfit": {"headline": "Easy layers", "items": [], "reason": ""},
                }

            def render_content(content, output):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"\x89PNG\r\n\x1a\nfake")

            result = run_morning(root, build_content_fn=build, render_fn=render_content)

            self.assertEqual(result["weather"], "18C, clear")
            self.assertTrue((root / "content" / "latest.json").exists())
            self.assertEqual((root / "renderer" / "latest.png").read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_failed_render_keeps_previous_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "renderer" / "latest.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"previous image")

            def build():
                return {
                    "weather": {"summary": "18C, clear"},
                    "outfit": {"headline": "Easy layers", "items": [], "reason": ""},
                }

            def fail_render(content, output):
                output.write_bytes(b"partial image")
                raise RuntimeError("render failed")

            with self.assertRaises(RuntimeError):
                run_morning(root, build_content_fn=build, render_fn=fail_render)

            self.assertEqual(image.read_bytes(), b"previous image")
            self.assertFalse((root / "renderer" / "latest.tmp.png").exists())

    def test_runtime_environment_file_does_not_override_process_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "environment"
            path.write_text(
                "ANTHROPIC_API_KEY=file-key\n"
                "MD_SERVER_PORT=9090\n"
                "# comment\n"
            )

            with patch.dict(
                "os.environ",
                {"ANTHROPIC_API_KEY": "process-key"},
                clear=True,
            ):
                loaded = load_environment(path)
                self.assertEqual(loaded["MD_SERVER_PORT"], "9090")
                self.assertEqual(
                    os.environ["ANTHROPIC_API_KEY"],
                    "process-key",
                )
                self.assertEqual(os.environ["MD_SERVER_PORT"], "9090")

    def test_local_calendar_filters_today_and_preserves_context(self):
        events = parse_calendar_events(
            [
                {
                    "start": "2026-06-23T12:00:00+10:00",
                    "end": "2026-06-23T13:00:00+10:00",
                    "title": "Lunch",
                    "location": "Surry Hills",
                    "dress_code": "smart casual",
                },
                {
                    "start": "2026-06-24T09:30:00+10:00",
                    "end": "2026-06-24T10:00:00+10:00",
                    "title": "Tomorrow",
                    "location": "",
                    "dress_code": "casual",
                },
                {
                    "start": "2026-06-23T09:30:00+10:00",
                    "end": "2026-06-23T10:00:00+10:00",
                    "title": "Standup",
                    "location": "",
                    "dress_code": "casual",
                },
            ],
            today=date(2026, 6, 23),
        )

        self.assertEqual([event["title"] for event in events], ["Standup", "Lunch"])
        self.assertEqual(events[0]["time"], "09:30")
        self.assertEqual(events[1]["location"], "Surry Hills")
        self.assertEqual(events[1]["dress_code"], "smart casual")

    def test_fetch_calendar_reads_local_events_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "start": "2026-06-23T17:30:00+10:00",
                            "end": "2026-06-23T18:30:00+10:00",
                            "title": "Badminton",
                            "location": "Court",
                            "dress_code": "athletic",
                        }
                    ]
                )
            )

            events = fetch_calendar(path, today=date(2026, 6, 23))

            self.assertEqual(events[0]["title"], "Badminton")
            self.assertEqual(events[0]["time"], "17:30")
            self.assertEqual(events[0]["dress_code"], "athletic")

    def test_calendar_supports_relative_demo_events(self):
        events = parse_calendar_events(
            [
                {
                    "day_offset": 0,
                    "time": "09:30",
                    "duration_minutes": 30,
                    "title": "Standup",
                    "dress_code": "casual",
                }
            ],
            today=date(2026, 6, 24),
        )

        self.assertEqual(events[0]["time"], "09:30")
        self.assertTrue(events[0]["start"].startswith("2026-06-24T09:30"))

    def test_google_calendar_events_preserve_context(self):
        events = parse_google_events(
            [
                {
                    "summary": "Client lunch",
                    "description": "Dress code: smart casual",
                    "location": "CBD",
                    "start": {"dateTime": "2026-06-24T12:00:00+10:00"},
                    "end": {"dateTime": "2026-06-24T13:00:00+10:00"},
                }
            ],
            timezone_name="Australia/Sydney",
        )

        self.assertEqual(events[0]["time"], "12:00")
        self.assertEqual(events[0]["location"], "CBD")
        self.assertEqual(events[0]["dress_code"], "smart casual")

    def test_authenticated_empty_google_calendar_does_not_use_demo_events(self):
        with (
            patch.dict("os.environ", {"MD_OFFLINE": "0"}),
            patch(
                "connectors.calendar_google.fetch_google_calendar",
                return_value=[],
            ),
        ):
            self.assertEqual(fetch_calendar(), [])

    def test_server_serves_image_health_and_etag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "renderer" / "latest.png"
            content = root / "content" / "latest.json"
            image.parent.mkdir(parents=True)
            content.parent.mkdir(parents=True)
            image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
            content.write_text(
                json.dumps({"generated_at": "2026-06-24T06:00:00+10:00"})
            )

            try:
                server = ThreadingHTTPServer(
                    ("127.0.0.1", 0),
                    create_handler(root),
                )
            except PermissionError:
                self.skipTest("localhost sockets are unavailable in this sandbox")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"

            try:
                with urlopen(f"{base}/latest.png") as response:
                    etag = response.headers["ETag"]
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers["Content-Type"], "image/png")
                    self.assertEqual(response.read()[:8], b"\x89PNG\r\n\x1a\n")

                request = Request(
                    f"{base}/latest.png",
                    headers={"If-None-Match": etag},
                )
                with self.assertRaises(HTTPError) as error:
                    urlopen(request)
                self.assertEqual(error.exception.code, 304)

                with urlopen(f"{base}/health.json") as response:
                    health = json.loads(response.read())
                self.assertEqual(health["status"], "ok")
                self.assertEqual(
                    health["generated_at"],
                    "2026-06-24T06:00:00+10:00",
                )
            finally:
                server.shutdown()
                server.server_close()

    def test_launchd_plists_schedule_generation_and_keep_server_alive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "venv" / "bin").mkdir(parents=True)
            plists = build_plists(root, hour=5, minute=45)

            generator = plists["com.morningdesk.generate"]
            server = plists["com.morningdesk.serve"]

            self.assertEqual(
                generator["StartCalendarInterval"],
                {"Hour": 5, "Minute": 45},
            )
            self.assertIn(
                str(root / "scripts" / "morning.py"),
                generator["ProgramArguments"],
            )
            self.assertTrue(server["KeepAlive"])
            self.assertIn(
                str(root / "server" / "app.py"),
                server["ProgramArguments"],
            )

    def test_status_reports_configured_integrations_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            config = home / ".config" / "morning-desk"
            config.mkdir(parents=True)
            (config / "gcal_token.json").write_text("{}")
            image = root / "renderer" / "latest.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + b"\x00\x00\x00\rIHDR"
                + struct.pack(">II", 1200, 825)
            )

            with patch.dict(
                "os.environ",
                {"ANTHROPIC_API_KEY": "configured"},
                clear=True,
            ):
                status = collect_status(root, home=home)

            self.assertTrue(status["claude"]["configured"])
            self.assertTrue(status["google_calendar"]["token"])
            self.assertFalse(status["gmail"]["token"])
            self.assertEqual(status["image"]["size"], [1200, 825])

    def test_empty_authenticated_gmail_results_do_not_create_fake_alerts(self):
        with patch.object(_gmail, "search", return_value=[]):
            self.assertEqual(fetch_airbnb_messages(), [])
            self.assertEqual(fetch_va_messages(), [])

    def test_unconfigured_gmail_is_empty_unless_demo_mode_is_enabled(self):
        with (
            patch.object(_gmail, "search", return_value=None),
            patch.dict("os.environ", {"MD_DEMO": "0"}),
        ):
            self.assertEqual(fetch_airbnb_messages(), [])
            self.assertEqual(fetch_va_messages(), [])

        with (
            patch.object(_gmail, "search", return_value=None),
            patch.dict("os.environ", {"MD_DEMO": "1"}),
        ):
            self.assertEqual(len(fetch_airbnb_messages()), 1)
            self.assertEqual(len(fetch_va_messages()), 1)


if __name__ == "__main__":
    unittest.main()
