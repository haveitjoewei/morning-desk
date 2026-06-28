"""Turn the messy wardrobe photos into clean product shots (Gemini image edit).

Image-to-image: each photo in wardrobe/images/ is sent to Gemini 2.5 Flash Image
with an edit instruction to present the SAME garment as a clean, de-wrinkled,
evenly-lit product shot on a seamless background. Originals are kept; cleaned
versions go to wardrobe/images_clean/<id>.jpg. Resumable (skips done ones).

Requires GEMINI_API_KEY (or GOOGLE_API_KEY). One image call per garment.

    ./venv/bin/python -m wardrobe.enhance_images            # all
    ./venv/bin/python -m wardrobe.enhance_images --limit 3  # sample first
"""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "wardrobe" / "images"
DST = ROOT / "wardrobe" / "images_clean"
MODEL = os.environ.get("MD_IMAGE_MODEL", "gemini-2.5-flash-image")

PROMPT = (
    "Re-photograph this exact garment as a clean e-commerce product shot. Present it "
    "neatly on a pure solid white (#FFFFFF) seamless background with NO drop shadow, "
    "gently steamed so it is smooth and wrinkle-free, evenly and softly lit, centered "
    "with even margins. Remove any hangers, clutter, floor, furniture, hands or people. "
    "Preserve the garment's exact colour, pattern, fabric texture, proportions, collar/"
    "sleeve/hem shape, and any logos or graphics precisely. Do not restyle, recolour, or "
    "change the garment in any way — only clean up the presentation. The flat white "
    "background must be uniform so the garment can be cleanly cut out later."
)


def _key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _client():
    from google import genai

    return genai.Client(api_key=_key())


def _enhance_one(client, image_bytes):
    from google.genai import types
    from PIL import Image

    image = Image.open(io.BytesIO(image_bytes))
    resp = client.models.generate_content(model=MODEL, contents=[PROMPT, image])
    for part in resp.candidates[0].content.parts:
        inline = getattr(part, "inline_data", None)
        if inline and inline.data:
            return inline.data
    raise RuntimeError("no image returned")


def enhance(limit=None):
    if not _key():
        raise SystemExit("GEMINI_API_KEY not set — image cleanup needs it. See SETUP.md.")
    DST.mkdir(parents=True, exist_ok=True)
    client = _client()

    photos = sorted(p for p in SRC.iterdir() if p.suffix.lower() == ".jpg")
    photos = [p for p in photos if not (DST / p.name).exists()]
    if limit is not None:
        photos = photos[:limit]

    print(f"{len(photos)} image(s) to clean up.")
    for index, path in enumerate(photos, 1):
        try:
            data = _enhance_one(client, path.read_bytes())
            (DST / path.name).write_bytes(data)
            print(f"  [{index}/{len(photos)}] {path.name} -> images_clean/{path.name}")
        except Exception as exc:
            print(f"  [{index}/{len(photos)}] {path.name}: SKIPPED ({exc})")
    print(f"Done. Cleaned images in {DST}")


def main():
    parser = argparse.ArgumentParser(description="Clean up wardrobe photos into product shots.")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N images.")
    args = parser.parse_args()
    enhance(limit=args.limit)


if __name__ == "__main__":
    main()
