"""End-of-day reflection prompt + a recap of today, with a local fallback.

Note: the system has no record of what actually happened today, so the recap is
built from today's *scheduled* events and invites you to name your own wins — it
does not fabricate accomplishments.
"""
from __future__ import annotations

import json

from ai._llm import MODEL, available, client, text_of

SYSTEM = (
    "You write a calm end-of-day card for a living-room display. Given today's "
    "scheduled events, return: a 'recap' (1-2 plain sentences noting what was on "
    "today and gently inviting the person to name a win) and a 'reflection' (one "
    "short open question for winding down). You do not know what actually happened, "
    "so never claim accomplishments — frame the recap around the schedule. No "
    "greeting, no markdown."
)

SCHEMA = {
    "type": "object",
    "properties": {"recap": {"type": "string"}, "reflection": {"type": "string"}},
    "required": ["recap", "reflection"],
    "additionalProperties": False,
}

_FALLBACK_REFLECTION = "What is one thing from today worth carrying into tomorrow?"


def _fallback(calendar):
    if calendar:
        titles = ", ".join(e.get("title", "") for e in calendar[:3])
        recap = f"Today held: {titles}. Which of these turned into a win?"
    else:
        recap = "An open day with nothing on the calendar. What did you make of it?"
    return {"recap": recap, "reflection": _FALLBACK_REFLECTION}


def generate_reflection(calendar=None):
    calendar = calendar or []
    if not available():
        return _fallback(calendar)
    try:
        context = {"today_events": [{"time": e.get("time"), "title": e.get("title")} for e in calendar]}
        resp = client().messages.create(
            model=MODEL,
            max_tokens=300,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
        )
        data = json.loads(text_of(resp))
        if data.get("recap") and data.get("reflection"):
            return data
    except Exception:
        pass
    return _fallback(calendar)
