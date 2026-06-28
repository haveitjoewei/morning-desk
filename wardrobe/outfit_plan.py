"""Per-date outfit plan so the night-before choice IS the morning choice.

The evening job picks tomorrow's outfit and stores it here keyed by date; the
next morning reuses the stored choice instead of regenerating (outfit generation
is otherwise non-deterministic). Cleared entries simply regenerate on demand.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def _plan_path():
    default = Path(__file__).resolve().parents[1] / "content" / "outfit_plan.json"
    return Path(os.environ.get("MD_OUTFIT_PLAN", str(default)))


def _load():
    try:
        return json.loads(_plan_path().read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data):
    path = _plan_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("outfit_plan.tmp.json")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def get_outfit(date_iso):
    return _load().get(date_iso)


def set_outfit(date_iso, outfit, keep_from=None):
    data = _load()
    data[date_iso] = outfit
    if keep_from:  # prune past dates to keep the file small
        data = {k: v for k, v in data.items() if k >= keep_from}
    _save(data)
    return outfit


def planned_outfit(date_iso, builder, keep_from=None):
    """Return the stored outfit for date_iso, or build it once and store it."""
    existing = get_outfit(date_iso)
    if existing is not None:
        return existing
    return set_outfit(date_iso, builder(), keep_from=keep_from)
