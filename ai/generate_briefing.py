"""Generate a concise narrative briefing, with a deterministic local fallback."""
import json

from ai._llm import MODEL, available, client, text_of


SYSTEM = (
    "Write a calm morning briefing for a living-room e-ink display. "
    "Use 2-3 short plain sentences. Mention the first scheduled event, actionable "
    "priority count, and useful weather implications. No greeting, markdown, or filler."
)


def fallback_briefing(weather, calendar, priority_items):
    parts = []

    if calendar:
        first = calendar[0]
        parts.append(
            f"{len(calendar)} scheduled event{'s' if len(calendar) != 1 else ''}; "
            f"first is {first['title']} at {first['time']}."
        )
    else:
        parts.append("No scheduled events today.")

    if priority_items:
        parts.append(
            f"{len(priority_items)} thing{'s' if len(priority_items) != 1 else ''} "
            "need attention before the day gets away."
        )
    else:
        parts.append("There is nothing urgent waiting.")

    condition = weather.get("condition", "")
    if condition in {"rain_likely", "rain_later", "storm"}:
        parts.append("Rain is likely, so handle outdoor errands early.")
    elif condition == "clear":
        parts.append("Conditions look clear.")
    elif condition:
        parts.append(f"Expect {condition.replace('_', ' ')} conditions.")

    return " ".join(parts)


def generate_briefing(weather, calendar, priority_items):
    fallback = fallback_briefing(weather, calendar, priority_items)
    if not available():
        return fallback

    try:
        context = {
            "weather": weather,
            "calendar": calendar,
            "priority_items": priority_items,
        }
        response = client().messages.create(
            model=MODEL,
            max_tokens=220,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False),
                }
            ],
        )
        return text_of(response) or fallback
    except Exception:
        return fallback
