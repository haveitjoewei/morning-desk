"""PIN gate for the companion app.

A single shared PIN (env WARDROBE_PIN). On success we mint a short signed token
(HMAC over an expiry) the device stores and sends on API calls — not real auth,
but keeps strangers out and is frictionless for one trusted user.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time


def _secret() -> bytes:
    return os.environ.get("WARDROBE_SECRET", "dev-secret").encode()


def check_pin(pin) -> bool:
    expected = os.environ.get("WARDROBE_PIN", "")
    return bool(expected) and hmac.compare_digest(str(pin), expected)


def make_token(ttl_days: int = 30) -> str:
    exp = str(int(time.time()) + ttl_days * 86400)
    sig = hmac.new(_secret(), exp.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def verify_token(token) -> bool:
    try:
        exp, sig = str(token).split(".", 1)
        good = hmac.new(_secret(), exp.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, good) and int(exp) > time.time()
    except Exception:
        return False
