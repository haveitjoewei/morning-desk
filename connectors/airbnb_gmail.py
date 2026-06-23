"""Airbnb connector — host-relevant Airbnb mail via Gmail (no app scraping).

Searches Gmail for recent Airbnb notifications and normalizes each to a RawEvent.
Query is env-configurable (MD_AIRBNB_QUERY); falls back to a stub when Gmail
isn't set up so tests and the morning job still run.
"""
from __future__ import annotations

import os

from connectors import _gmail
from connectors.base import RawEvent

DEFAULT_QUERY = "from:airbnb.com newer_than:2d -in:trash"

_STUB = [
    RawEvent(
        source="airbnb",
        title="Guest asked about ants",
        body="Guest message awaiting reply",
        metadata={"suggested_action": "Reply or forward to VA"},
    )
]


def fetch_airbnb_messages():
    query = os.environ.get("MD_AIRBNB_QUERY", DEFAULT_QUERY)
    messages = _gmail.search(query, max_results=int(os.environ.get("MD_AIRBNB_MAX", "10")))
    if not messages:
        return list(_STUB)
    return [
        RawEvent(
            source="airbnb",
            title=m["subject"],
            body=m["snippet"],
            metadata={"suggested_action": "Reply or forward to VA", "gmail_id": m["id"]},
        )
        for m in messages
    ]


if __name__ == "__main__":
    import sys

    if "--auth" in sys.argv:
        _gmail.authorize()
    else:
        for ev in fetch_airbnb_messages():
            print(f"[{ev.source}] {ev.title} — {ev.body}")
