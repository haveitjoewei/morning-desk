"""Companion web app — PIN-gated, stateless API + static PWA for one profile.

Her preferences live in her browser and ride each /api/outfit request; the server
holds no per-user state. Garment images (cleaned + cutouts) are precomputed offline
and served as static files, so the runtime stays light enough for serverless.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.outfit import anchor_warnings, plan_outfit
from core.profiles import profile_dir
from wardrobe.catalog import load_wardrobe, save_metadata_correction
from webapp.auth import check_pin, make_token, verify_token

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
PROFILES_ROOT = Path(os.environ.get("MD_PROFILES_ROOT", str(ROOT / "profiles")))


def profile() -> str:
    return os.environ.get("WARDROBE_PROFILE", "evangeline")


app = FastAPI(title="Wardrobe Companion")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
# Cutouts ship as static CDN assets (kept out of the function so it stays under the
# 225MB size limit) and are served straight from the CDN at their own path. This mount
# makes local dev serve the same URLs; on Vercel the CDN answers first so it's unused.
if PROFILES_ROOT.exists():
    app.mount("/profiles", StaticFiles(directory=str(PROFILES_ROOT)), name="profiles")


def require_token(authorization: str = Header(default="")):
    token = authorization[7:] if authorization.startswith("Bearer ") else authorization
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="locked")
    return True


def _url_for_id(item_id):
    """Transparent cutout served as a static CDN asset at /profiles/<who>/cutouts/."""
    if not item_id:
        return None
    return f"/profiles/{profile()}/cutouts/{item_id}.png"


def _image_url(image):
    return _url_for_id(Path(image).stem) if image else None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/unlock")
async def unlock(body: dict):
    if not check_pin(body.get("pin", "")):
        raise HTTPException(status_code=401, detail="wrong pin")
    return {"token": make_token()}


@app.post("/api/outfit")
def outfit(body: dict, _=Depends(require_token)):
    result = plan_outfit(profile(), prefs=body.get("prefs") or {}, day=body.get("day") or {})
    for piece in result.get("pieces", []):
        piece["url"] = _url_for_id(piece.get("id")) or _image_url(piece.get("image"))
    return result


@app.get("/api/wardrobe")
def wardrobe(_=Depends(require_token)):
    items = load_wardrobe(profile=profile())
    return [
        {
            "id": it.get("id"),
            "name": it.get("name"),
            "category": it.get("category"),
            "url": _url_for_id(it.get("id")),
            "warmth": it.get("warmth"),
            "polish": it.get("polish"),
            "comfort": it.get("comfort"),
            "home_ok": it.get("home_ok"),
            "office_ok": it.get("office_ok"),
            "wear_frequency": it.get("wear_frequency"),
            "avoid_often": it.get("avoid_often"),
        }
        for it in items
    ]


@app.post("/api/wardrobe/{item_id}")
def update_wardrobe_item(item_id: str, body: dict, _=Depends(require_token)):
    item = save_metadata_correction(item_id, body, profile=profile())
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "category": item.get("category"),
        "warmth": item.get("warmth"),
        "polish": item.get("polish"),
        "comfort": item.get("comfort"),
        "home_ok": item.get("home_ok"),
        "office_ok": item.get("office_ok"),
        "wear_frequency": item.get("wear_frequency"),
        "avoid_often": item.get("avoid_often"),
    }


@app.post("/api/anchors/check")
def check_anchors(body: dict, _=Depends(require_token)):
    items = load_wardrobe(profile=profile())
    return {"warnings": anchor_warnings(items, body.get("anchors") or [])}


@app.get("/api/weather")
def weather(_=Depends(require_token)):
    from connectors.weather import fetch_weather_for

    return fetch_weather_for(profile())


@app.get("/api/geocode")
def geocode_city(q: str = "", _=Depends(require_token)):
    from connectors.weather import geocode

    result = geocode(q)
    if not result:
        raise HTTPException(status_code=404, detail="city not found")
    return result


@app.get("/img/{kind}/{name}")
def image(kind: str, name: str):
    if kind not in {"cutouts", "clean"} or "/" in name or ".." in name:
        raise HTTPException(status_code=404)
    folder = "cutouts" if kind == "cutouts" else "images_clean"
    path = profile_dir(profile()) / folder / name
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)
