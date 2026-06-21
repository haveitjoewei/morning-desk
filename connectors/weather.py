"""Weather connector — Open-Meteo (free, no API key).

Returns the stable shape consumed by the orchestrator + outfit generator:
    {"summary": str, "high": int, "low": int, "condition": str}

Location is env-configurable so this is not hardcoded to one city:
    MD_LAT, MD_LON   floats   (default: Sydney, AU)
    MD_TZ            string   (default: auto)

Network/parse failures degrade gracefully to a safe "unknown" payload rather
than crashing the morning job — a briefing appliance must still render.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

API = "https://api.open-meteo.com/v1/forecast"
DEFAULT_LAT = -33.8688   # Sydney
DEFAULT_LON = 151.2093

# WMO weather codes → (condition slug, human label). Grouped to keep it readable.
_WMO = {
    0: ("clear", "clear"),
    1: ("mostly_clear", "mostly clear"),
    2: ("partly_cloudy", "partly cloudy"),
    3: ("overcast", "overcast"),
    45: ("fog", "fog"),
    48: ("fog", "freezing fog"),
    51: ("drizzle", "light drizzle"),
    53: ("drizzle", "drizzle"),
    55: ("drizzle", "heavy drizzle"),
    56: ("freezing_drizzle", "freezing drizzle"),
    57: ("freezing_drizzle", "freezing drizzle"),
    61: ("rain", "light rain"),
    63: ("rain", "rain"),
    65: ("rain", "heavy rain"),
    66: ("freezing_rain", "freezing rain"),
    67: ("freezing_rain", "freezing rain"),
    71: ("snow", "light snow"),
    73: ("snow", "snow"),
    75: ("snow", "heavy snow"),
    77: ("snow", "snow grains"),
    80: ("rain_showers", "rain showers"),
    81: ("rain_showers", "rain showers"),
    82: ("rain_showers", "violent rain showers"),
    85: ("snow_showers", "snow showers"),
    86: ("snow_showers", "snow showers"),
    95: ("thunderstorm", "thunderstorm"),
    96: ("thunderstorm", "thunderstorm with hail"),
    99: ("thunderstorm", "thunderstorm with hail"),
}


def _decode(code):
    return _WMO.get(code, ("unknown", "unsettled"))


def _location():
    lat = float(os.environ.get("MD_LAT", DEFAULT_LAT))
    lon = float(os.environ.get("MD_LON", DEFAULT_LON))
    tz = os.environ.get("MD_TZ", "auto")
    return lat, lon, tz


def _unavailable():
    return {
        "summary": "Weather unavailable",
        "high": None,
        "low": None,
        "condition": "unknown",
    }


def fetch_weather():
    lat, lon, tz = _location()
    query = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,weather_code",
            "timezone": tz,
            "forecast_days": 1,
        }
    )
    url = f"{API}?{query}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
        daily = data["daily"]
        high = round(daily["temperature_2m_max"][0])
        low = round(daily["temperature_2m_min"][0])
        condition, label = _decode(daily["weather_code"][0])
    except Exception:
        return _unavailable()

    return {
        "summary": f"{high}C, {label}",
        "high": high,
        "low": low,
        "condition": condition,
    }


if __name__ == "__main__":
    print(json.dumps(fetch_weather(), indent=2))
