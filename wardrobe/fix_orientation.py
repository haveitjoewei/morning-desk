"""Detect and correct wrongly-rotated cleaned garment images (vision pass).

Gemini's cleanup occasionally lays a garment sideways/upside-down. This asks the
model for the clockwise rotation needed to make each garment upright (collar/
waist at top, shoes grounded) and applies it in place on wardrobe/images_clean/.
Idempotent: a corrected image returns 0 on re-run. Requires ANTHROPIC_API_KEY.

    ./venv/bin/python -m wardrobe.fix_orientation            # all cleaned images
    ./venv/bin/python -m wardrobe.fix_orientation --limit 5  # sample
"""
from __future__ import annotations

import argparse
import base64
import io
from pathlib import Path

from ai._llm import MODEL, available, client, text_of

CLEAN = Path(__file__).resolve().parents[1] / "wardrobe" / "images_clean"

SYSTEM = (
    "You see one clothing item photographed as a product shot on white. Reply with the "
    "rotation in degrees CLOCKWISE needed to make it upright as normally displayed: a top/"
    "jacket with the collar/neckline at the top, trousers with the waistband at the top, "
    "shoes sitting flat on their soles. If it is already upright, the answer is 0."
)

SCHEMA = {
    "type": "object",
    "properties": {"rotation": {"type": "integer", "enum": [0, 90, 180, 270]}},
    "required": ["rotation"],
    "additionalProperties": False,
}

# Clockwise degrees -> lossless PIL transpose.
_TRANSPOSE = {90: 4, 180: 3, 270: 2}  # ROTATE_270, ROTATE_180, ROTATE_90


def _b64(path, edge=512):
    from PIL import Image

    img = Image.open(path).convert("RGB")
    img.thumbnail((edge, edge))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _detect(b64):
    resp = client(timeout=60).messages.create(
        model=MODEL,
        max_tokens=50,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": "Rotation to make this upright?"},
            ],
        }],
    )
    import json

    return int(json.loads(text_of(resp)).get("rotation", 0))


def fix(limit=None):
    if not available():
        raise SystemExit("ANTHROPIC_API_KEY not set — orientation fix needs it.")
    from PIL import Image

    photos = sorted(CLEAN.glob("*.jpg"))
    if limit is not None:
        photos = photos[:limit]

    fixed = 0
    for index, path in enumerate(photos, 1):
        try:
            rotation = _detect(_b64(path))
        except Exception as exc:
            print(f"  [{index}/{len(photos)}] {path.name}: SKIPPED ({exc})")
            continue
        if rotation in _TRANSPOSE:
            img = Image.open(path).convert("RGB").transpose(_TRANSPOSE[rotation])
            img.save(path, format="JPEG", quality=88)
            fixed += 1
            print(f"  [{index}/{len(photos)}] {path.name}: rotated {rotation}deg CW")
    print(f"Done. Corrected {fixed}/{len(photos)} image(s).")


def main():
    parser = argparse.ArgumentParser(description="Fix wrongly-rotated cleaned wardrobe images.")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    fix(limit=args.limit)


if __name__ == "__main__":
    main()
