# Wardrobe Companion App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split morning-desk's outfit engine into a profile-aware core, give Evangeline her own isolated wardrobe + preferences, and ship a PIN-gated, mobile-first PWA (hosted on Vercel free) that serves her a daily outfit she can tweak — as a birthday gift due Thursday 2026-07-02.

**Architecture:** One shared, profile-aware engine in this repo. Wardrobe data lives under `profiles/<name>/`. morning-desk uses `joseph` (unchanged); a new stateless `webapp/` serves `evangeline`. Her preferences live in her browser (localStorage) and ride each request; cutouts are precomputed offline so the runtime stays light enough for serverless.

**Tech Stack:** Python 3.12, existing deps (anthropic, Pillow, PyYAML); FastAPI for the web app; vanilla HTML/CSS/JS frontend + PWA (manifest + service worker); Vercel Python serverless for hosting. rembg/PIL heavy ops only run offline (ingest), never at request time.

**Spec:** `docs/superpowers/specs/2026-06-29-wardrobe-companion-app-design.md`

---

## File Structure

**New — core profile support**
- `core/profiles.py` — profile path resolution + per-profile config (category set, location, default prefs).
- `profiles/joseph/` — moved from current `wardrobe/`: `items.json`, `images_clean/`, `cutouts/`, plus `prefs.json`, `config.json`.
- `profiles/evangeline/` — her `items.json`, `images_clean/`, `cutouts/`, `prefs.json`, `config.json`, `inbox/`.

**Modified — engine becomes profile-aware (default `joseph`, so morning-desk is unaffected)**
- `wardrobe/catalog.py` — `load_wardrobe(profile=...)`, `_piece_image(item, profile)`, `resolve_pieces(..., profile)`.
- `wardrobe/ingest.py`, `wardrobe/enhance_images.py`, `wardrobe/fix_orientation.py`, `wardrobe/compose.py` — take `--profile`.
- `wardrobe/outfit_plan.py` — plan keyed by profile.
- `ai/generate_outfit.py` — accept a `request` (prefs + day overrides); build the stylist prompt from it; enforce anchor.

**New — style request + womenswear**
- `ai/style_request.py` — `build_request(prefs, day)` → structured weights + prompt fragments; anchor validation.
- `core/categories.py` — per-profile category sets (menswear / womenswear) + layering roles.

**New — web app**
- `webapp/__init__.py`
- `webapp/app.py` — FastAPI app + routes.
- `webapp/auth.py` — PIN → HMAC token; verify.
- `webapp/static/index.html`, `app.js`, `style.css`, `manifest.json`, `service-worker.js`, `icon-192.png`, `icon-512.png`
- `api/index.py` — Vercel ASGI entry exporting `webapp.app:app`.
- `vercel.json` — build/routes config.
- `tests/test_webapp.py`, `tests/test_style_request.py`, `tests/test_profiles.py`

---

## Phase 1 — Profile-aware core (morning-desk keeps working)

### Task 1: Profile resolution module

**Files:**
- Create: `core/__init__.py` (empty), `core/profiles.py`
- Test: `tests/test_profiles.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_profiles.py
import json
from core.profiles import profile_dir, load_config, DEFAULT_PROFILE

def test_default_profile_is_joseph():
    assert DEFAULT_PROFILE == "joseph"

def test_profile_dir_points_under_profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    assert profile_dir("evangeline") == tmp_path / "evangeline"

def test_load_config_returns_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    cfg = load_config("evangeline")
    assert "categories" in cfg and "location" in cfg
```

- [ ] **Step 2: Run test, verify it fails** — `./venv/bin/python -m pytest tests/test_profiles.py -q` → FAIL (no module).

- [ ] **Step 3: Implement**

