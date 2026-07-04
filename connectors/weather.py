import json
import os
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


OPEN_METEO_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
FALLBACK_WEATHER = {
    "summary": "18C, rain later",
    "high": 18,
    "low": 11,
    "condition": "rain_later",
    "precipitation_probability": 60,
    "precipitation_mm": 1.0,
    "hourly": [
        {"hour": 6, "temp": 12, "pop": 10, "mm": 0.0, "wind": 9},
        {"hour": 9, "temp": 14, "pop": 30, "mm": 0.2, "wind": 12},
        {"hour": 12, "temp": 17, "pop": 55, "mm": 0.6, "wind": 15},
        {"hour": 15, "temp": 18, "pop": 70, "mm": 1.2, "wind": 18},
        {"hour": 18, "temp": 15, "pop": 40, "mm": 0.3, "wind": 14},
        {"hour": 21, "temp": 13, "pop": 15, "mm": 0.0, "wind": 10},
    ],
}


def load_weather_config(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[1] / "config" / "location.json"
    return json.loads(path.read_text())


def build_open_meteo_url(config, days=1):
    query = urlencode(
        {
            "latitude": config["latitude"],
            "longitude": config["longitude"],
            "timezone": config.get("timezone", "auto"),
            "forecast_days": days,
            "current": "temperature_2m,weather_code,precipitation",
            "hourly": "temperature_2m,precipitation_probability,precipitation,wind_speed_10m",
            "daily": ",".join(
                [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                    "precipitation_sum",
                    "weather_code",
                ]
            ),
        }
    )
    return f"{OPEN_METEO_ENDPOINT}?{query}"


def condition_from(code, precipitation_probability=0, precipitation_mm=0):
    if code in {95, 96, 99}:
        return "storm"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "rain_likely" if precipitation_probability >= 70 or precipitation_mm >= 3 else "rain_later"
    if code in {45, 48}:
        return "fog"
    if code in {1, 2, 3}:
        return "cloudy"
    return "clear"


def summary_for(temp, condition):
    labels = {
        "rain_likely": "rain likely",
        "rain_later": "rain later",
        "storm": "storms",
        "snow": "snow",
        "fog": "fog",
        "cloudy": "cloudy",
        "clear": "clear",
    }
    return f"{round(temp)}C, {labels.get(condition, condition)}"


def parse_open_meteo(payload, day=0):
    current = payload.get("current", {})
    daily = payload["daily"]
    high = round(daily["temperature_2m_max"][day])
    low = round(daily["temperature_2m_min"][day])
    precipitation_probability = (daily.get("precipitation_probability_max") or [0] * (day + 1))[day] or 0
    precipitation_mm = (daily.get("precipitation_sum") or [0] * (day + 1))[day] or 0
    weather_code = (daily.get("weather_code") or [current.get("weather_code", 0)] * (day + 1))[day]
    condition = condition_from(weather_code, precipitation_probability, precipitation_mm)
    # Today uses the current temperature; future days use the daily high.
    temp = current.get("temperature_2m", high) if day == 0 else high

    return {
        "summary": summary_for(temp, condition),
        "high": high,
        "low": low,
        "condition": condition,
        "precipitation_probability": precipitation_probability,
        "precipitation_mm": precipitation_mm,
        "hourly": _hourly_precip(payload.get("hourly", {}), day),
    }


def _hourly_precip(hourly, day):
    """Waking-hours (6am-9pm) temp + precip chance for the target day, for an intraday bar."""
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    pops = hourly.get("precipitation_probability") or []
    mms = hourly.get("precipitation") or []
    winds = hourly.get("wind_speed_10m") or []
    bars = []
    for i in range(day * 24, min(day * 24 + 24, len(times))):
        hour = int(str(times[i])[11:13] or 0)
        if 6 <= hour <= 21:
            bars.append({
                "hour": hour,
                "temp": round(float(temps[i])) if i < len(temps) and temps[i] is not None else None,
                "pop": int(pops[i] or 0) if i < len(pops) else 0,
                "mm": round(float(mms[i] or 0), 2) if i < len(mms) else 0.0,
                "wind": round(float(winds[i])) if i < len(winds) and winds[i] is not None else None,
            })
    return bars


def fetch_open_meteo(config, days=1):
    # open-meteo has been slow (~8s); allow it to finish so the result gets cached
    # (in KV) for the next window instead of timing out and refetching every request.
    with urlopen(build_open_meteo_url(config, days), timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_weather(config_path=None, day=0):
    if os.environ.get("MD_OFFLINE") == "1":
        return FALLBACK_WEATHER.copy()
    try:
        payload = fetch_open_meteo(load_weather_config(config_path), days=day + 1)
        return parse_open_meteo(payload, day=day)
    except (OSError, URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        return FALLBACK_WEATHER.copy()


def geocode(name):
    """City name -> {latitude, longitude, timezone, label} via Open-Meteo (no key)."""
    if not name:
        return None
    query = urlencode({"name": name, "count": 1})
    try:
        with urlopen(f"https://geocoding-api.open-meteo.com/v1/search?{query}", timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    results = data.get("results") or []
    if not results:
        return None
    r = results[0]
    return {
        "latitude": r["latitude"],
        "longitude": r["longitude"],
        "timezone": r.get("timezone", "auto"),
        "label": ", ".join(filter(None, [r.get("name"), r.get("country_code")])),
    }


def fetch_weather_for(profile, day=0):
    """Weather for a profile's configured location (profiles/<profile>/config.json)."""
    if os.environ.get("MD_OFFLINE") == "1":
        return FALLBACK_WEATHER.copy()
    try:
        from core.profiles import load_config

        location = load_config(profile).get("location", {})
        payload = fetch_open_meteo(location, days=day + 1)
        return parse_open_meteo(payload, day=day)
    except (OSError, URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        return FALLBACK_WEATHER.copy()
