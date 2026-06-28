"""Compose a full-outfit image by cutting garments out and stacking them.

Cutout: the cleaned product shots sit on a uniform white background, so a
flood-fill from the corners removes the background while preserving white/light
pixels *inside* the garment (threshold keying would punch holes in a white
shirt). Good enough for a preview; swap in rembg for production-grade edges.

    ./venv/bin/python -m wardrobe.compose <id> <id> ...   # -> wardrobe/outfit_preview.png
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = (255, 0, 255)  # sentinel colour to mark background, then make transparent

# Visual top-to-bottom order so the column reads like a laid-out outfit.
ORDER = {"outerwear": 0, "midlayer": 1, "top": 2, "bottom": 3, "shoes": 4, "accessory": 5}


def _source(item_id):
    clean = ROOT / "wardrobe" / "images_clean" / f"{item_id}.jpg"
    original = ROOT / "wardrobe" / "images" / f"{item_id}.jpg"
    return clean if clean.exists() else (original if original.exists() else None)


def cutout(path, thresh=42):
    """Return an RGBA image with the white background flood-filled to transparent."""
    from PIL import Image, ImageChops, ImageDraw

    base = Image.open(path).convert("RGB")
    w, h = base.size
    for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        ImageDraw.floodfill(base, corner, SEED, thresh=thresh)
    # Alpha = 0 exactly where the flood-fill painted the sentinel, 255 elsewhere.
    diff = ImageChops.difference(base, Image.new("RGB", base.size, SEED)).convert("L")
    alpha = diff.point(lambda v: 0 if v == 0 else 255)
    rgba = base.convert("RGBA")
    rgba.putalpha(alpha)
    bbox = rgba.getbbox()
    return rgba.crop(bbox) if bbox else rgba


def compose(item_ids, out_path=None, cell=380, gap=24, pad=40):
    from PIL import Image

    out_path = Path(out_path) if out_path else ROOT / "wardrobe" / "outfit_preview.png"
    cuts = []
    for item_id in item_ids:
        src = _source(item_id)
        if not src:
            print(f"  (no image for {item_id}, skipping)")
            continue
        img = cutout(src)
        scale = min(cell / img.width, cell / img.height, 1.0)
        if scale < 1.0:
            img = img.resize((round(img.width * scale), round(img.height * scale)))
        cuts.append(img)

    if not cuts:
        raise SystemExit("No garment images available to compose.")

    width = cell + pad * 2
    height = pad * 2 + sum(c.height for c in cuts) + gap * (len(cuts) - 1)
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    y = pad
    for img in cuts:
        x = (width - img.width) // 2
        canvas.paste(img, (x, y), img)
        y += img.height + gap

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, format="PNG")
    print(f"Wrote {out_path} ({len(cuts)} pieces)")
    return out_path


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m wardrobe.compose <id> <id> ...")
    compose(sys.argv[1:])


if __name__ == "__main__":
    main()
