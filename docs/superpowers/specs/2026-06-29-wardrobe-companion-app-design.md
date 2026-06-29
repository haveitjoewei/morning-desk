# Wardrobe Companion App — Design

**Date:** 2026-06-29
**Goal:** A birthday gift (due Thursday 2026-07-02): a mobile-first web app that gives
Evangeline a daily outfit from her own wardrobe, which she can tweak. Built by
splitting morning-desk's outfit engine into a shared, profile-aware core so
morning-desk keeps using it for Joseph while her app uses it independently. Her
clothes and preferences never mix with his.

## 1. Scope (v1)

In scope:
- Per-profile wardrobes (Joseph / Evangeline), fully isolated.
- A shared "stylist core" the engine both front-ends call.
- Her hosted, PIN-gated, mobile-first web app: see today's outfit + tweak it.
- Her tweaks: standing prefs (runs cold, style notes, love/avoid colors) and
  per-day controls (occasion, temp nudge, anchor a piece, free-text wish, regenerate).
- Womenswear-aware categories for her profile.
- Reuse the existing ingest → enhance (white bg) → cutout pipeline for her clothes.

Out of scope (v1):
- Saving favorites / outfit history.
- Full wardrobe management UI (browse/edit/delete her items in the app). She gets the
  outfit + tweaks; Joseph curates her catalog via the existing CLI tools.
- Calendar integration for her (occasion picker replaces it).
- Cross-device preference sync (prefs live per-device in the browser).
- Real user accounts (single shared PIN).

## 2. Architecture

**Approach A (chosen): same repo, profile-aware core.** Refactor the engine in place to
take a profile; add `profiles/` and a `webapp/`. One codebase, no drift, engine
improvements benefit both front-ends. (Approach B — extract to an installable package —
deferred until it's worth the versioning overhead.)

```
profiles/
  joseph/      items.json  images_clean/  cutouts/  prefs.json  (categories: menswear)
  evangeline/  items.json  images_clean/  cutouts/  prefs.json  (categories: womenswear)

core/ (or refactored wardrobe/ + ai/)   profile-aware stylist engine
  - load_wardrobe(profile)              reads profiles/<profile>/items.json
  - generate_outfit(profile, weather, request)   request = prefs + day-overrides
  - ingest / enhance / cutout / fix_orientation  all take a profile

morning-desk (existing)   uses profile "joseph"; unchanged behaviour
webapp/ (new)             FastAPI, serves profile "evangeline"
```

**Profile** = a directory of data + a `prefs.json`, plus a category set. The core never
hardcodes a profile; callers pass one. morning-desk's scripts default to `joseph`.

### Migration of existing data
- Move current `wardrobe/items.json`, `images_clean/`, `cutouts/` → `profiles/joseph/`.
- Engine functions gain a `profile` parameter (default `joseph` so morning-desk is
  unaffected). Paths derive from the profile.
- `outfit_plan` (night = morning determinism) stays a morning-desk concern, keyed by
  profile so the two never collide.

## 3. Her web app

Mobile-first, single screen. Stack: FastAPI + a light HTML/CSS/JS frontend (no heavy
framework — server-rendered page + a little vanilla JS for tweaks/regenerate).

**Screens / states:**
- **Unlock:** one PIN field; on success the device remembers it (token in localStorage).
- **Today:** the recommended outfit rendered as the flat-lay (her cutouts), headline +
  stylist reason, the weather line.
- **Tweak bar:** occasion picker, warmer/lighter toggle, "anchor a piece" (opens a
  thumbnail grid of her wardrobe to pick one), a wish text field, and Regenerate.
- **Prefs (settings):** runs-cold toggle, style notes, love/avoid colors. Saved to
  localStorage.

**Endpoints (stateless):**
- `POST /api/outfit` — body: `{ prefs, day }` (prefs from localStorage, day = occasion
  /temp nudge/anchor id/wish). Returns the outfit (pieces + images + headline + reason).
- `GET /api/wardrobe` — her items (id, name, category, thumbnail) for the anchor picker.
- `GET /api/weather` — her location's weather (location in profile config).
- `GET /` — the app shell; `POST /api/unlock` — checks PIN, returns a signed token.
- Static: her cutout/enhanced images.

**Data flow:** browser holds prefs + PIN token → sends prefs + day controls with each
`/api/outfit` call → stateless server runs the shared engine (server-side
`ANTHROPIC_API_KEY`) → returns the outfit. No DB, no persistent disk.

## 4. Tweak → engine mapping

| Tweak | Engine effect |
|---|---|
| Runs cold (standing) | Warmth weighting up; bias toward an added layer |
| Style notes (standing) | Appended to the stylist system/context |
| Love/avoid colors | Palette guidance in the prompt |
| Occasion (per-day) | Formality/context target (Casual…Going out) |
| Warmer / lighter (per-day) | Shifts the temperature the engine dresses for |
| Anchor a piece (per-day) | Force-include that item; build the look around it |
| Wish (per-day) | Free-text instruction appended to the prompt |

These extend the engine's existing `context`/preferences input — the generator already
accepts structured context; we add `prefs` and `day` fields and fold them into the
stylist prompt, with `anchor` enforced in selection (and validated against her wardrobe).

## 5. Womenswear categories

Her profile's category set: `top, blouse, knit, cardigan, outerwear, dress, skirt, pants,
jeans, shorts, shoes, bag, accessory`. Layering rules adapt: a `dress` is a complete base
(no separate top/bottom); `skirt`/`pants`/`jeans`/`shorts` are bottoms; `cardigan`/`knit`
/`outerwear` are layers; shoes/bag/accessory finish. The flat-lay grouping and
per-category sizing extend to these. Her ingest vision prompt is womenswear-aware. The
category set is profile-scoped, so Joseph's stays menswear.

## 6. Hosting & security

- **Host:** Railway or Fly.io, ~$5/mo, always-on (no cold-start lag). Her wardrobe images
  ship inside the deploy. `ANTHROPIC_API_KEY` and the `WARDROBE_PIN` are host env vars.
- **Security:** single shared PIN. `POST /api/unlock` checks it and returns a signed
  (HMAC) token stored in localStorage; the token is required on API calls. Not real auth,
  but keeps strangers out and is frictionless for her. HTTPS via the host's domain.
- **Privacy note:** her photos live on the host. Acceptable for a private personal
  deployment; documented so it's a conscious choice.

## 7. Pre-Thursday data prep

Joseph scans her clothes → drop into `profiles/evangeline/inbox/` → run the existing
pipeline (ingest → enhance white-bg → cutout → fix_orientation), now profile-aware, to
build her catalog + images. Roughly the same flow already used for his 82 items.

## 8. Risks / cut-lines for the deadline

- If hosting setup runs long, fall back to home-machine + Cloudflare tunnel (still a real
  URL) — same app, different deploy.
- If womenswear layering proves fiddly, ship with the core categories above and refine
  post-gift.
- The anchor picker (wardrobe thumbnail grid) is the most UI; if time-tight, ship anchor
  as "type the item name" first, add the visual picker right after.

## Success criteria

On Thursday, Evangeline opens a link on her phone, enters a PIN once, and sees a
genuinely good outfit from her own clothes. She can say "I'm cold," pick an occasion,
anchor a piece she wants to wear, or type a wish, and get a new look that respects it —
all without touching Joseph's wardrobe or anything technical.
