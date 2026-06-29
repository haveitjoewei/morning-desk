# Deploying "Your Closet" (the wardrobe companion app)

The app is **stateless**: her wardrobe images ship with the deploy, her preferences
live in her browser, and each request just calls Claude. Runtime deps are tiny
(`fastapi`, `anthropic`) — see `requirements-web.txt`.

## Environment variables (all hosts)

| Var | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your Anthropic key (server-side; she never sees it) |
| `WARDROBE_PIN` | the PIN she'll type (e.g. a memorable 4–6 digits) |
| `WARDROBE_SECRET` | any long random string (signs her login token) |
| `WARDROBE_PROFILE` | `evangeline` |
| `MD_TZ` | `Australia/Sydney` (or her timezone) |

## Recommended: Railway or Fly.io (always-on, dead simple, reliable)

Her cleaned images + cutouts live under `profiles/evangeline/` (gitignored). The
**Dockerfile** copies them into the image, so a container deploy just works.

**Railway**
1. Push this repo to GitHub (the Dockerfile is detected automatically).
2. New Project → Deploy from repo.
3. Add the env vars above.
4. Railway gives an HTTPS URL — that's her link.

**Fly.io**
```
fly launch --no-deploy        # detects the Dockerfile
fly secrets set ANTHROPIC_API_KEY=... WARDROBE_PIN=... WARDROBE_SECRET=... WARDROBE_PROFILE=evangeline MD_TZ=Australia/Sydney
fly deploy
```

## Free option: Vercel (`vercel.json` + `api/index.py` included)

```
vercel --prod
```
Set the same env vars in the Vercel dashboard. Notes: Vercel runs it as a Python
serverless function (10s limit — the outfit call fits). `includeFiles` ships her
`profiles/evangeline/**`. If the function size or ASGI specifics give trouble, use
Railway/Fly (above) — same app, no fiddling.

## Fallback: your Mac + a tunnel (no hosting account)

```
set -a; source ~/.config/morning-desk/environment; set +a
export WARDROBE_PIN=... WARDROBE_SECRET=... WARDROBE_PROFILE=evangeline
./venv/bin/uvicorn webapp.app:app --host 0.0.0.0 --port 8210
# in another terminal:
cloudflared tunnel --url http://localhost:8210
```
Cloudflare prints a stable HTTPS URL. Works while your Mac is on.

## Swapping in her real clothes (after you scan them)

1. Drop her photos into `profiles/evangeline/inbox/`.
2. Run (needs the keys):
   ```
   ./venv/bin/python -m wardrobe.ingest --profile evangeline
   ./venv/bin/python -m wardrobe.enhance_images --profile evangeline
   ./venv/bin/python -m wardrobe.fix_orientation --profile evangeline
   ```
3. Regenerate her cutouts:
   ```
   ./venv/bin/python -c "from pathlib import Path; from wardrobe.compose import cutout; \
   d=Path('profiles/evangeline'); [cutout(p).save(d/'cutouts'/(p.stem+'.png')) for p in (d/'images_clean').glob('*.jpg')]"
   ```
4. Redeploy. (The current `profiles/evangeline` data is **placeholder** — menswear
   items remapped to womenswear categories — just so the app runs before her scan.)

## How she uses it (the gift note)

1. Open the link on her phone.
2. Tap Share → **Add to Home Screen** (it becomes an app with an icon).
3. Enter the PIN once.
4. See today's outfit. Tap an occasion, "Warmer", anchor a piece she wants to wear,
   or type a wish — then "Show me an outfit".