```python
# core/profiles.py
from __future__ import annotations
import json
import os
from pathlib import Path

DEFAULT_PROFILE = "joseph"
_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CONFIG = {
    "location": {"latitude": -33.8688, "longitude": 151.2093,
                 "timezone": "Australia/Sydney", "label": "Sydney"},
    "categories": "menswear",
}

def profiles_root() -> Path:
    return Path(os.environ.get("MD_PROFILES_ROOT", _ROOT / "profiles"))

def profile_dir(name: str) -> Path:
    return profiles_root() / name

def load_config(name: str) -> dict:
    path = profile_dir(name) / "config.json"
    cfg = dict(DEFAULT_CONFIG)
    if path.exists():
        cfg.update(json.loads(path.read_text()))
    return cfg

def items_path(name: str) -> Path:
    return profile_dir(name) / "items.json"
```

- [ ] **Step 4: Run test, verify PASS.**
- [ ] **Step 5: Commit** — `git add core tests/test_profiles.py && git commit -m "feat(core): profile resolution"`

### Task 2: Move Joseph's data into a profile

**Files:** move `wardrobe/items.json` → `profiles/joseph/items.json`; `wardrobe/images_clean/` → `profiles/joseph/images_clean/`; `wardrobe/cutouts/` (gitignored, regenerated). Add `profiles/joseph/config.json` (`{"categories":"menswear","location":{...Sydney}}`) and `profiles/joseph/prefs.json` (`{}`).

- [ ] **Step 1:** `mkdir -p profiles/joseph && git mv wardrobe/items.json profiles/joseph/items.json`
- [ ] **Step 2:** `mkdir -p profiles/joseph/images_clean && git mv wardrobe/images_clean/* profiles/joseph/images_clean/ 2>/dev/null; true` (images_clean is gitignored — also `mv` on disk). Move the real files on disk: `mv wardrobe/images/ profiles/joseph/images/` and `mv wardrobe/images_clean profiles/joseph/images_clean`.
- [ ] **Step 3:** Write `profiles/joseph/config.json` and `prefs.json` (content above). Update `.gitignore`: `profiles/*/images/`, `profiles/*/images_clean/`, `profiles/*/cutouts/`, `profiles/*/inbox/`.
- [ ] **Step 4: Commit** — `git add -A && git commit -m "refactor: move joseph wardrobe into profiles/joseph"`

### Task 3: Make catalog profile-aware

**Files:** Modify `wardrobe/catalog.py`. Test: `tests/test_profiles.py` (extend).

- [ ] **Step 1: Failing test**

```python
def test_load_wardrobe_reads_profile_items(tmp_path, monkeypatch):
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    d = tmp_path / "eve"; d.mkdir()
    (d / "items.json").write_text('[{"name":"Red Dress","category":"dress","image":"profiles/eve/images/red.jpg"}]')
    from wardrobe.catalog import load_wardrobe
    items = load_wardrobe(profile="eve")
    assert items[0]["name"] == "Red Dress"
```

- [ ] **Step 2: Run → FAIL** (load_wardrobe has no profile arg).
- [ ] **Step 3: Implement** — change `load_wardrobe(path=None, corrections_path=None, profile=DEFAULT_PROFILE)`: when `path is None`, use `core.profiles.items_path(profile)`. Update `_piece_image` to accept a profile and resolve images under `profile_dir(profile)`. Update `resolve_pieces(names, items, profile=DEFAULT_PROFILE)` to pass profile to `_piece_image` and keep `category`. Keep all existing callers working via the default.
- [ ] **Step 4: Run full suite** — `./venv/bin/python -m pytest tests/ -q` → all PASS (morning-desk default path unchanged).
- [ ] **Step 5: Commit** — `git commit -am "refactor(catalog): profile-aware load/resolve"`

### Task 4: Profile-thread the wardrobe CLIs + outfit plan

**Files:** Modify `wardrobe/ingest.py`, `enhance_images.py`, `fix_orientation.py`, `compose.py`, `outfit_plan.py`.

