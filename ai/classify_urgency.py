"""Urgency classifier — RawEvent → one of ignore | low | today | urgent.

Claude classifies when a credential is present; otherwise a keyword heuristic
keeps the morning job deterministic and offline-safe. Only `today`/`urgent`
items surface on the display (filtering happens downstream in the schema).
"""
from __future__ import annotations

import json

from ai._llm import MODEL, available, client, text_of

URGENCY = ("ignore", "low", "today", "urgent")

SYSTEM = (
    "You triage one inbound message for a morning briefing. Classify how much it "
    "needs the user's attention TODAY into exactly one of: "
    "'urgent' (blocking, needs a decision/reply now), "
    "'today' (should be handled today but not blocking), "
    "'low' (informational, can wait), "
    "'ignore' (noise, no action). When uncertain, prefer 'today' over 'urgent'."
)

SCHEMA = {
    "type": "object",
    "properties": {"urgency": {"type": "string", "enum": list(URGENCY)}},
    "required": ["urgency"],
    "additionalProperties": False,
}


def _heuristic(event):
    text = f"{event.title} {event.body}".lower()
    if "blocking" in text or "approval" in text:
        return "urgent"
    if "awaiting reply" in text or "asked" in text:
        return "today"
    return "low"


def classify_urgency(event):
    if not available():
        return _heuristic(event)
    try:
        payload = json.dumps(
            {"source": event.source, "title": event.title, "body": event.body},
            ensure_ascii=False,
        )
        resp = client().messages.create(
            model=MODEL,
            max_tokens=50,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": payload}],
        )
        urgency = json.loads(text_of(resp)).get("urgency")
        if urgency in URGENCY:
            return urgency
    except Exception:
        pass
    return _heuristic(event)
