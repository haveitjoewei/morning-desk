"""Choose a weather- and calendar-aware outfit from known wardrobe items."""
import json

from ai._llm import MODEL, available, client, text_of


OUTFIT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "items": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
    "required": ["headline", "items", "reason"],
    "additionalProperties": False,
}

SYSTEM = (
    "Choose one outfit only from the provided wardrobe item names. Balance weather, "
    "style, dress code, and activity. Return a short headline, 3-5 exact item names, "
    "and one concise reason. Never invent an item."
)


def fallback_outfit(weather, wardrobe_items, calendar=None):
    calendar = calendar or []
    wants_rain = weather.get("condition") in {"rain_later", "rain_likely", "storm"}
    smart_casual = any(event.get("dress_code") == "smart casual" for event in calendar)
    athletic_events = [event for event in calendar if event.get("dress_code") == "athletic"]
    condition = weather.get("condition", "weather").replace("_", " ")
    temperature_note = "mild temperature"
    if weather.get("high", 0) <= 14:
        temperature_note = "cool day"
    elif weather.get("high", 0) >= 26:
        temperature_note = "warm day"

    def first(category, *, rain_ok=None, formality=None):
        for item in wardrobe_items:
            if item["category"] != category:
                continue
            if rain_ok is not None and item.get("rain_ok") != rain_ok:
                continue
            if formality is not None and item.get("formality") != formality:
                continue
            return item["name"]
        return None

    formality = "smart casual" if smart_casual else None
    items = [
        first("outerwear", rain_ok=True)
        if wants_rain
        else first("midlayer", formality=formality),
        first("top", formality=formality) or first("top"),
        first("bottom", formality=formality) or first("bottom"),
        first("shoes", rain_ok=True, formality=formality)
        if wants_rain
        else first("shoes", formality=formality),
    ]
    items = [item for item in items if item]

    headline = "Rain-ready casual" if wants_rain else "Easy casual layers"
    calendar_note = "smart casual calendar" if smart_casual else "casual calendar"
    if smart_casual:
        headline = "Smart casual layers"
    athletic_note = ""
    if athletic_events:
        athletic_note = f" Bring athletic kit for {athletic_events[0]['title']}."

    return {
        "headline": headline,
        "items": items,
        "reason": (
            f"{condition.capitalize()}, {temperature_note}, {calendar_note}."
            f"{athletic_note}"
        ),
    }


def valid_outfit(outfit, wardrobe_items):
    known = {item["name"] for item in wardrobe_items}
    return (
        isinstance(outfit, dict)
        and isinstance(outfit.get("headline"), str)
        and isinstance(outfit.get("reason"), str)
        and isinstance(outfit.get("items"), list)
        and 2 <= len(outfit["items"]) <= 5
        and all(isinstance(item, str) and item in known for item in outfit["items"])
    )


def generate_outfit(weather, wardrobe_items, calendar=None):
    calendar = calendar or []
    fallback = fallback_outfit(weather, wardrobe_items, calendar)
    if not available():
        return fallback

    try:
        context = {
            "weather": weather,
            "calendar": calendar,
            "wardrobe": wardrobe_items,
        }
        response = client().messages.create(
            model=MODEL,
            max_tokens=260,
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": OUTFIT_SCHEMA,
                }
            },
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
        outfit = json.loads(text_of(response))
        return outfit if valid_outfit(outfit, wardrobe_items) else fallback
    except Exception:
        return fallback
