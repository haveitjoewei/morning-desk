"""On-demand outfit planning for a profile — what the web app calls per request.

Pulls the profile's weather + wardrobe, turns the wearer's prefs + the day's
tweaks into a style request (applying cold-bias and the temperature nudge to the
temperature the engine dresses for), generates the outfit, and resolves the
chosen pieces to images. Stateless: no caching, the wearer decides when to ask.
"""
from __future__ import annotations

from ai.generate_outfit import generate_outfit
from ai.style_request import build_request, effective_high
from connectors.weather import fetch_weather_for
from wardrobe.catalog import load_wardrobe, resolve_pieces


def plan_outfit(profile, prefs=None, day=None):
    prefs, day = prefs or {}, day or {}
    weather = fetch_weather_for(profile)
    wardrobe = load_wardrobe(profile=profile)
    request = build_request(prefs, day)

    # Dress for the cold-bias/nudge-adjusted temperature, but keep the real summary.
    dressed_weather = {**weather, "high": effective_high(weather.get("high"), prefs, day)}
    outfit = generate_outfit(
        dressed_weather,
        wardrobe,
        calendar=[],
        context={"intent": request["occasion"]},
        request=request,
    )
    outfit = {**outfit, "pieces": resolve_pieces(outfit.get("items", []), wardrobe, profile=profile)}
    return {**outfit, "weather": weather}
