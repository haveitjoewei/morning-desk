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
}


def load_weather_config(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[1] / "config" / "location.json"
    return json.loads(path.read_text())


def build_open_meteo_url(config):
    query = urlencode(
        {
            "latitude": config["latitude"],
            "longitude": config["longitude"],
            "timezone": config.get("timezone", "auto"),
            "forecast_days": 1,
            "current": "temperature_2m,weather_code,precipitation",
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


def parse_open_meteo(payload):
    current = payload["current"]
    daily = payload["daily"]
    high = round(daily["temperature_2m_max"][0])
    low = round(daily["temperature_2m_min"][0])
    precipitation_probability = daily.get("precipitation_probability_max", [0])[0] or 0
    precipitation_mm = daily.get("precipitation_sum", [0])[0] or 0
    weather_code = daily.get("weather_code", [current.get("weather_code", 0)])[0]
    condition = condition_from(weather_code, precipitation_probability, precipitation_mm)

    return {
        "summary": summary_for(current["temperature_2m"], condition),
        "high": high,
        "low": low,
        "condition": condition,
        "precipitation_probability": precipitation_probability,
        "precipitation_mm": precipitation_mm,
    }


def fetch_open_meteo(config):
    with urlopen(build_open_meteo_url(config), timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_weather(config_path=None):
    if os.environ.get("MD_OFFLINE") == "1":
        return FALLBACK_WEATHER.copy()
    try:
        return parse_open_meteo(fetch_open_meteo(load_weather_config(config_path)))
    except (OSError, URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return FALLBACK_WEATHER.copy()
