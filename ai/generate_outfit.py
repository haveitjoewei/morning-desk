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
    "You are a professional menswear stylist assembling one cohesive outfit from the "
    "client's actual wardrobe. Use ONLY the provided item names — never invent an item.\n"
    "Style like a stylist, not a checklist:\n"
    "- Palette: build on a neutral base (1-2 neutrals) and add at most ONE accent colour. "
    "Keep colours harmonious — analogous or a considered complementary pop; never two "
    "competing brights. Earth tones (olive/tan/brown) pair together; navy and grey are "
    "safe anchors.\n"
    "- Contrast & depth: balance light and dark values so the outfit isn't flat; an all-"
    "tonal look is fine only if deliberate (e.g. layered greys).\n"
    "- Pattern: at most one patterned piece; everything else solid.\n"
    "- Proportion & layering: a complete look is top + bottom + shoes; add a mid-layer or "
    "outerwear only when warmth or rain calls for it. Don't stack two bulky layers.\n"
    "- Register: keep every piece in one formality lane — today's intent decides it "
    "(office/dress_to_impress leans 'smart casual'; work_from_home/off is 'casual'). Each "
    "item's 'formality' lists the settings it suits.\n"
    "- Weather: weight warmth/thickness/material to the temperature; prefer rain_ok pieces "
    "when rain is likely. Avoid 'worn'-condition items when dressing to impress.\n"
    "Return a short evocative headline, 3-5 exact item names, and one tight reason that "
    "names the occasion and explains WHY the pieces work together (the colour/texture logic)."
)


def _formality_ok(item, target):
    """Formality may be a scalar (legacy) or a list of suitable settings."""
    value = item.get("formality")
    if isinstance(value, list):
        return target in value
    return value == target


def fallback_outfit(weather, wardrobe_items, calendar=None, context=None):
    calendar = calendar or []
    context = context or {}
    wants_rain = weather.get("condition") in {"rain_later", "rain_likely", "storm"}
    smart_casual = any(event.get("dress_code") == "smart casual" for event in calendar)
    athletic_events = [event for event in calendar if event.get("dress_code") == "athletic"]
    office_day = context.get("work_mode") == "office"
    dress_to_impress = context.get("intent") == "dress_to_impress" or office_day
    condition = weather.get("condition", "weather").replace("_", " ")
    temperature_note = "mild temperature"
    if weather.get("high", 0) <= 14:
        temperature_note = "cool day"
    elif weather.get("high", 0) >= 26:
        temperature_note = "warm day"

    def score(item, formality=None):
        value = 0
        if formality and _formality_ok(item, formality):
            value += 4
        if athletic_events:
            if _formality_ok(item, "athletic"):
                value += 2
        elif _formality_ok(item, "athletic") and not _formality_ok(item, "casual"):
            value -= 5
        if dress_to_impress and "dress_to_impress" in item.get("style_tags", []):
            value += 3
        if office_day and "office" in item.get("best_for", []):
            value += 2
        if context.get("occasion") and context["occasion"] in item.get("best_for", []):
            value += 2
        if (
            item.get("category") == "bottom"
            and "short" in item.get("subtype", "").lower()
            and weather.get("high", 0) < 24
        ):
            value -= 3
        return value

    def first(category, *, rain_ok=None, formality=None):
        matches = []
        for item in wardrobe_items:
            if item["category"] != category:
                continue
            if rain_ok is not None and item.get("rain_ok") != rain_ok:
                continue
            matches.append(item)
        if not matches:
            return None
        matches.sort(key=lambda item: score(item, formality), reverse=True)
        best = matches[0]
        if formality and not _formality_ok(best, formality) and score(best, formality) == 0:
            return None
        return best["name"]

    formality = "smart casual" if smart_casual or dress_to_impress else "casual"
    items = [
        first("outerwear", rain_ok=True)
        if wants_rain
        else first("midlayer", formality=formality),
        first("top", formality=formality) or first("top"),
        first("bottom", formality=formality) or first("bottom"),
        first("shoes", rain_ok=True, formality=formality) or first("shoes", formality=formality)
        if wants_rain
        else first("shoes", formality=formality),
    ]
    items = [item for item in items if item]

    headline = "Rain-ready casual" if wants_rain else "Easy casual layers"
    calendar_note = "smart casual calendar" if smart_casual else "casual calendar"
    if smart_casual:
        headline = "Smart casual layers"
    elif office_day:
        headline = "Office polish"
        calendar_note = "office day, dress to impress"
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


def generate_outfit(weather, wardrobe_items, calendar=None, context=None):
    calendar = calendar or []
    context = context or {}
    fallback = fallback_outfit(weather, wardrobe_items, calendar, context)
    if not available():
        return fallback

    try:
        context = {
            "weather": weather,
            "calendar": calendar,
            "context": context,
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
