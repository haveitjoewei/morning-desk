"""Vision wardrobe ingest — photo in, structured garment record out.

Reads every image in wardrobe/inbox/, sends each (upright, downscaled) to Claude
vision, and writes a structured record to wardrobe/items.json. Processed photos
are re-encoded upright and moved to wardrobe/images/<id>.jpg. Low-confidence
records are listed in wardrobe/review.md for you to confirm.

Resumable: re-running skips photos already represented in items.json (matched by
source filename), so an interrupted or partial run continues where it left off.

Requires ANTHROPIC_API_KEY (one vision call per photo).

    ./venv/bin/python -m wardrobe.ingest            # all of inbox/
    ./venv/bin/python -m wardrobe.ingest --limit 5  # first 5 only (sampling)
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
from pathlib import Path

from ai._llm import MODEL, available, client, text_of
from core.categories import categories_for
from core.profiles import DEFAULT_PROFILE, load_config, profile_dir

ROOT = Path(__file__).resolve().parents[1]
PROFILE = DEFAULT_PROFILE
_pdir = profile_dir(PROFILE)
INBOX = _pdir / "inbox"
IMAGES = _pdir / "images"
ITEMS = _pdir / "items.json"
SEED_BACKUP = _pdir / "items.seed.json"
REVIEW = _pdir / "review.md"
CATEGORIES = categories_for(load_config(PROFILE).get("categories", "menswear"))


def configure(profile):
    """Point the ingest at a profile's folders + category vocabulary."""
    global PROFILE, INBOX, IMAGES, ITEMS, SEED_BACKUP, REVIEW, CATEGORIES
    PROFILE = profile
    p = profile_dir(profile)
    INBOX, IMAGES = p / "inbox", p / "images"
    ITEMS, SEED_BACKUP, REVIEW = p / "items.json", p / "items.seed.json", p / "review.md"
    CATEGORIES = categories_for(load_config(profile).get("categories", "menswear"))
    GARMENT_SCHEMA["properties"]["category"]["enum"] = CATEGORIES

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MAX_EDGE = 1024

FORMALITY_LEVELS = ["athletic", "casual", "smart casual", "business", "formal"]
SEASONS = ["summer", "spring", "autumn", "winter", "transitional"]

GARMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Short human label, e.g. 'navy colorblock crewneck'"},
        "category": {
            "type": "string",
            "enum": CATEGORIES,
        },
        "subtype": {"type": "string", "description": "e.g. 'long-sleeve t-shirt', 'low-top sneakers'"},
        "brand": {"type": ["string", "null"], "description": "Only if a logo/wordmark is visible, else null"},
        "colors": {"type": "array", "items": {"type": "string"}, "description": "Dominant first"},
        "neutral": {"type": "boolean", "description": "True for black/white/grey/navy/beige/tan basics"},
        "pattern": {"type": "string", "enum": ["solid", "colorblock", "striped", "check", "graphic", "other"]},
        "sleeve": {"type": "string", "enum": ["long", "short", "sleeveless", "na"]},
        "material": {"type": "string", "description": "Best inference, e.g. 'cotton jersey', 'leather'"},
        "texture": {"type": "string", "description": "e.g. 'smooth knit', 'brushed fleece', 'mesh'"},
        "thickness": {"type": "string", "enum": ["thin", "medium", "thick"]},
        "warmth": {"type": "integer", "description": "1 (lightest) to 5 (warmest)"},
        "formality": {
            "type": "array",
            "items": {"type": "string", "enum": FORMALITY_LEVELS},
            "description": "EVERY setting it suits, e.g. ['casual','smart casual']",
        },
        "rain_ok": {"type": "boolean"},
        "season": {"type": "array", "items": {"type": "string", "enum": SEASONS}},
        "condition": {"type": "string", "enum": ["new", "good", "worn"]},
        "fit_notes": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": [
        "name", "category", "subtype", "brand", "colors", "neutral", "pattern",
        "sleeve", "material", "texture", "thickness", "warmth", "formality",
        "rain_ok", "season", "condition", "fit_notes", "confidence",
    ],
    "additionalProperties": False,
}

