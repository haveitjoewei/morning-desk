import json
import re
import shutil
from pathlib import Path


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
COLOR_WORDS = {
    "black",
    "blue",
    "brown",
    "cream",
    "green",
    "grey",
    "gray",
    "navy",
    "olive",
    "white",
}
CATEGORY_WORDS = {
    "coat": "outerwear",
    "jacket": "outerwear",
    "parka": "outerwear",
    "shell": "outerwear",
    "hoodie": "midlayer",
    "overshirt": "midlayer",
    "sweater": "midlayer",
    "jumper": "midlayer",
    "shirt": "top",
    "tee": "top",
    "tshirt": "top",
    "pants": "bottom",
    "jeans": "bottom",
    "trousers": "bottom",
    "shorts": "bottom",
    "boots": "shoes",
    "shoes": "shoes",
    "sneakers": "shoes",
}


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "wardrobe-item"


def infer_category(words):
    for word in words:
        if word in CATEGORY_WORDS:
            return CATEGORY_WORDS[word]
    return "unknown"


def infer_colors(words):
    colors = [word for word in words if word in COLOR_WORDS]
    return ["grey" if color == "gray" else color for color in colors] or ["unknown"]


def draft_record(source, image_path):
    stem = source.stem
    words = re.findall(r"[a-z0-9]+", stem.lower())
    text = " ".join(words)
    rain_ok = any(word in text for word in ["rain", "waterproof", "shell", "goretex"])

    return {
        "id": slugify(stem),
        "name": text,
        "category": infer_category(words),
        "colors": infer_colors(words),
        "warmth": "unknown",
        "rain_ok": rain_ok,
        "wind_ok": rain_ok,
        "formality": "unknown",
        "style_tags": ["needs_review"],
        "material_guess": "unknown",
        "texture": "unknown",
        "thickness": "unknown",
        "fit": "unknown",
        "best_for": [],
        "avoid_for": [],
        "review_status": "needs_review",
        "confidence": "low",
        "correction_history": [],
        "image": str(image_path),
        "notes": "",
    }


def import_photos(inbox=None, images=None, drafts=None):
    root = Path(__file__).resolve().parents[1]
    inbox = Path(inbox) if inbox else root / "wardrobe" / "inbox"
    images = Path(images) if images else root / "wardrobe" / "images"
    drafts = Path(drafts) if drafts else root / "wardrobe" / "drafts.json"

    inbox.mkdir(parents=True, exist_ok=True)
    images.mkdir(parents=True, exist_ok=True)

    records = []
    for source in sorted(inbox.iterdir()):
        if not source.is_file() or source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        item_id = slugify(source.stem)
        target = images / f"{item_id}{source.suffix.lower().replace('.jpeg', '.jpg')}"
        shutil.copy2(source, target)
        image_path = Path("wardrobe") / "images" / target.name
        records.append(draft_record(source, image_path))

    drafts.parent.mkdir(parents=True, exist_ok=True)
    drafts.write_text(json.dumps(records, indent=2) + "\n")
    return records


def main():
    records = import_photos()
    print(f"Wrote {len(records)} wardrobe draft item(s) to wardrobe/drafts.json")


if __name__ == "__main__":
    main()
