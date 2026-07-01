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
_FORMALITY_RANK = {"athletic": 0, "casual": 1, "smart casual": 2, "business": 3, "formal": 4}
_BOLD_PATTERNS = {"graphic", "floral", "colorblock", "check", "animal", "leopard"}
_BOLD_WORDS = ("leopard", "floral", "plaid", "snakeskin", "zebra", "tie-dye", "sequin")


def _is_headwear(item):
    text = (item.get("subtype", "") + " " + item.get("name", "")).lower()
    return any(w in text for w in _HEAD_WORDS)


def _formality_ranks(item):
    value = item.get("formality")
    levels = value if isinstance(value, list) else ([value] if value else [])
    return [_FORMALITY_RANK[level] for level in levels if level in _FORMALITY_RANK]


def _is_bold_pattern(item):
    if item.get("pattern") in _BOLD_PATTERNS:
        return True
    text = (item.get("subtype", "") + " " + item.get("name", "")).lower()
    return any(w in text for w in _BOLD_WORDS)


def anchor_warnings(wardrobe, anchors):
    by_id = {item.get("id"): item for item in wardrobe}
    selected = [by_id[a] for a in anchors or [] if a in by_id]
    warnings = []
    by_slot = {}
    for item in selected:
        by_slot.setdefault(_anchor_slot(item), []).append(item.get("name"))

    # 1. Same wear-slot (two tops, two skirts, two bags, two dresses…)
    for slot, names in by_slot.items():
        if len(names) > 1 and slot in {"top", "bottom", "shoes", "bag", "dress"}:
            warnings.append(f"These may compete for the same {slot} slot: {', '.join(names)}.")
    # 2. Two head pieces
    heads = [item.get("name") for item in selected if _is_headwear(item)]
    if len(heads) > 1:
        warnings.append(f"You can only wear one on your head: {', '.join(heads)}.")
    # 3. A dress plus separates
    if "dress" in by_slot and ("top" in by_slot or "bottom" in by_slot):
        warnings.append("A dress usually replaces a separate top and bottom.")
    # 4. Formality clash — two pieces whose dressiness ranges don't overlap
    for i in range(len(selected)):
        for j in range(i + 1, len(selected)):
            a, b = _formality_ranks(selected[i]), _formality_ranks(selected[j])
            if a and b and (max(a) < min(b) - 1 or max(b) < min(a) - 1):
                warnings.append(
                    f"{selected[i].get('name')} and {selected[j].get('name')} are very "
                    "different dressiness levels."
                )
    # 5. Two bold patterns
    bold = [item.get("name") for item in selected if _is_bold_pattern(item)]
    if len(bold) > 1:
        warnings.append(f"Two bold patterns may clash: {', '.join(bold)}.")
    # 6. Warmth clash — only when a very warm and a very light piece compete for the SAME
    #    slot (e.g. two layers). Across slots a light base under a warm coat is valid layering.
    for names in by_slot.values():
        picks = [i for i in selected if i.get("name") in names]
        warm = [i.get("name") for i in picks if (i.get("warmth") or 3) >= 4]
        light = [i.get("name") for i in picks if (i.get("warmth") or 3) <= 1]
        if warm and light:
            warnings.append(f"These suit very different temperatures: {warm[0]} vs {light[0]}.")
            break
    return warnings


def _today(cfg):
    """Today in the profile's own timezone — the server runs in UTC, which is a day
    behind in Australia for much of the day."""
    tz = (cfg.get("location") or {}).get("timezone")
    if tz:
        try:
            from zoneinfo import ZoneInfo

            return _dt.datetime.now(ZoneInfo(tz)).date()
        except Exception:
            pass
    return _dt.date.today()


def _parse_date(value, today):
    if not value:
        return today
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return today


_WEATHER_CACHE = {}  # key -> (monotonic_expiry, weather); short-lived, per warm process
_WEATHER_TTL = 600  # seconds — a day's forecast doesn't move between rapid adjustments


def _weather(cfg, location_override, offset):
    import time

    from connectors.weather import FALLBACK_WEATHER, fetch_open_meteo, parse_open_meteo

    if os.environ.get("MD_OFFLINE") == "1":
        return FALLBACK_WEATHER.copy()
    location = location_override or cfg.get("location", {})
    key = (location.get("latitude"), location.get("longitude"), offset)
    hit = _WEATHER_CACHE.get(key)
    now = time.monotonic()
    if hit and hit[0] > now:
        return hit[1].copy()
    try:
        payload = fetch_open_meteo(location, days=offset + 1)
        weather = parse_open_meteo(payload, day=offset)
        _WEATHER_CACHE[key] = (now + _WEATHER_TTL, weather)
        return weather.copy()
    except Exception:
        return FALLBACK_WEATHER.copy()


def _default_occasion(target_date, prefs):
    office_days = prefs.get("office_days", [1, 3])  # Tue, Thu
    return "Work" if target_date.weekday() in office_days else "Casual"


def plan_outfit(profile, prefs=None, day=None):
    prefs, day = {**load_prefs(profile), **(prefs or {})}, dict(day or {})
    cfg = load_config(profile)

    today = _today(cfg)
    target = _parse_date(day.get("date"), today)
    offset = max(0, min(6, (target - today).days))  # Open-Meteo: today..+6
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
    place = (day.get("location") or cfg.get("location") or {}).get("label")
    return {
        **outfit,
        "weather": weather,
        "occasion": day["occasion"],
        "date": target.isoformat(),
        "place": place,
    }