- [ ] **Step 1:** Add `--profile` (default `joseph`) argparse to ingest/enhance/fix_orientation/compose; derive `inbox/`, `images_clean/`, `cutouts/`, `items.json` paths from `core.profiles.profile_dir(profile)`. `compose.write_outfit_cutouts(content, root, profile=...)` writes to `profiles/<profile>/cutouts/` and resolves piece images by profile.
- [ ] **Step 2:** `outfit_plan`: key entries by profile — store `{profile: {date: outfit}}` or use `MD_OUTFIT_PLAN` path per profile. Add `profile` param to `planned_outfit`.
- [ ] **Step 3:** Update `orchestrator/run_morning_job.py` + `run_evening_job.py` to pass `profile="joseph"` explicitly to `load_wardrobe`, `resolve_pieces`, `planned_outfit`.
- [ ] **Step 4: Run suite + a live `scripts.morning`** → identical morning-desk output. PASS.
- [ ] **Step 5: Commit** — `git commit -am "refactor: thread profile through wardrobe tools + jobs"`

---

## Phase 2 — Style request (tweaks) in the engine

### Task 5: build_request — map prefs + day-overrides to engine inputs

**Files:** Create `ai/style_request.py`. Test: `tests/test_style_request.py`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_style_request.py
from ai.style_request import build_request, effective_high

def test_cold_and_warmer_lower_the_effective_temperature():
    prefs = {"runs_cold": True}
    day = {"temp_nudge": "warmer"}
    # runs_cold subtracts 3, warmer subtracts another 2 -> dresses for 5C cooler
    assert effective_high(18, prefs, day) == 13

def test_lighter_raises_effective_temperature():
    assert effective_high(18, {}, {"temp_nudge": "lighter"}) == 21

def test_request_carries_anchor_and_wish_and_occasion():
    r = build_request({"style_notes": "soft neutrals", "love_colors": ["sage"]},
                      {"occasion": "going out", "anchor": "green-cardigan", "wish": "something flowy"})
    assert r["anchor"] == "green-cardigan"
    assert "going out" in r["formality_hint"]
    assert "something flowy" in r["instructions"]
    assert "soft neutrals" in r["instructions"]
    assert "sage" in r["instructions"]
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**

```python
# ai/style_request.py
from __future__ import annotations

OCCASION_FORMALITY = {
    "casual": "casual", "cozy home": "casual", "work": "smart casual",
    "dressy": "smart casual", "going out": "smart casual",
}

def effective_high(high, prefs, day):
    high = high if isinstance(high, (int, float)) else 18
    if prefs.get("runs_cold"):
        high -= 3
    nudge = (day or {}).get("temp_nudge")
    if nudge == "warmer":
        high -= 2
    elif nudge == "lighter":
        high += 3
    return round(high)

def build_request(prefs, day):
    prefs, day = prefs or {}, day or {}
    bits = []
    if prefs.get("style_notes"):
        bits.append(f"Personal style: {prefs['style_notes']}.")
    if prefs.get("love_colors"):
        bits.append(f"Favours these colours: {', '.join(prefs['love_colors'])}.")
    if prefs.get("avoid_colors"):
        bits.append(f"Avoid these colours: {', '.join(prefs['avoid_colors'])}.")
    if prefs.get("runs_cold"):
        bits.append("Runs cold — prefer thicker layers and an extra layer.")
    if day.get("wish"):
        bits.append(f"Today she asked for: {day['wish']}.")
    occasion = (day.get("occasion") or "casual").lower()
    return {
        "anchor": day.get("anchor"),
        "formality_hint": OCCASION_FORMALITY.get(occasion, "casual"),
        "occasion": occasion,
        "instructions": " ".join(bits),
        "runs_cold": bool(prefs.get("runs_cold")),
    }
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `git add ai/style_request.py tests/test_style_request.py && git commit -m "feat(ai): style request from prefs + day overrides"`

### Task 6: Wire request into generate_outfit (incl. anchor enforcement)

**Files:** Modify `ai/generate_outfit.py`. Test: extend `tests/test_style_request.py` with a fallback test (offline).

- [ ] **Step 1: Failing test (offline anchor in fallback)**

```python
def test_fallback_outfit_includes_anchor_item():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 11}
    wardrobe = [
        {"name": "green cardigan", "category": "cardigan", "formality": ["casual","smart casual"]},
        {"name": "white tee", "category": "top", "formality": ["casual"]},
        {"name": "blue jeans", "category": "bottom", "formality": ["casual"]},
        {"name": "white sneakers", "category": "shoes", "formality": ["casual"]},
    ]
    out = generate_outfit(weather, wardrobe, calendar=[], context={},
                          request={"anchor": "green cardigan", "instructions": "", "formality_hint": "casual"})
    assert "green cardigan" in out["items"]
