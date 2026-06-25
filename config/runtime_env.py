import os
from pathlib import Path


def default_environment_path():
    return Path.home() / ".config" / "morning-desk" / "environment"


def load_environment(path=None):
    path = Path(path) if path else default_environment_path()
    if not path.exists():
        return {}

    loaded = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded
