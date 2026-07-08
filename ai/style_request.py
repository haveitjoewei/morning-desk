"""Turn a person's preferences and a day's tweaks into engine inputs.

Standing prefs (runs cold, style notes, love/avoid colours) plus per-day controls
become a single request the outfit generator folds into its stylist prompt and
selection:
  - occasion + dress_step  -> a formality target (dressier / more casual, continuous)
  - temp_step              -> warmer / lighter, continuous (each step ~2C)
  - anchor / anchors       -> build around one or more specific pieces
  - wish                   -> free-text instruction
  - variety                -> ask for a fresh, less-obvious combination
  - rejections / exclude   -> pieces to avoid (with reasons)
"""
from __future__ import annotations

FORMALITY_LEVELS = ["casual", "smart casual", "business", "formal"]
OCCASION_BASE = {
    "casual": 0, "cozy home": 0, "weekend": 0, "work": 1, "dressy": 1, "going out": 1, "formal": 3,
}


def effective_high(high, prefs, day):
    """Temperature the outfit should dress for, after cold-bias and the warmth steps."""
    high = high if isinstance(high, (int, float)) else 18
    prefs, day = prefs or {}, day or {}
    if prefs.get("runs_cold"):
        high -= 3
    nudge = day.get("temp_nudge")
    if nudge == "warmer":
        high -= 2
    elif nudge == "lighter":
        high += 3
    high += int(day.get("temp_step", 0)) * 2  # negative steps = warmer
    # A "too cold"/"too warm" swap reason should re-pick that slot warmer/lighter — not
    # just avoid the piece. A swap pins the rest, so this only shifts the swapped slot.
    for rej in day.get("rejections") or []:
        reason = (rej.get("reason", "") if isinstance(rej, dict) else "").lower()
        if "cold" in reason:
            high -= 4
        elif "warm" in reason or "hot" in reason:
            high += 4
    return round(high)


def _formality(occasion, dress_step):
    base = OCCASION_BASE.get(occasion, 0)
    idx = max(0, min(len(FORMALITY_LEVELS) - 1, base + int(dress_step or 0)))
    return FORMALITY_LEVELS[idx]


def build_request(prefs, day):
    prefs, day = prefs or {}, day or {}
    occasion = (day.get("occasion") or "casual").lower()
    formality = _formality(occasion, day.get("dress_step", 0))

    avoid = list(day.get("exclude") or [])
    recent = list(day.get("recent") or [])
    bits = []
    if prefs.get("style_notes"):
        bits.append(f"Personal style: {prefs['style_notes']}.")
    for rule in prefs.get("rules") or []:
        bits.append(rule)
    if recent:
        bits.append(
            "Recently worn — rotate away from these for variety unless one is clearly "
            f"ideal today: {', '.join(recent)}."
        )
    if prefs.get("love_colors"):
        bits.append(f"Favours these colours: {', '.join(prefs['love_colors'])}.")
    if prefs.get("avoid_colors"):
        bits.append(f"Avoid these colours: {', '.join(prefs['avoid_colors'])}.")
    if prefs.get("runs_cold"):
        bits.append("Runs cold — prefer thicker layers and an extra layer.")
    bits.append(f"Target formality: {formality}.")
    if day.get("wish"):
        bits.append(f"Today she asked for: {day['wish']}.")
    for rej in day.get("rejections") or []:
        name = rej.get("item") if isinstance(rej, dict) else rej
        reason = rej.get("reason", "") if isinstance(rej, dict) else ""
        if name:
            avoid.append(name)
            bits.append(f"Do NOT use '{name}'{f' ({reason})' if reason else ''}; pick something else.")
    if day.get("variety"):
        bits.append("Offer a fresh, less-obvious combination — avoid the usual go-to pieces.")
    anchors = list(day.get("anchors") or ([day["anchor"]] if day.get("anchor") else []))
    if anchors:
        bits.append(f"Anchor these pieces if they can coexist in one outfit: {', '.join(anchors)}.")

    return {
        "anchor": day.get("anchor"),
        "anchors": anchors,
        "formality_hint": formality,
        "occasion": occasion,
        "instructions": " ".join(bits),
        "style_notes": prefs.get("style_notes", ""),
        "runs_cold": bool(prefs.get("runs_cold")),
        "avoid": avoid,
        "recent": recent,
        "variety": bool(day.get("variety")),
    }
