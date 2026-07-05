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
from core.profiles import load_config, profile_dir
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


def require_token(authorization: str = Header(default="")) -> str:
    """Verify the token and return the profile it is bound to."""
    token = authorization[7:] if authorization.startswith("Bearer ") else authorization
    prof = verify_token(token)
    if not prof:
        raise HTTPException(status_code=401, detail="locked")
    return prof


_EDITABLE = ("warmth", "polish", "comfort", "wear_frequency", "home_ok", "office_ok", "avoid_often")


def _wardrobe(prof):
    """Wardrobe with the wearer's saved metadata edits applied. On Vercel the
    filesystem is read-only, so edits live in KV (closet:<prof>:corr) — merge them here."""
    from webapp import kvstore

    items = load_wardrobe(profile=prof)
    corr = kvstore.get_json(f"closet:{prof}:corr") if kvstore.available() else None
    if corr:
        for item in items:
            fields = corr.get(item.get("id"))
            if fields:
                item.update(fields)
    return items


def _url_for_id(item_id, prof):
    """Transparent cutout served as a static CDN asset at /profiles/<who>/cutouts/."""
    if not item_id:
        return None
    return f"/profiles/{prof}/cutouts/{item_id}.png"


def _image_url(image, prof):
    return _url_for_id(Path(image).stem, prof) if image else None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/dashboard")
def dashboard():
    return FileResponse(STATIC / "dashboard.html")


@app.post("/api/unlock")
async def unlock(body: dict):
    prof = check_pin(body.get("pin", ""))
    if not prof:
        raise HTTPException(status_code=401, detail="wrong pin")
    try:
        menswear = load_config(prof).get("categories") == "menswear"
    except Exception:
        menswear = False
    return {
        "token": make_token(prof),
        "profile": prof,
        "name": prof.capitalize(),
        "menswear": menswear,
    }


@app.post("/api/outfit")
def outfit(body: dict, prof: str = Depends(require_token)):
    result = plan_outfit(prof, prefs=body.get("prefs") or {}, day=body.get("day") or {},
                         wardrobe=_wardrobe(prof))
    for piece in result.get("pieces", []):
        piece["url"] = _url_for_id(piece.get("id"), prof) or _image_url(piece.get("image"), prof)
    result["profile"] = prof
    return result


@app.get("/api/wardrobe")
def wardrobe(prof: str = Depends(require_token)):
    items = _wardrobe(prof)
    return [
        {
            "id": it.get("id"),
            "name": it.get("name"),
            "category": it.get("category"),
            "url": _url_for_id(it.get("id"), prof),
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
def update_wardrobe_item(item_id: str, body: dict, prof: str = Depends(require_token)):
    from webapp import kvstore

    fields = {k: body[k] for k in _EDITABLE if k in body}
    if kvstore.available():
        # Vercel FS is read-only; persist edits to KV so they stick and sync.
        corr = kvstore.get_json(f"closet:{prof}:corr") or {}
        corr[item_id] = {**corr.get(item_id, {}), **fields}
        kvstore.set_json(f"closet:{prof}:corr", corr)
        item = next((i for i in _wardrobe(prof) if i.get("id") == item_id), None)
    else:
        item = save_metadata_correction(item_id, body, profile=prof)
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


@app.get("/api/state")
def get_state(prof: str = Depends(require_token)):
    """Cross-device state (locked outfits + saved prefs) for this profile."""
    from webapp import kvstore

    if not kvstore.available():
        return {"synced": False}
    data = kvstore.get_json(f"closet:{prof}") or {}
    return {
        "synced": True,
        "locked": data.get("locked") or {},
        "prefs": data.get("prefs"),
        "occasions": data.get("occasions") or {},
    }


@app.post("/api/state")
def put_state(body: dict, prof: str = Depends(require_token)):
    from webapp import kvstore

    if not kvstore.available():
        return {"synced": False}
    payload = {
        "locked": body.get("locked") or {},
        "prefs": body.get("prefs"),
        "occasions": body.get("occasions") or {},
    }
    kvstore.set_json(f"closet:{prof}", payload)
    return {"synced": True}


@app.post("/api/anchors/check")
def check_anchors(body: dict, prof: str = Depends(require_token)):
    items = _wardrobe(prof)
    return {"warnings": anchor_warnings(items, body.get("anchors") or [])}


@app.get("/api/weather")
def weather(prof: str = Depends(require_token)):
    from connectors.weather import fetch_weather_for

    return fetch_weather_for(prof)


@app.get("/api/geocode")
def geocode_city(q: str = "", _: str = Depends(require_token)):
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