```

- [ ] **Step 2: Run → FAIL** (no `request` param / no anchor logic).
- [ ] **Step 3: Implement** — add `request=None` to `generate_outfit` and `fallback_outfit`. In the fallback: if `request["anchor"]` matches a wardrobe item name, ensure it's in `items` (prepend, dedupe, keep ≤5). Use `effective_high(weather["high"], ...)` for temperature_note (import from `ai.style_request`). In the Claude path: pass `request` in the JSON context and append `request["instructions"]` + an explicit "You MUST include this exact item: <anchor>" line to the system prompt when an anchor is set; after generation, if anchor missing from items, fall back. Keep `context` working (no behaviour change when `request` is None).
- [ ] **Step 4: Run full suite** → PASS (existing outfit tests unaffected).
- [ ] **Step 5: Commit** — `git commit -am "feat(ai): generate_outfit honours style request + anchor"`

### Task 7: A profile-aware on-demand outfit function

**Files:** Create `core/outfit.py` (thin orchestration for the web app). Test: `tests/test_style_request.py`.

- [ ] **Step 1: Failing test (offline)**

```python
def test_plan_outfit_for_profile_returns_pieces(tmp_path, monkeypatch):
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    monkeypatch.setenv("MD_OFFLINE", "1")
    d = tmp_path / "eve"; (d).mkdir()
    (d/"items.json").write_text('[{"name":"Red Dress","category":"dress","image":"profiles/eve/images_clean/red.jpg","formality":["smart casual"],"warmth":2}]')
    (d/"config.json").write_text('{"categories":"womenswear","location":{"latitude":-33.8,"longitude":151.2,"timezone":"Australia/Sydney"}}')
    from core.outfit import plan_outfit
    result = plan_outfit("eve", prefs={}, day={"occasion":"dressy"})
    assert "headline" in result and "pieces" in result
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — `plan_outfit(profile, prefs, day)`:
  1. `weather = fetch_weather_for(profile)` (reads `config.location`; offline → fallback).
  2. `wardrobe = load_wardrobe(profile=profile)`.
  3. `request = build_request(prefs, day)`.
  4. `outfit = generate_outfit(weather, wardrobe, calendar=[], context={"intent": request["occasion"]}, request=request)`.
  5. `outfit["pieces"] = resolve_pieces(outfit["items"], wardrobe, profile=profile)`.
  6. return `{**outfit, "weather": weather}`. (No outfit_plan caching here — her app is on-demand.)
  Add `fetch_weather_for(profile)` in `connectors/weather.py` taking a location dict (refactor `fetch_weather` to delegate).
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat(core): plan_outfit on-demand per profile"`

---

## Phase 3 — Her profile data (womenswear)

### Task 8: Womenswear category set + ingest variant

**Files:** Create `core/categories.py`. Modify `wardrobe/ingest.py` (category enum from profile config).

- [ ] **Step 1:** `core/categories.py`:

```python
MENSWEAR = ["top","midlayer","outerwear","bottom","shoes","accessory"]
WOMENSWEAR = ["top","blouse","knit","cardigan","outerwear","dress","skirt",
              "pants","jeans","shorts","shoes","bag","accessory"]
# Layout roles for the flat-lay (which row / size bucket each category sits in)
TOP_ROW = {"outerwear","midlayer","top","blouse","knit","cardigan","dress"}
BOTTOM_ROW = {"bottom","skirt","pants","jeans","shorts","shoes","bag","accessory"}

def categories_for(name):
    return {"menswear": MENSWEAR, "womenswear": WOMENSWEAR}.get(name, MENSWEAR)
```

