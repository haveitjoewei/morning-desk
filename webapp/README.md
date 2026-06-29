# Your Closet — wardrobe companion app

A mobile-first, PIN-gated web app (installable PWA) that gives one person a daily
outfit from their own wardrobe, which they can tweak. Built on the same engine as
morning-desk, with isolated per-profile wardrobes (`profiles/<name>/`).

## What it does

- Shows today's outfit (her wardrobe) as a clean flat-lay with the weather + a
  stylist reason.
- Tweaks: occasion, warmer/lighter, **anchor a piece** (build around it), and a
  free-text wish ("something flowy", "wear the green cardigan").
- Standing preferences (runs cold, style notes, love/avoid colours) live in her
  browser and ride each request — the server is stateless.

## Run locally

```bash
set -a; source ~/.config/morning-desk/environment; set +a   # ANTHROPIC_API_KEY
export WARDROBE_PIN=1234 WARDROBE_SECRET=any-long-random WARDROBE_PROFILE=evangeline
./venv/bin/uvicorn webapp.app:app --port 8210
# open http://localhost:8210  (PIN: 1234)
```

## Deploy

See **[DEPLOY.md](DEPLOY.md)** — Railway/Fly (recommended, always-on), Vercel (free),
or a Cloudflare tunnel from your Mac. Same file covers env vars and how to swap in
her real clothes once scanned.

## Status

The current `profiles/evangeline` data is **placeholder** (Joseph's items remapped to
womenswear categories) so the app runs before her clothes are scanned. Replace per
DEPLOY.md → "Swapping in her real clothes".

## Architecture

`webapp/app.py` (FastAPI, stateless) → `core/outfit.plan_outfit(profile, prefs, day)`
→ shared engine (`ai/`, `connectors/`, `wardrobe/`). Auth in `webapp/auth.py` (HMAC
token from a shared PIN). Frontend in `webapp/static/` (vanilla JS + PWA).
