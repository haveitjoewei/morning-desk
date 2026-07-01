"""Tiny per-profile persistence over an Upstash/Vercel-KV Redis REST endpoint.

Optional: if no store is configured (KV_REST_API_URL / KV_REST_API_TOKEN, or the
UPSTASH_* equivalents), every call no-ops and callers fall back to browser-local
state. Connect a KV store in Vercel and it starts syncing across devices — no code
change. Values are small JSON blobs, so a single GET/SET per read/write is plenty.
"""
from __future__ import annotations

import json
import os
import urllib.request


def _cfg():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return (url.rstrip("/"), token) if url and token else (None, None)


def available() -> bool:
    return _cfg()[0] is not None


def _command(*args):
    url, token = _cfg()
    if not url:
        return None
    req = urllib.request.Request(
        url,
        data=json.dumps(list(args)).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return json.load(resp).get("result")
    except Exception:
        return None


def get_json(key):
    raw = _command("GET", key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def set_json(key, value) -> bool:
    return _command("SET", key, json.dumps(value, ensure_ascii=False)) is not None
