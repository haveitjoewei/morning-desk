"""Compose a full-outfit image by cutting garments out and stacking them.

Cutout uses rembg when available (clean subject masks); otherwise it flood-fills
the uniform white background of the cleaned product shots (preserves light pixels
inside the garment, unlike threshold keying). Pieces are stacked top-to-bottom by
category so the column reads like a laid-out outfit.

    ./venv/bin/python -m wardrobe.compose <id> <id> ...   # -> wardrobe/outfit_preview.png
"""
from __future__ import annotations

import sys
from pathlib import Path

from wardrobe.catalog import load_wardrobe, resolve_pieces

ROOT = Path(__file__).resolve().parents[1]
SEED = (255, 0, 255)  # sentinel to mark flood-filled background
ORDER = {"outerwear": 0, "midlayer": 1, "top": 2, "bottom": 3, "shoes": 4, "accessory": 5}

_REMBG_SESSION = None


def _cutout_rembg(img):
    global _REMBG_SESSION
    from rembg import new_session, remove

    if _REMBG_SESSION is None:
        _REMBG_SESSION = new_session("u2netp")
    return remove(img, session=_REMBG_SESSION).convert("RGBA")


def _cutout_floodfill(img, thresh=42):
    from PIL import Image, ImageChops, ImageDraw

    base = img.convert("RGB")
    w, h = base.size
    for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        ImageDraw.floodfill(base, corner, SEED, thresh=thresh)
    diff = ImageChops.difference(base, Image.new("RGB", base.size, SEED)).convert("L")
    alpha = diff.point(lambda v: 0 if v == 0 else 255)
    rgba = base.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def cutout(path):
    """RGBA garment with the background removed, cropped to content."""
    from PIL import Image

    img = Image.open(path).convert("RGB")
    try:
        rgba = _cutout_rembg(img)
    except Exception:
        rgba = _cutout_floodfill(img)
    bbox = rgba.getbbox()
    return rgba.crop(bbox) if bbox else rgba


def _ordered(pieces, items):
    cat = {i.get("name"): i.get("category", "") for i in items}
    return sorted(pieces, key=lambda p: ORDER.get(cat.get(p.get("name"), ""), 9))


