"""Turn a person's preferences and a day's tweaks into engine inputs.

Standing prefs (runs cold, style notes, love/avoid colours) plus per-day overrides
(occasion, temperature nudge, anchor a piece, free-text wish) become a single
request the outfit generator folds into its stylist prompt and selection.
"""
from __future__ import annotations

OCCASION_FORMALITY = {
    "casual": "casual",
    "cozy home": "casual",
    "work": "smart casual",
    "dressy": "smart casual",
    "going out": "smart casual",
}


def effective_high(high, prefs, day):
    """Temperature the outfit should dress for, after cold-bias and the day nudge."""
    high = high if isinstance(high, (int, float)) else 18
    if (prefs or {}).get("runs_cold"):
        high -= 3
    nudge = (day or {}).get("temp_nudge")
    if nudge == "warmer":
        high -= 2
    elif nudge == "lighter":
        high += 3
    return round(high)


def build_request(prefs, day):
    prefs, day = prefs or {}, day or {}
    bits = []
    if prefs.get("style_notes"):
        bits.append(f"Personal style: {prefs['style_notes']}.")
    if prefs.get("love_colors"):
        bits.append(f"Favours these colours: {', '.join(prefs['love_colors'])}.")
    if prefs.get("avoid_colors"):
        bits.append(f"Avoid these colours: {', '.join(prefs['avoid_colors'])}.")
    if prefs.get("runs_cold"):
        bits.append("Runs cold — prefer thicker layers and an extra layer.")
    if day.get("wish"):
        bits.append(f"Today she asked for: {day['wish']}.")
    occasion = (day.get("occasion") or "casual").lower()
    return {
        "anchor": day.get("anchor"),
        "formality_hint": OCCASION_FORMALITY.get(occasion, "casual"),
        "occasion": occasion,
        "instructions": " ".join(bits),
        "runs_cold": bool(prefs.get("runs_cold")),
    }
