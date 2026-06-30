from __future__ import annotations
import json
import os
from pathlib import Path

DEFAULT_PROFILE = "joseph"
_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CONFIG = {
    "location": {"latitude": -33.8688, "longitude": 151.2093,
                 "timezone": "Australia/Sydney", "label": "Sydney"},
    "categories": "menswear",
}

def profiles_root() -> Path:
    return Path(os.environ.get("MD_PROFILES_ROOT", _ROOT / "profiles"))

def profile_dir(name: str) -> Path:
    return profiles_root() / name

def load_config(name: str) -> dict:
    path = profile_dir(name) / "config.json"
    cfg = dict(DEFAULT_CONFIG)
    if path.exists():
        cfg.update(json.loads(path.read_text()))
    return cfg

def load_prefs(name: str) -> dict:
    path = profile_dir(name) / "prefs.json"
    return json.loads(path.read_text()) if path.exists() else {}

def items_path(name: str) -> Path:
    return profile_dir(name) / "items.json"
