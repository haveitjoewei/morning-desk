"""Briefing — 2-3 sentence narrative summary of the day from calendar + context."""
from __future__ import annotations

import json

from ai._llm import MODEL, available, client, text_of

SYSTEM = (
    "You write the morning briefing for a distraction-free e-ink desk display. "
    "Given the day's weather, calendar, and priority items, write 2-3 calm, "
    "plain sentences summarizing what needs attention before the day starts. "
    "No greeting, no preamble, no markdown — just the briefing sentences."
)

_FALLBACK = (
    "A light admin morning with one guest issue and one VA decision needing attention. "
    "The afternoon looks wet, so handle errands early if you can."
)


def generate_briefing(calendar=None, weather=None, priority_items=None):
    if not available():
        return _FALLBACK
    try:
        context = {
            "weather": weather or {},
            "calendar": calendar or [],
            "priority_items": [
                {
                    "title": getattr(p, "title", None) or p.get("title"),
                    "urgency": getattr(p, "urgency", None) or p.get("urgency"),
                    "source": getattr(p, "source", None) or p.get("source"),
                }
                for p in (priority_items or [])
            ],
        }
        resp = client().messages.create(
            model=MODEL,
            max_tokens=300,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
        )
        out = text_of(resp)
        return out or _FALLBACK
    except Exception:
        return _FALLBACK
