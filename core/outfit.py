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
