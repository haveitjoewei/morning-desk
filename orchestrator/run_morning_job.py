import json
from pathlib import Path

from ai.classify_urgency import classify_urgency
from ai.generate_briefing import generate_briefing
from ai.generate_journal import generate_journal_prompt
from ai.generate_outfit import generate_outfit
from connectors.airbnb_gmail import fetch_airbnb_messages
from connectors.calendar_google import fetch_calendar
from connectors.va_inbox import fetch_va_messages
from connectors.weather import fetch_weather
from content.schema import BriefingContent, PriorityItem
from wardrobe.catalog import load_wardrobe


def build_content():
    weather = fetch_weather()
    calendar = fetch_calendar()
    wardrobe_items = load_wardrobe()
    raw_priority_events = fetch_airbnb_messages() + fetch_va_messages()

    priority_items = [
        PriorityItem(
            event.title,
            event.source,
            classify_urgency(event),
            event.body,
            event.metadata["suggested_action"],
        )
        for event in raw_priority_events
    ]
    briefing = generate_briefing(calendar, weather, priority_items)

    return BriefingContent.from_parts(
        weather=weather,
        outfit=generate_outfit(weather, wardrobe_items, calendar),
        briefing=briefing,
        calendar=calendar,
        priority_items=priority_items,
        journal_prompt=generate_journal_prompt(briefing, calendar),
    ).to_dict()


def write_content(content, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(content, indent=2) + "\n")
    return content


def main():
    root = Path(__file__).resolve().parents[1]
    write_content(build_content(), root / "content" / "latest.json")


if __name__ == "__main__":
    main()