SYSTEM = (
    "You are an expert wardrobe cataloguer. You see ONE garment photographed on a "
    "floor, hanger, or body — often wrinkled or rotated. Identify the single main "
    "garment and describe it. Infer material, texture, and thickness from visual cues "
    "(sheen, weave, drape, ribbing). For 'formality', list EVERY setting the piece "
    "genuinely suits from athletic/casual/smart casual/business/formal — a plain black "
    "tee is both casual and smart casual. Mark 'neutral' true for black/white/grey/navy/"
    "beige/tan basics that pair with anything. Set 'brand' only if a logo or wordmark is "
    "clearly visible, otherwise null — never guess a brand. Use confidence 'medium' or "
    "'low' when fabric blend or thickness is uncertain."
)


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "item"


def encode_upright(path):
    """Return (base64_jpeg, jpeg_bytes) — EXIF-rotated upright, downscaled, re-encoded."""
    from PIL import Image, ImageOps

    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((MAX_EDGE, MAX_EDGE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    data = buf.getvalue()
    return base64.b64encode(data).decode("ascii"), data


def analyze(b64):
    resp = client(timeout=60).messages.create(
        model=MODEL,
        max_tokens=600,
        output_config={"format": {"type": "json_schema", "schema": GARMENT_SCHEMA}},
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": "Catalogue this garment."},
                ],
            }
        ],
    )
    return json.loads(text_of(resp))


def load_items():
    """Load items.json, backing up a demo seed (records without 'source') once."""
    if not ITEMS.exists():
        return []
    existing = json.loads(ITEMS.read_text())
    if existing and not any("source" in r for r in existing):
        if not SEED_BACKUP.exists():
            SEED_BACKUP.write_text(json.dumps(existing, indent=2) + "\n")
        return []
    return existing


def unique_id(base, taken):
    candidate = base
    n = 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def write_items(items):
    tmp = ITEMS.with_name("items.tmp.json")
    tmp.write_text(json.dumps(items, indent=2) + "\n")
    tmp.replace(ITEMS)


def write_review(items):
    flagged = [i for i in items if i.get("confidence") in {"medium", "low"}]
    lines = [
        "# Wardrobe review",
        "",
        f"{len(items)} item(s) catalogued, {len(flagged)} need a look "
        "(confidence medium/low — fabric or thickness inferred).",
        "",
    ]
    for i in flagged:
        lines.append(
            f"- **{i['name']}** (`{i['id']}`) — {i['confidence']} · "
            f"{i['material']}, {i['thickness']} · formality {', '.join(i['formality'])} · "
            f"`{i['image']}`"
        )
    lines.append("")
    lines.append("Correct any item by telling me its id and what's wrong; I update its record.")
    REVIEW.write_text("\n".join(lines) + "\n")


def ingest(limit=None):
    if not available():
        raise SystemExit("ANTHROPIC_API_KEY not set — vision ingest needs it. See SETUP.md step 1.")

    IMAGES.mkdir(parents=True, exist_ok=True)
    items = load_items()
    done_sources = {i.get("source") for i in items}
    taken_ids = {i["id"] for i in items}

    photos = sorted(p for p in INBOX.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED)
    photos = [p for p in photos if p.name not in done_sources]
    if limit is not None:
        photos = photos[:limit]

    print(f"{len(photos)} photo(s) to process ({len(items)} already catalogued).")
    for idx, path in enumerate(photos, 1):
        try:
            b64, jpeg = encode_upright(path)
            record = analyze(b64)
        except Exception as exc:
            print(f"  [{idx}/{len(photos)}] {path.name}: SKIPPED ({exc})")
            continue

        item_id = unique_id(slugify(record["name"]), taken_ids)
        taken_ids.add(item_id)
        image_rel = Path("profiles") / PROFILE / "images" / f"{item_id}.jpg"
        (ROOT / image_rel).write_bytes(jpeg)

        record.update({"id": item_id, "image": str(image_rel), "source": path.name, "learned": []})
        items.append(record)
        write_items(items)
        path.unlink()  # remove from inbox only after successful persist
        print(f"  [{idx}/{len(photos)}] {path.name} -> {item_id} ({record['confidence']})")

    write_review(items)
    print(f"Done. {len(items)} item(s) in {ITEMS}. Review: {REVIEW}")


def main():
    parser = argparse.ArgumentParser(description="Vision wardrobe ingest.")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N photos.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="Wardrobe profile to ingest into.")
    args = parser.parse_args()
    configure(args.profile)
    ingest(limit=args.limit)


if __name__ == "__main__":
    main()
