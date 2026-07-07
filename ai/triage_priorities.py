"""Triage inbound messages for the attention list — urgency + a useful summary.

One Claude call classifies every inbound item and writes a short, specific
summary of what it is and what (if anything) needs doing — so the attention list
shows "Guest asks about early check-in — reply needed", not a raw subject line.
Auto-confirmations and platform notifications are downranked to 'low' so they
drop off the list. Offline/no-key falls back to a keyword heuristic + snippet.
"""
from __future__ import annotations

import json

from ai._llm import MODEL, available, client, text_of
from ai.classify_urgency import _heuristic

URGENCY = ("ignore", "low", "today", "urgent")

SYSTEM = (
    "You triage a host's inbound messages (Airbnb, VA/email) for a morning briefing "
    "attention list. For EACH message, in input order, return an urgency and a short "
    "summary.\n"
    "urgency:\n"
    "- 'urgent': needs a decision or reply now / blocking.\n"
    "- 'today': a guest question or host action to handle today.\n"
    "- 'low': informational — booking or reservation confirmations, payout notices, "
    "receipts, automated platform notifications, and automated reminders about "
    "UPCOMING/FUTURE arrivals or check-ins ('X is coming soon', 'reservation reminder') "
    "where the arrival is not today. These need no reply; default such messages to 'low'. "
    "Only mark an arrival reminder 'today'/'urgent' if the guest arrives today or is "
    "actually asking a question.\n"
    "- 'ignore': pure noise.\n"
    "summary: one specific line (<= 12 words) saying what it is and what to do, e.g. "
    "'Guest Aimee asks about early check-in — reply needed' or 'Booking confirmed for "
    "Aug 1 — no action'. Return exactly one object per input message, in order."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "urgency": {"type": "string", "enum": list(URGENCY)},
                    "summary": {"type": "string"},
                },
                "required": ["urgency", "summary"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def _short(text, words=14):
    parts = (text or "").split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def _fallback(events):
    return [{"urgency": _heuristic(e), "summary": _short(e.body) or e.title} for e in events]


def triage(events):
    """Return [{urgency, summary}] aligned to events."""
    events = list(events)
    if not events:
        return []
    if not available():
        return _fallback(events)
    try:
        payload = [
            {"i": idx, "source": e.source, "subject": e.title, "snippet": e.body}
            for idx, e in enumerate(events)
        ]
        resp = client().messages.create(
            model=MODEL,
            max_tokens=900,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        items = json.loads(text_of(resp)).get("items", [])
        if len(items) == len(events):
            out = []
            for item in items:
                urgency = item.get("urgency")
                out.append({
                    "urgency": urgency if urgency in URGENCY else "low",
                    "summary": item.get("summary") or "",
                })
            return out
    except Exception:
        pass
    return _fallback(events)
