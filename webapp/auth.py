"""PIN gate for the companion app.

Each profile has its own PIN (env WARDROBE_PIN for the default profile, and
WARDROBE_PIN_<NAME> for any others). Unlocking with a PIN mints a short signed
token that carries the matched profile, so one deployment serves several closets —
sign out and unlock with a different PIN to switch. Not real auth, but keeps
strangers out and is frictionless for a couple of trusted users.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time


def _secret() -> bytes:
    return os.environ.get("WARDROBE_SECRET", "dev-secret").encode()


def _default_profile() -> str:
    return os.environ.get("WARDROBE_PROFILE", "evangeline")


def _profile_pins() -> dict:
    """Map PIN -> profile name from the environment.

    WARDROBE_PIN belongs to the default profile; WARDROBE_PIN_<NAME> adds <name>.
    """
    pins = {}
    base = os.environ.get("WARDROBE_PIN")
    if base:
        pins[base] = _default_profile()
    prefix = "WARDROBE_PIN_"
    for key, value in os.environ.items():
        if key.startswith(prefix) and value:
            pins[value] = key[len(prefix):].lower()
    return pins


def check_pin(pin):
    """Return the profile whose PIN matches, else None."""
    pin = str(pin)
    matched = None
    for expected, profile in _profile_pins().items():
        if hmac.compare_digest(pin, expected):
            matched = profile
    return matched


def make_token(profile=None, ttl_days: int = 30) -> str:
    profile = profile or _default_profile()
    exp = str(int(time.time()) + ttl_days * 86400)
    payload = f"{profile}.{exp}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(token):
    """Return the profile bound to a valid token, else None."""
    try:
        parts = str(token).split(".")
        if len(parts) < 3:
            return None
        sig, exp, profile = parts[-1], parts[-2], ".".join(parts[:-2])
        payload = f"{profile}.{exp}"
        good = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, good) and int(exp) > time.time():
            return profile
        return None
    except Exception:
        return None
