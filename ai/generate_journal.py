"""Journal prompt — one short reflective question tuned to the day."""
from __future__ import annotations

import json

from ai._llm import MODEL, available, client, text_of

SYSTEM = (
    "You write a single short morning journal prompt for a calm e-ink desk display. "
    "One sentence, a reflective open question, grounded in the day's context when useful. "
    "No preamble, no quotes, no markdown — just the question."
)

_FALLBACK = "What is one thing that would make today feel under control?"


def generate_journal_prompt(briefing=None, calendar=None):
    if not available():
        return _FALLBACK
    try:
        context = {"briefing": briefing or "", "calendar": calendar or []}
        resp = client().messages.create(
            model=MODEL,
            max_tokens=100,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
        )
        out = text_of(resp)
        return out or _FALLBACK
    except Exception:
        return _FALLBACK
