"""On-demand outfit planning for a profile — what the web app calls per request.

Pulls weather (for a chosen date/location, so she can plan ahead) and the
profile's wardrobe, defaults the occasion from her weekday schedule (office days),
turns prefs + the day's tweaks into a style request, generates the outfit, and
resolves the chosen pieces to images. Stateless.
"""
from __future__ import annotations

import datetime as _dt
import os

from ai.generate_outfit import generate_outfit
from ai.style_request import build_request, effective_high
from core.profiles import load_config, load_prefs
from wardrobe.catalog import load_wardrobe, resolve_pieces

UPPER_CATEGORIES = {"top", "blouse", "knit"}
LOWER_CATEGORIES = {"bottom", "pants", "jeans", "skirt", "shorts"}


def _anchor_slot(item):
    category = item.get("category")
    if category in UPPER_CATEGORIES:
        return "top"
    if category in LOWER_CATEGORIES:
        return "bottom"
    if category in {"midlayer", "cardigan", "outerwear"}:
        return "layer"
    return category


_HEAD_WORDS = ("hat", "cap", "beanie", "beret")


def _is_headwear(item):
    text = (item.get("subtype", "") + " " + item.get("name", "")).lower()
    return any(w in text for w in _HEAD_WORDS)


def anchor_warnings(wardrobe, anchors):
    by_id = {item.get("id"): item for item in wardrobe}
    selected = [by_id[a] for a in anchors or [] if a in by_id]
    warnings = []
    by_slot = {}
    for item in selected:
        by_slot.setdefault(_anchor_slot(item), []).append(item.get("name"))

    for slot, names in by_slot.items():
        if len(names) > 1 and slot in {"top", "bottom", "shoes", "bag", "dress"}:
            warnings.append(f"These may compete for the same {slot} slot: {', '.join(names)}.")
    heads = [item.get("name") for item in selected if _is_headwear(item)]
    if len(heads) > 1:
        warnings.append(f"You can only wear one on your head: {', '.join(heads)}.")
    if "dress" in by_slot and ("top" in by_slot or "bottom" in by_slot):
        warnings.append("A dress usually replaces a separate top and bottom.")
    return warnings


def _parse_date(value):
    if not value:
        return _dt.date.today()
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return _dt.date.today()


def _weather(cfg, location_override, offset):
    from connectors.weather import FALLBACK_WEATHER, fetch_open_meteo, parse_open_meteo

    if os.environ.get("MD_OFFLINE") == "1":
        return FALLBACK_WEATHER.copy()
    location = location_override or cfg.get("location", {})
    try:
        payload = fetch_open_meteo(location, days=offset + 1)
        return parse_open_meteo(payload, day=offset)
    except Exception:
        return FALLBACK_WEATHER.copy()


def _default_occasion(target_date, prefs):
    office_days = prefs.get("office_days", [1, 3])  # Tue, Thu
    return "Work" if target_date.weekday() in office_days else "Casual"


def plan_outfit(profile, prefs=None, day=None):
    prefs, day = {**load_prefs(profile), **(prefs or {})}, dict(day or {})
    cfg = load_config(profile)

    target = _parse_date(day.get("date"))
    offset = max(0, min(6, (target - _dt.date.today()).days))  # Open-Meteo: today..+6
    weather = _weather(cfg, day.get("location"), offset)

    if not day.get("occasion"):
        day["occasion"] = _default_occasion(target, prefs)

    wardrobe = load_wardrobe(profile=profile)
    request = build_request(prefs, day)
    dressed = {**weather, "high": effective_high(weather.get("high"), prefs, day)}
    outfit = generate_outfit(
        dressed, wardrobe, calendar=[], context={"intent": request["occasion"]}, request=request
    )
    outfit["pieces"] = resolve_pieces(outfit.get("items", []), wardrobe, profile=profile)
    return {**outfit, "weather": weather, "occasion": day["occasion"], "date": target.isoformat()}