- [ ] **Step 2:** `ingest.py`: read `core.profiles.load_config(profile)["categories"]`, build the `category` enum in `GARMENT_SCHEMA` from `categories_for(...)`. Add a womenswear note to the system prompt when womenswear (e.g. "a dress is a complete base; identify skirts vs trousers; note heel height for shoes").
- [ ] **Step 3:** Extend `html_render`/`compose` category→row/size maps to include womenswear categories (use `core.categories.TOP_ROW`/`BOTTOM_ROW`; size: dress like top-tall, bag/accessory small).
- [ ] **Step 4: Run suite** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: womenswear categories + ingest variant"`

### Task 9: Build Evangeline's catalog (manual, gated on her photos)

**Files:** `profiles/evangeline/{config.json, prefs.json, inbox/}`.

- [ ] **Step 1:** Create `profiles/evangeline/config.json` (`{"categories":"womenswear","location":{...her city}}`) and `prefs.json` (`{"runs_cold": true}` as a sensible default).
- [ ] **Step 2:** Joseph drops her scanned photos into `profiles/evangeline/inbox/`.
- [ ] **Step 3:** Run, in order (needs keys):
  - `./venv/bin/python -m wardrobe.ingest --profile evangeline`
  - `./venv/bin/python -m wardrobe.enhance_images --profile evangeline`
  - `./venv/bin/python -m wardrobe.fix_orientation --profile evangeline`
- [ ] **Step 4:** Spot-check `profiles/evangeline/items.json` + a few `images_clean/`; correct via `wardrobe.correct --profile evangeline ...`.
- [ ] **Step 5: Commit** — `git add profiles/evangeline/items.json profiles/evangeline/config.json prefs.json && git commit -m "data: evangeline catalog"` (images gitignored).

---

## Phase 4 — Web app (FastAPI + PWA)

### Task 10: PIN auth (HMAC token)

**Files:** Create `webapp/__init__.py`, `webapp/auth.py`. Test: `tests/test_webapp.py`.

- [ ] **Step 1: Failing test**

```python
# tests/test_webapp.py
import os
from webapp.auth import make_token, verify_token, check_pin

def test_pin_roundtrip(monkeypatch):
    monkeypatch.setenv("WARDROBE_PIN", "2468")
    monkeypatch.setenv("WARDROBE_SECRET", "s3cret")
    assert check_pin("2468")
    assert not check_pin("0000")
    tok = make_token()
    assert verify_token(tok)
    assert not verify_token(tok + "x")
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**

```python
# webapp/auth.py
import hashlib, hmac, os, time

def _secret() -> bytes:
    return os.environ.get("WARDROBE_SECRET", "dev-secret").encode()

def check_pin(pin: str) -> bool:
    return hmac.compare_digest(str(pin), os.environ.get("WARDROBE_PIN", ""))

