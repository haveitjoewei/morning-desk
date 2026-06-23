import json
import tempfile
import unittest
from pathlib import Path

from content.schema import BriefingContent, PriorityItem
from connectors.weather import build_open_meteo_url, parse_open_meteo
from ai.generate_outfit import generate_outfit
from orchestrator.run_morning_job import build_content, write_content
from scripts.morning import run_morning
from renderer.render import load_layout, render, slot_text
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

    def test_layout_has_living_room_design_anchors(self):
        root = Path(__file__).resolve().parents[1]
        layout = load_layout(root / "renderer" / "layout.yaml")
        slots = {slot["id"]: slot for slot in layout["slots"]}

        self.assertEqual(slots["attention"]["type"], "attention")
        self.assertEqual(slots["attention"]["style"]["chrome"], "solid")
        self.assertEqual(slots["wear"]["label"], "WEAR")
        self.assertGreaterEqual(slots["hero"]["style"]["font_size"], 30)

    def test_structured_outfit_renders_as_title_items_and_reason(self):
        text = slot_text(
            {
                "headline": "Rain-ready casual",
                "items": ["navy rain shell", "grey tee", "black jeans"],
                "reason": "Rain later, casual calendar.",
            }
        )

        self.assertIn("Rain-ready casual", text)
        self.assertIn("navy rain shell", text)
        self.assertIn("grey tee", text)
        self.assertIn("Rain later, casual calendar.", text)

    def test_wardrobe_photo_import_creates_editable_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            self.assertTrue((images / "navy-rain-shell.jpg").exists())
            self.assertEqual(json.loads(drafts.read_text()), records)

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


if __name__ == "__main__":
    unittest.main()
