"""Outfit suggestion — weather + wardrobe + calendar → {headline, items, reason}.

Claude picks from the user's actual wardrobe when a credential is present;
otherwise a deterministic rule-based fallback keeps the contract identical.
"""
from __future__ import annotations

import json

from ai._llm import MODEL, available, client, text_of

SYSTEM = (
    "You are a concise personal stylist for a morning e-ink briefing. "
    "Pick a practical outfit from ONLY the wardrobe items provided. "
    "Respond with the structured object: a short headline, 3-5 item names "
    "(verbatim from the wardrobe), and one short reason citing weather/calendar."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "items": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
    "required": ["headline", "items", "reason"],
    "additionalProperties": False,
}


def _fallback(weather, wardrobe_items, calendar):
    wants_rain = weather.get("condition") in ("rain", "rain_later", "rain_showers", "drizzle")

    def first(category, *, rain_ok=None):
        for item in wardrobe_items:
            if item["category"] != category:
                continue
            if rain_ok is not None and item["rain_ok"] != rain_ok:
                continue
            return item["name"]
        return None

    items = [
        first("outerwear", rain_ok=True) if wants_rain else first("midlayer"),
        first("top"),
        first("bottom"),
        first("shoes", rain_ok=True) if wants_rain else first("shoes"),
    ]
    items = [item for item in items if item]

    return {
        "headline": "Rain-ready casual" if wants_rain else "Easy casual layers",
        "items": items,
        "reason": "Rain later, mild temperature, casual calendar."
        if wants_rain
        else "Mild day, casual calendar.",
    }


def generate_outfit(weather, wardrobe_items, calendar=None):
    calendar = calendar or []
    if not available():
        return _fallback(weather, wardrobe_items, calendar)
    try:
        wardrobe = [
            {"name": i["name"], "category": i["category"], "rain_ok": i.get("rain_ok")}
            for i in wardrobe_items
        ]
        payload = json.dumps(
            {"weather": weather, "calendar": calendar, "wardrobe": wardrobe},
            ensure_ascii=False,
        )
        resp = client().messages.create(
            model=MODEL,
            max_tokens=400,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": payload}],
        )
        data = json.loads(text_of(resp))
        if len(data.get("items", [])) >= 3:
            return data
    except Exception:
        pass
    return _fallback(weather, wardrobe_items, calendar)
