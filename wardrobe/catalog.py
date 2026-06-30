import json
from pathlib import Path

from core.profiles import DEFAULT_PROFILE, items_path


def _append_unique(values, additions):
    values = list(values or [])
    for addition in additions or []:
        if addition not in values:
            values.append(addition)
    return values


def _apply_correction(item, correction):
    item = dict(item)
    for key, value in correction.get("set", {}).items():
        item[key] = value

    for key, additions in correction.get("add", {}).items():
        item[key] = _append_unique(item.get(key, []), additions)

    if correction.get("note"):
        item["correction_history"] = _append_unique(
            item.get("correction_history", []),
            [correction["note"]],
        )
    return item


def load_wardrobe(path=None, corrections_path=None, profile=DEFAULT_PROFILE):
    path = Path(path) if path else items_path(profile)
    items = json.loads(path.read_text())
    corrections_path = (
        Path(corrections_path)
        if corrections_path
        else path.with_name("corrections.json")
    )
    if not corrections_path.exists():
        return items

    corrections = json.loads(corrections_path.read_text())
    by_name = {correction.get("name"): correction for correction in corrections}
    return [
        _apply_correction(item, by_name[item["name"]])
        if item.get("name") in by_name
        else item
        for item in items
    ]


def save_metadata_correction(item_id, values, profile=DEFAULT_PROFILE):
    path = items_path(profile)
    items = json.loads(path.read_text())
    item = next((it for it in items if item_id in (it.get("id"), it.get("name"))), None)
    if not item:
        return None

    allowed = {"warmth", "polish", "comfort", "home_ok", "office_ok", "wear_frequency", "avoid_often"}
    set_values = {k: v for k, v in (values or {}).items() if k in allowed}
    for key in ("warmth", "polish", "comfort", "wear_frequency"):
        if key in set_values:
            set_values[key] = max(1, min(5, int(set_values[key])))
    for key in ("home_ok", "office_ok", "avoid_often"):
        if key in set_values:
            set_values[key] = bool(set_values[key])

    corrections_path = path.with_name("corrections.json")
    corrections = json.loads(corrections_path.read_text()) if corrections_path.exists() else []
    correction = next((c for c in corrections if c.get("name") == item["name"]), None)
    if not correction:
        correction = {"name": item["name"], "set": {}}
        corrections.append(correction)
    correction.setdefault("set", {}).update(set_values)
    corrections_path.write_text(json.dumps(corrections, indent=2) + "\n")
    return _apply_correction(item, correction)


_ROOT = Path(__file__).resolve().parents[1]


def _piece_image(item, profile=DEFAULT_PROFILE):
    """Resolve a garment's image under its profile, preferring the cleaned product
    shot, then the original photo, else None. Path derives from the item id."""
    item_id = item.get("id") or Path(item.get("image", "")).stem
    if not item_id:
        return None
    clean = f"profiles/{profile}/images_clean/{item_id}.jpg"
    original = f"profiles/{profile}/images/{item_id}.jpg"
    if (_ROOT / clean).exists():
        return clean
    if (_ROOT / original).exists():
        return original
    return None


def resolve_pieces(names, items, profile=DEFAULT_PROFILE):
    """Map chosen outfit item names to [{name, image, category}] for visual display."""
    by_name = {item.get("name"): item for item in items}
    pieces = []
    for name in names:
        item = by_name.get(name)
        pieces.append({
            "id": item.get("id") if item else None,
            "name": name,
            "image": _piece_image(item, profile) if item else None,
            "category": item.get("category", "") if item else "",
            "warmth": item.get("warmth") if item else None,
            "polish": item.get("polish") if item else None,
            "comfort": item.get("comfort") if item else None,
            "home_ok": item.get("home_ok") if item else None,
            "office_ok": item.get("office_ok") if item else None,
            "wear_frequency": item.get("wear_frequency") if item else None,
            "avoid_often": item.get("avoid_often") if item else None,
        })
    return pieces
