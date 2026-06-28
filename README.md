# Morning Desk

A distraction-free morning briefing rendered to a single 800x480 e-ink image.

## Current Pipeline

```text
Weather + Calendar + Gmail
            |
      classify/generate
            |
    content/latest.json
            |
       layout.yaml
            |
    renderer/latest.png
            |
       HTTP endpoint
```

The project works without credentials using deterministic local fallbacks. When
Anthropic or Google credentials are configured, the same pipeline automatically
uses the live integrations.

## Setup

```bash
make setup
make test
make status
make morning
make serve
```

Open `http://127.0.0.1:8080/latest.png`.

`make morning` fetches weather, collects calendar and priority items, generates
the briefing/outfit/journal content, writes `content/latest.json`, and renders
`renderer/latest.png`.

`make status` reports whether Claude, Google Calendar, Gmail, the rendered image,
and server configuration are ready without making external requests.

## Automatic Startup

On macOS, install the daily generator and always-on image server with:

```bash
make install-service
```

The briefing is generated at 5:45 AM local time and once immediately when the
agent is loaded. Logs are written under `logs/`.

Remove both agents with:

```bash
make uninstall-service
```

## Configuration

Weather location is editable in `config/location.json`.

Local fallback calendar events live in `calendar/events.json`. Relative events
with `"day_offset": 0` always represent today. The default file is empty;
`calendar/events.example.json` contains demo data you can copy or adapt.

The local wardrobe catalog lives in `wardrobe/items.json`.

## Claude

Set either credential before running `make morning`:

```bash
export ANTHROPIC_API_KEY="..."
```

Optional model override:

```bash
export MD_CLAUDE_MODEL="claude-opus-4-8"
```

For launchd, put runtime values in:

```text
~/.config/morning-desk/environment
```

Use `config/environment.example` as the template and set permissions to `600`.
Existing process environment values take precedence over the file.

Without a credential, briefing, outfit, urgency, and journal generation use
deterministic local logic. Claude outfit output is rejected if it invents an
item not present in `wardrobe/items.json`.

## Google Calendar

1. Enable the Google Calendar API.
2. Create an OAuth desktop-app credential.
3. Save it to:

```text
~/.config/morning-desk/gcal_credentials.json
```

4. Run:

```bash
make calendar-auth
```

The token is stored at `~/.config/morning-desk/gcal_token.json`. If OAuth is not
configured or fails, Morning Desk uses `calendar/events.json`. An authenticated
but empty Google Calendar stays empty rather than showing demo events.

## Gmail Sources

Enable the Gmail API and save an OAuth desktop credential to:

```text
~/.config/morning-desk/gmail_credentials.json
```

Then run:

```bash
make gmail-auth
```

Airbnb mail and VA-forwarded items are read-only Gmail searches. Queries can be
overridden with `MD_AIRBNB_QUERY` and `MD_VA_QUERY`.

Missing Gmail credentials and authenticated searches with no matching messages
produce no priority items. Set `MD_DEMO=1` only when you explicitly want the
sample Airbnb/VA alerts.

## Wardrobe Intake

Wardrobe photo intake is local-first. Drop photos into
`wardrobe/inbox/`, then run:

```bash
make wardrobe-import
```

Draft records are written to `wardrobe/drafts.json` for review before promotion
to `wardrobe/items.json`. Originals stay in `wardrobe/inbox/`; copied working
images are stored in `wardrobe/images/`.

Drafts include editable style fields such as material guess, texture,
thickness, fit, best uses, avoid uses, review status, confidence, and correction
history. Unknown values are intentional: they keep weak photo evidence separate
from facts you have confirmed.

Local corrections can be stored in `wardrobe/corrections.json` without editing
the base catalog. Each correction targets an exact item name:

```json
[
  {
    "name": "navy chore coat",
    "set": {
      "fit": "boxy but cropped",
      "warmth": "light"
    },
    "add": {
      "style_tags": ["dress_to_impress"],
      "best_for": ["office", "nice dinner"]
    },
    "note": "Looks longer in one photo than it fits."
  }
]
```

Morning Desk applies those corrections automatically before choosing an outfit.
The default schedule treats Tuesday, Thursday, and Friday as office days with a
dress-to-impress bias; Monday and Wednesday are work-from-home comfort days.

When you are ready to send wardrobe images to Claude for visual analysis, run:

```bash
make wardrobe-analyze
```

Use `MD_OFFLINE=1` to guarantee no photo analysis call is made. The analyzer
updates `wardrobe/drafts.json` with AI-inferred garment fields and marks records
as `ai_reviewed`; review before promoting them into the main catalog.

## Device

The backend now renders at Inkplate 10's native 1200x825 resolution. Design
coordinates remain 800x480 in `renderer/layout.yaml`, and the renderer scales
them to the configured canvas.

The Arduino sketch is in `device/morning_desk/`. Create
`device/morning_desk/secrets.h` from `secrets.example.h`, set the Wi-Fi details
and the server's LAN URL, then upload it with the Inkplate board package and
Inkplate library installed.

The device wakes, connects to Wi-Fi, streams `/latest.png`, refreshes the panel,
and sleeps for 24 hours. Failed fetches retry after 15 minutes without replacing
an already-displayed briefing.