def compose_outfit(pieces, items, out_path, cell=380, gap=24, pad=40, layout="column"):
    """Stack the outfit's pieces into one image. layout 'column' (tall, full-outfit
    card) or 'row' (wide, fits the dashboard WEAR panel). Returns out_path or None."""
    from PIL import Image

    cat_of = {i.get("name"): i.get("category", "") for i in items}
    cuts, cats = [], []
    for piece in _ordered(pieces, items):
        image = piece.get("image")
        if not image or not (ROOT / image).exists():
            continue
        img = cutout(ROOT / image)
        scale = min(cell / img.width, cell / img.height, 1.0)
        if scale < 1.0:
            img = img.resize((round(img.width * scale), round(img.height * scale)))
        cuts.append(img)
        cats.append(cat_of.get(piece.get("name"), ""))
    if not cuts:
        return None

    if layout == "flatlay":
        # Two staggered columns — tops on the left, bottoms+shoes on the right —
        # each overlapped and gently tilted: the curated stylist flat-lay look.
        angles = [-5, 4, -4, 5]

        def _rot(idxs):
            return [
                cuts[i].rotate(angles[k % len(angles)], expand=True, resample=Image.BICUBIC,
                               fillcolor=(0, 0, 0, 0))
                for k, i in enumerate(idxs)
            ]

        tops = [i for i, c in enumerate(cats) if c in {"outerwear", "midlayer", "top"}]
        bottoms = [i for i, c in enumerate(cats) if c in {"bottom", "shoes", "accessory"}]
        if not tops or not bottoms:  # fallback: split in half
            half = (len(cuts) + 1) // 2
            tops, bottoms = list(range(half)), list(range(half, len(cuts)))
        col1, col2 = _rot(tops), _rot(bottoms)

        overlap = 0.20

        def _col(imgs):
            ys, y = [], 0
            for k, im in enumerate(imgs):
                if k:
                    y = ys[-1] + int(imgs[k - 1].height * (1 - overlap))
                ys.append(y)
            w = max((im.width for im in imgs), default=0)
            h = (ys[-1] + imgs[-1].height) if imgs else 0
            return ys, w, h

        ys1, w1, h1 = _col(col1)
        ys2, w2, h2 = _col(col2)
        colgap = int(max(w1, w2) * 0.10)
        drop = int(max(h1, h2) * 0.12)  # stagger the right column downward
        width = pad * 2 + w1 + colgap + w2
        height = pad * 2 + max(h1, h2 + drop)
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        for k in reversed(range(len(col1))):
            im = col1[k]
            canvas.paste(im, (pad + (w1 - im.width) // 2, pad + ys1[k]), im)
        for k in reversed(range(len(col2))):
            im = col2[k]
            canvas.paste(im, (pad + w1 + colgap + (w2 - im.width) // 2, pad + drop + ys2[k]), im)
    elif layout == "stack":
        # Overlapped vertical column (cuts ordered top -> shoes): each piece sits
        # over the previous so the whole outfit reads as one layered look.
        overlap = 0.24
        ys, y = [], pad
        for index, img in enumerate(cuts):
            if index:
                y = ys[-1] + int(cuts[index - 1].height * (1 - overlap))
            ys.append(y)
        width = max(c.width for c in cuts) + pad * 2
        height = ys[-1] + cuts[-1].height + pad
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        # Paste lowest piece first so upper garments render in front at the overlaps.
        for index in reversed(range(len(cuts))):
            img = cuts[index]
            canvas.paste(img, ((width - img.width) // 2, ys[index]), img)
    elif layout == "row":
        height = cell + pad * 2
        width = pad * 2 + sum(c.width for c in cuts) + gap * (len(cuts) - 1)
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        x = pad
        for img in cuts:
            canvas.paste(img, (x, (height - img.height) // 2), img)
            x += img.width + gap
    else:
        width = cell + pad * 2
        height = pad * 2 + sum(c.height for c in cuts) + gap * (len(cuts) - 1)
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        y = pad
        for img in cuts:
            canvas.paste(img, ((width - img.width) // 2, y), img)
            y += img.height + gap

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, format="PNG")
    return out_path


def write_outfit_composite(content, root):
    """Build renderer/outfit.png from the content's outfit pieces. Skipped offline
    (tests); removes a stale composite when no garment images are available."""
    import os

    if os.environ.get("MD_OFFLINE") == "1":
        return None
    out = Path(root) / "renderer" / "outfit.png"
    pieces = (content.get("outfit") or {}).get("pieces", [])
    result = compose_outfit(pieces, load_wardrobe(), out, layout="flatlay")
    if result is None and out.exists():
        out.unlink()
    return result


def write_outfit_cutouts(content, root):
    """Save a transparent cutout PNG per outfit piece to renderer/cutouts/<id>.png
    for the HTML flat-lay to lay out with captions. Skipped offline (tests)."""
    import os

    if os.environ.get("MD_OFFLINE") == "1":
        return None
    out_dir = Path(root) / "renderer" / "cutouts"
    if out_dir.exists():
        for stale in out_dir.glob("*.png"):
            stale.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    pieces = (content.get("outfit") or {}).get("pieces", [])
    written = 0
    for piece in pieces:
        image = piece.get("image")
        if not image or not (ROOT / image).exists():
            continue
        cutout(ROOT / image).save(out_dir / f"{Path(image).stem}.png")
        written += 1
    return out_dir if written else None


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m wardrobe.compose <id> <id> ...")
    items = load_wardrobe()
    by_id = {i["id"]: i for i in items}
    names = [by_id[a]["name"] for a in sys.argv[1:] if a in by_id]
    pieces = resolve_pieces(names, items)
    out = compose_outfit(pieces, items, ROOT / "wardrobe" / "outfit_preview.png")
    print(f"Wrote {out}" if out else "No images to compose.")


if __name__ == "__main__":
    main()