def make_token(ttl_days: int = 30) -> str:
    exp = str(int(time.time()) + ttl_days * 86400)
    sig = hmac.new(_secret(), exp.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"

def verify_token(token: str) -> bool:
    try:
        exp, sig = token.split(".", 1)
        good = hmac.new(_secret(), exp.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, good) and int(exp) > time.time()
    except Exception:
        return False
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `git add webapp tests/test_webapp.py && git commit -m "feat(webapp): PIN HMAC auth"`

### Task 11: FastAPI app + routes

**Files:** Create `webapp/app.py`. Test: extend `tests/test_webapp.py` (use `fastapi.testclient`).

- [ ] **Step 1:** `./venv/bin/pip install fastapi 'uvicorn[standard]' httpx` and add to `requirements.txt`.
- [ ] **Step 2: Failing test**

```python
def test_unlock_and_outfit(monkeypatch, tmp_path):
    monkeypatch.setenv("WARDROBE_PIN", "2468")
    monkeypatch.setenv("WARDROBE_SECRET", "s")
    monkeypatch.setenv("MD_OFFLINE", "1")
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    monkeypatch.setenv("WARDROBE_PROFILE", "eve")
    d = tmp_path/"eve"; d.mkdir()
    (d/"items.json").write_text('[{"name":"Red Dress","category":"dress","image":"x.jpg","formality":["smart casual"],"warmth":2}]')
    (d/"config.json").write_text('{"categories":"womenswear","location":{"latitude":-33.8,"longitude":151.2,"timezone":"Australia/Sydney"}}')
    from fastapi.testclient import TestClient
    from webapp.app import app
    c = TestClient(app)
    assert c.post("/api/unlock", json={"pin":"0000"}).status_code == 401
    tok = c.post("/api/unlock", json={"pin":"2468"}).json()["token"]
    r = c.post("/api/outfit", headers={"Authorization": f"Bearer {tok}"},
               json={"prefs":{}, "day":{"occasion":"dressy"}})
    assert r.status_code == 200 and "headline" in r.json()
    assert c.post("/api/outfit", json={"prefs":{},"day":{}}).status_code == 401
```

- [ ] **Step 3: Implement** — `webapp/app.py`:
  - `app = FastAPI()`, mount `webapp/static` at `/static`, and serve `profiles/<profile>/images_clean` and `cutouts` at `/img/...` (read profile from `WARDROBE_PROFILE`, default `evangeline`).
  - Dependency `require_token` (reads `Authorization: Bearer`, calls `verify_token`, else 401).
  - `POST /api/unlock {pin}` → `check_pin` → `{token}` or 401.
  - `POST /api/outfit {prefs, day}` (auth) → `core.outfit.plan_outfit(profile, prefs, day)`; map each piece image to `/img/cutouts/<id>.png` (or `/img/clean/<id>.jpg`) URL; return outfit JSON.
  - `GET /api/wardrobe` (auth) → `[{id,name,category,thumb_url}]` for the anchor picker.
  - `GET /api/weather` (auth) → current weather for the profile.
  - `GET /` → serve `static/index.html`.
  - On `plan_outfit`, generate cutouts on demand only if missing (offline/test: skip).
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat(webapp): FastAPI routes (unlock, outfit, wardrobe, weather)"`

### Task 12: Frontend (mobile-first) + PWA

**Files:** Create `webapp/static/{index.html, app.js, style.css, manifest.json, service-worker.js, icon-192.png, icon-512.png}`.

- [ ] **Step 1: `index.html`** — semantic shell: lock screen (PIN input), main screen (weather line, outfit flat-lay container `#outfit`, headline, reason), tweak bar (occasion `<select>`, warmer/lighter buttons, "Anchor a piece" button → opens `#wardrobe-grid` modal, free-text `#wish`, Regenerate), settings drawer (runs-cold toggle, style notes, love/avoid colors). Link `manifest.json`, theme-color meta, apple-touch-icon. Mobile viewport meta.
- [ ] **Step 2: `app.js`** — vanilla JS:
  - `state.prefs` loaded from `localStorage["wardrobe.prefs"]`; `state.token` from `localStorage["wardrobe.token"]`.
  - `unlock(pin)` → POST `/api/unlock`; store token.
  - `fetchOutfit()` → POST `/api/outfit` with `{prefs: state.prefs, day: currentDay()}`; render flat-lay (reuse the per-category sizing from the dashboard: tops row / bottoms+shoes row, captions, cutout PNGs from returned URLs).
  - `openAnchorPicker()` → GET `/api/wardrobe`; grid of thumbnails; selecting sets `day.anchor` and refetches.
  - settings save → write `state.prefs` to localStorage.
  - Register `service-worker.js`.
- [ ] **Step 3: `style.css`** — reuse the dashboard's visual language (serif headline, mono labels, flat-lay sizing per category, neutral palette), tuned for a phone (single column, large tap targets).
- [ ] **Step 4: `manifest.json`** (`name`, `short_name`, `display: standalone`, `theme_color`, `background_color`, icons 192/512) and `service-worker.js` (cache the shell: `/`, `/static/*`; network-first for `/api/*`). Generate simple icons (a wardrobe/hanger glyph on the brand color).
- [ ] **Step 5: Manual check** — `WARDROBE_PROFILE=evangeline ./venv/bin/python -m uvicorn webapp.app:app --port 8200`, open on phone (same wifi) or via screenshot: unlock, see outfit, tweak occasion, anchor a piece, type a wish, regenerate; "Add to Home Screen" shows icon + standalone.
- [ ] **Step 6: Commit** — `git add webapp/static && git commit -m "feat(webapp): mobile PWA frontend"`

---

## Phase 5 — Deploy to Vercel

### Task 13: Vercel serverless packaging

**Files:** Create `api/index.py`, `vercel.json`, `requirements-web.txt` (runtime-only deps: `fastapi`, `mangum` or Vercel ASGI, `anthropic`, `pillow` — NOT rembg/onnxruntime).

- [ ] **Step 1:** `api/index.py` exports the ASGI app for Vercel's Python runtime:

```python
# api/index.py
from webapp.app import app  # Vercel Python serverless serves this ASGI app
```

- [ ] **Step 2:** `vercel.json` — route all paths to the Python function; include `profiles/evangeline/images_clean`, `cutouts`, and `webapp/static` as static/included files; set max duration 10s. Configure `WARDROBE_PROFILE=evangeline`.
- [ ] **Step 3:** Precompute her cutouts locally (`wardrobe.compose`/`write_outfit_cutouts` is offline) and commit them into the deploy (override the gitignore for `profiles/evangeline/cutouts/` and `images_clean/` so they ship — these are needed at runtime and rembg is NOT in the deploy).
- [ ] **Step 4:** Set Vercel env vars: `ANTHROPIC_API_KEY`, `WARDROBE_PIN`, `WARDROBE_SECRET`, `WARDROBE_PROFILE`, her `MD_TZ`/location (or rely on profile config). Deploy: `vercel --prod`.
- [ ] **Step 5:** Smoke test the live URL on a phone: unlock, outfit, tweak, anchor, regenerate, install PWA. Confirm function stays under 10s and images load.
- [ ] **Step 6: Commit** — `git add api vercel.json requirements-web.txt && git commit -m "chore(deploy): vercel serverless packaging"`

### Task 14: Final pass + gift readiness

- [ ] **Step 1:** Full suite green: `./venv/bin/python -m pytest tests/ -q`.
- [ ] **Step 2:** Confirm morning-desk still works end-to-end (his profile): `./venv/bin/python -m scripts.morning` renders his dashboard unchanged.
- [ ] **Step 3:** Set her PIN to something memorable; write a tiny "how to use" note for her (open link → add to home screen → enter PIN).
- [ ] **Step 4:** Seed sensible defaults in `profiles/evangeline/prefs.json` (`runs_cold: true`, style notes in her voice).
- [ ] **Step 5: Commit/tag** — `git commit -am "chore: gift readiness" && git tag wardrobe-app-v1`.

---

## Self-Review

- **Spec coverage:** v1 scope (daily outfit + tweaks) → Tasks 5–7, 11–12. Profiles/isolation → Tasks 1–4, 9. Tweaks (cold/occasion/anchor/wish/temp + free-text) → Tasks 5–6, 12. Womenswear → Task 8. Stateless prefs (localStorage) → Task 12. PIN → Tasks 10–11. PWA → Task 12. Vercel → Task 13. Data prep → Task 9. All covered.
- **Out-of-scope respected:** no favorites/history, no in-app wardrobe editing, no accounts, no cross-device sync — none added.
- **Type consistency:** `build_request` returns `{anchor, formality_hint, occasion, instructions, runs_cold}`; consumed identically in Tasks 6–7 and the `/api/outfit` route. `plan_outfit(profile, prefs, day)` signature consistent across Tasks 7, 11. `make_token/verify_token/check_pin` consistent across Tasks 10–11.
- **Risk cut-lines:** anchor-by-name ships before the visual picker if time-tight (Task 12 Step 2 works with a typed name too); Vercel → Railway/Fly/Cloudflare-tunnel fallback (Task 13 / spec §8).
