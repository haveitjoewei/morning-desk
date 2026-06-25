"""VA inbox connector — items the VA forwards to a dedicated address/label.

The VA forwards anything needing attention to a Gmail label/address (no WhatsApp
scraping in v1). Searches Gmail and normalizes each to a RawEvent. Query is
env-configurable (MD_VA_QUERY); falls back to a stub when Gmail isn't set up.
"""
from __future__ import annotations

import os

from connectors import _gmail
from connectors.base import RawEvent

DEFAULT_QUERY = "label:VA newer_than:2d -in:trash"

_STUB = [
    RawEvent(
        source="va",
        title="Waiting on pest quote approval",
        body="VA flagged as blocking, needs your decision",
        metadata={"suggested_action": "Approve or decline quote"},
    )
]


def fetch_va_messages():
    query = os.environ.get("MD_VA_QUERY", DEFAULT_QUERY)
    messages = _gmail.search(query, max_results=int(os.environ.get("MD_VA_MAX", "10")))
    if messages is None:
        return list(_STUB) if os.environ.get("MD_DEMO") == "1" else []
    return [
        RawEvent(
            source="va",
            title=m["subject"],
            body=m["snippet"],
            metadata={"suggested_action": "Review and decide", "gmail_id": m["id"]},
        )
        for m in messages
    ]


if __name__ == "__main__":
    import sys

    if "--auth" in sys.argv:
        _gmail.authorize()
    else:
        for ev in fetch_va_messages():
            print(f"[{ev.source}] {ev.title} — {ev.body}")
