"""Per-profile memory of recently-worn outfits, so picks rotate instead of
repeating the same staples. Keyed by date; small JSON under the profile (runtime
state, gitignored)."""
from __future__ import annotations

import json

from core.profiles import profile_dir


def _path(profile):
    return profile_dir(profile) / "recent.json"


def _load(profile):
    try:
        return json.loads(_path(profile).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def recent_items(profile, exclude_date=None, days=5):
    """Item names worn over the last `days` recorded dates, excluding one date."""
    data = _load(profile)
    dates = sorted(d for d in data if d != exclude_date)[-days:]
    names = []
    for d in dates:
        for name in data[d]:
            if name not in names:
                names.append(name)
    return names


def record(profile, date, items, keep=8):
    data = _load(profile)
    data[str(date)] = list(items)
    for old in sorted(data)[:-keep]:  # prune oldest beyond `keep`
        data.pop(old, None)
    path = _path(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("recent.tmp.json")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)
