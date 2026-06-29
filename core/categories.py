"""Per-profile garment category sets + flat-lay layout roles.

Menswear and womenswear differ (a dress is a complete base; skirts vs trousers).
The ingest schema's category enum and the flat-lay grouping both read from here.
"""
from __future__ import annotations

MENSWEAR = ["top", "midlayer", "outerwear", "bottom", "shoes", "accessory"]
WOMENSWEAR = [
    "top", "blouse", "knit", "cardigan", "outerwear", "dress", "skirt",
    "pants", "jeans", "shorts", "shoes", "bag", "accessory",
]

# Flat-lay grouping: which categories sit in the upper row vs the lower row.
TOP_ROW = {"outerwear", "midlayer", "top", "blouse", "knit", "cardigan", "dress"}
BOTTOM_ROW = {"bottom", "skirt", "pants", "jeans", "shorts", "shoes", "bag", "accessory"}


def categories_for(name):
    return {"menswear": MENSWEAR, "womenswear": WOMENSWEAR}.get(name, MENSWEAR)
