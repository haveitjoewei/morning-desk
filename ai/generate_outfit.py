def generate_outfit(weather, wardrobe_items, calendar=None):
    calendar = calendar or []
    wants_rain = weather.get("condition") == "rain_later"

    def first(category, *, rain_ok=None):
        for item in wardrobe_items:
            if item["category"] != category:
                continue
            if rain_ok is not None and item["rain_ok"] != rain_ok:
                continue
            return item["name"]
        return None

    items = [
        first("outerwear", rain_ok=True) if wants_rain else first("midlayer"),
        first("top"),
        first("bottom"),
        first("shoes", rain_ok=True) if wants_rain else first("shoes"),
    ]
    items = [item for item in items if item]

    return {
        "headline": "Rain-ready casual" if wants_rain else "Easy casual layers",
        "items": items,
        "reason": "Rain later, mild temperature, casual calendar.",
    }
