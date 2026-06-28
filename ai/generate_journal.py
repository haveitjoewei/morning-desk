"""Journal prompt — one short reflective question tuned to the day."""
from __future__ import annotations

import json

from ai._llm import MODEL, available, client, text_of

SYSTEM = (
    "You write ONE short morning journal prompt for a calm desk display — a question that "
    "helps the reader prepare and clear their head before the day, not vague positivity. "
    "Draw on grounded reflective traditions and rotate the angle day to day:\n"
    "- Stoic morning prep: anticipate one likely friction and how to meet it; separate what "
    "is and isn't in their control.\n"
    "- Intention (Five-Minute Journal): what would make today good; the single thing that "
    "matters most.\n"
    "- For an over-thinker: narrow rather than widen — name one focus, set down a worry, or "
    "notice a thought without being run by it (cognitive defusion).\n"
    "Ground it in today's calendar/load when useful: a full day -> a focusing prompt; an "
    "open day -> an intention prompt. One sentence, an open question, no preamble, no "
    "quotes, no markdown — just the question."
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
