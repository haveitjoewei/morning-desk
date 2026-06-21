# Morning Desk

Stage 1 scaffold for an e-ink morning briefing appliance.

## What works

- Builds the v1 content JSON contract with stubbed data.
- Filters priority items to `today` and `urgent` in the orchestrator/content layer.
- Loads a non-coder-editable YAML layout.
- Renders the latest briefing to a PNG using only the Python standard library.
- Serves the PNG at `/latest.png`.

## Run

```bash
PYTHONPATH=. python3 orchestrator/run_morning_job.py
PYTHONPATH=. python3 renderer/render.py
PYTHONPATH=. python3 server/app.py
```

Then open `http://127.0.0.1:8080/latest.png`.

Install Pillow for anti-aliased text:

```bash
python3 -m pip install -r requirements.txt
```

Without Pillow, the renderer falls back to the dependency-free bitmap font.

## Test

```bash
PYTHONPATH=. python3 -m unittest discover -s tests
```

## Wardrobe Intake

Drop clothing photos into `wardrobe/inbox/`, then run:

```bash
PYTHONPATH=. python3 wardrobe/import_photos.py
```

The importer copies supported images into `wardrobe/images/` and writes editable draft records to `wardrobe/drafts.json`. Review warmth, rain suitability, formality, and notes before promoting real items into `wardrobe/items.json`.
