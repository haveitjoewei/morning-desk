# Morning Desk — e-ink morning briefing appliance

Distraction-free morning briefing on a dedicated Inkplate e-ink display. AI-driven
backend renders a single PNG each morning ("what needs my attention before I start
the day"); the device just wakes → GET image → draw → sleep. See `README.md` for the
full product brief.

## Architecture (4 layers, JSON is the seam)

```
connectors/ → orchestrator/ → content/latest.json → renderer/ → PNG → server/ → device
```

- **connectors/** — one module per source. Each `fetch()`s and normalizes to a common
  shape (`RawEvent` in `base.py`). No business logic, no formatting.
- **ai/** — Claude calls: `classify_urgency` (4-state enum), `generate_briefing`,
  `generate_outfit`, `generate_journal`. Prompts, not agents.
- **orchestrator/run_morning_job.py** — cron entrypoint. Calls connectors + ai,
  assembles `BriefingContent`, writes `content/latest.json`.
- **content/schema.py** — `BriefingContent` dataclass = the contract. Keep stable.
- **renderer/render.py** — reads `layout.yaml` + `latest.json`, draws PNG (800×480).
  Generic: knows only slot types `text`/`list`/`header` + dot-path `source`.
- **server/app.py** — serves latest PNG over HTTP.
- **device/inkplate_main.cpp** — wake, fetch, draw, sleep.
- **wardrobe/** — local clothing catalog feeding `generate_outfit` (extension beyond
  the original brief).

## Hard rules (from the brief — don't violate without discussion)

- No phone in the loop. Device talks only to the backend.
- Summarized, never streamed. Every block is classifier/summarizer output.
- Layout is data (`layout.yaml`), not code. Renderer is source-agnostic.
- Connectors are isolated plugins — adding a source never touches the renderer.
- No fragile deps in v1 critical path. WhatsApp scraping excluded; VA forwards to
  email/Slack instead. Airbnb via Gmail, not app scraping.
- Urgency is a 4-state enum (`ignore`/`low`/`today`/`urgent`). Only `today`/`urgent`
  surface; filtering happens in the orchestrator, not the renderer.

## Tech stack

Python 3.12, Pillow (render), PyYAML (layout), pytest. Stdlib `http.server` for serving.
Device firmware: Arduino/C++ (Inkplate SDK).

## Commands

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m orchestrator.run_morning_job   # build content/latest.json
./venv/bin/python -m renderer.render                # latest.json -> renderer/latest.png
./venv/bin/python -m pytest tests/ -q               # tests
```

## Status

- **Stage 1 (scaffold + stub→JSON→PNG):** done, 6 tests pass.
- **Stage 2 (real connectors):** in progress — weather first.
- **Stage 3 (Inkplate hardware):** not started.
