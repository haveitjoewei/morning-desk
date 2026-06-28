"""Self-correcting wardrobe — apply a plain-language correction to one garment.

You say what's wrong; Claude returns the corrected record and a note appended to
the garment's `learned[]` history, so future outfit picks respect the correction.

    ./venv/bin/python -m wardrobe.correct loafers "too formal for the office"
    ./venv/bin/python -m wardrobe.correct grey-nike-mesh-athletic-shorts "these are navy not grey"

The id can be an exact id, or any substring of an id or name (e.g. "loafers").
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from ai._llm import MODEL, available, client, text_of
from wardrobe.ingest import GARMENT_SCHEMA

ITEMS = Path(__file__).resolve().parents[1] / "wardrobe" / "items.json"

# Garment fields a correction may touch (the flat ingest schema fields).
MUTABLE = list(GARMENT_SCHEMA["properties"])

# Reuse the proven flat schema (a nested "updates" object was rejected as too
# complex); the model returns the full corrected record plus a learned note.
CORRECT_SCHEMA = copy.deepcopy(GARMENT_SCHEMA)
CORRECT_SCHEMA["properties"]["learned_note"] = {
    "type": "string",
    "description": "Short note recording what changed and why.",
}
CORRECT_SCHEMA["required"] = GARMENT_SCHEMA["required"] + ["learned_note"]

SYSTEM = (
    "You maintain a wardrobe catalogue. Given one garment's current record and a "
    "correction from its owner, return the corrected FULL record: change only the "
    "fields the correction implies and keep every other field identical to the input. "
    "'formality' is the list of settings the item suits (athletic/casual/smart casual/"
    "business/formal) — adjust the whole list when formality is corrected. Also write a "
    "short learned_note describing the change."
)


def find(items, needle):
    for i in items:
        if i.get("id") == needle:
            return i
    matches = [
        i for i in items
        if needle.lower() in i.get("id", "").lower() or needle.lower() in i.get("name", "").lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit("Ambiguous — matches: " + ", ".join(i["id"] for i in matches))
    return None


def correct(needle, instruction):
    if not available():
        raise SystemExit("ANTHROPIC_API_KEY not set — correction needs it.")
    items = json.loads(ITEMS.read_text())
    item = find(items, needle)
    if not item:
        raise SystemExit(f"No garment matching '{needle}'.")

    record = {k: item.get(k) for k in MUTABLE}
    resp = client(timeout=60).messages.create(
        model=MODEL,
        max_tokens=700,
        output_config={"format": {"type": "json_schema", "schema": CORRECT_SCHEMA}},
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": json.dumps({"record": record, "correction": instruction}, ensure_ascii=False),
        }],
    )
    result = json.loads(text_of(resp))
    note = result.pop("learned_note", "")
    changed = {k: result[k] for k in MUTABLE if k in result and result[k] != item.get(k)}

    if not changed:
        print(f"No field changes inferred for {item['id']}.")
    for k, v in changed.items():
        print(f"  {k}: {item.get(k)!r} -> {v!r}")
        item[k] = v
    item.setdefault("learned", []).append({"correction": instruction, "note": note})
    print(f"  learned += {note!r}")

    tmp = ITEMS.with_name("items.tmp.json")
    tmp.write_text(json.dumps(items, indent=2) + "\n")
    tmp.replace(ITEMS)
    print(f"Saved {item['id']}.")


def main():
    parser = argparse.ArgumentParser(description="Apply a plain-language wardrobe correction.")
    parser.add_argument("item", help="Garment id, or a substring of its id/name.")
    parser.add_argument("instruction", help="What's wrong, in plain language.")
    args = parser.parse_args()
    correct(args.item, args.instruction)


if __name__ == "__main__":
    main()
