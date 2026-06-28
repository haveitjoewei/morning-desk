import json
from pathlib import Path


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


def load_wardrobe(path=None, corrections_path=None):
    path = Path(path) if path else Path(__file__).with_name("items.json")
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


_ROOT = Path(__file__).resolve().parents[1]


def _piece_image(item):
    """Prefer the cleaned product shot, fall back to the original photo, else None."""
    image = item.get("image")  # e.g. "wardrobe/images/<id>.jpg"
    if not image:
        return None
    clean = image.replace("/images/", "/images_clean/")
    if (_ROOT / clean).exists():
        return clean
    if (_ROOT / image).exists():
        return image
    return None


def resolve_pieces(names, items):
    """Map chosen outfit item names to [{name, image}] for visual display."""
    by_name = {item.get("name"): item for item in items}
    pieces = []
    for name in names:
        item = by_name.get(name)
        pieces.append({"name": name, "image": _piece_image(item) if item else None})
    return pieces
