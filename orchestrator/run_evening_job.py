"""Evening job — tomorrow's prep plus an end-of-day reflection.

Built so the display can be time-aware: the morning job writes today's briefing,
the evening job writes this. Same content store + server; whichever ran last is
what the display shows.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ai.generate_outfit import generate_outfit
from ai.generate_reflection import generate_reflection
from connectors.calendar_google import fetch_calendar, tzinfo
from connectors.weather import fetch_weather
from orchestrator.run_morning_job import daily_context
from wardrobe.catalog import load_wardrobe
from wardrobe.outfit_plan import planned_outfit


def build_evening_content(today=None):
    tz = tzinfo()
    today = today or datetime.now(tz).date()
    tomorrow = today + timedelta(days=1)

    weather = fetch_weather(day=1)
    calendar_tomorrow = fetch_calendar(today=tomorrow)
    calendar_today = fetch_calendar(today=today)
    wardrobe_items = load_wardrobe()
    context = daily_context(tomorrow)

    outfit = planned_outfit(
        tomorrow.isoformat(),
        lambda: generate_outfit(weather, wardrobe_items, calendar_tomorrow, context),
        keep_from=today.isoformat(),
    )
    reflection = generate_reflection(calendar_today)

    return {
        "mode": "evening",
        "generated_at": datetime.now(tz).isoformat(timespec="seconds"),
        "date_label": "Tomorrow — " + tomorrow.strftime("%A, %-d %B"),
        "weather": weather,
        "outfit": outfit,
        "calendar": calendar_tomorrow,
        "recap": reflection["recap"],
        "reflection_prompt": reflection["reflection"],
    }
