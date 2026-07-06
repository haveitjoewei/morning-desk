"""Publish the morning brief blocks (schedule + priorities) to the dashboard's KV.

Runs LOCALLY (needs the Google Calendar + Gmail tokens in ~/.config/morning-desk);
posts to /api/brief with a kiosk token. The kiosk launcher runs this before opening
the dashboard, so the brief refreshes each morning/evening.

  MD_DASHBOARD_URL   default https://morning-desk-ashen.vercel.app
  token              argv[1] or env MD_KIOSK_TOKEN
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from ai.triage_priorities import triage
from connectors.airbnb_gmail import fetch_airbnb_messages
from connectors.calendar_google import fetch_calendar
from connectors.va_inbox import fetch_va_messages

BASE = os.environ.get("MD_DASHBOARD_URL", "https://morning-desk-ashen.vercel.app")


def _ampm(hhmm):
    try:
        h, m = map(int, str(hhmm).split(":"))
    except Exception:
        return str(hhmm)
    return f"{((h + 11) % 12) + 1}:{m:02d} {'AM' if h < 12 else 'PM'}"


def build():
    schedule = [
        {"time": _ampm(e.get("time", "")), "title": e.get("title", ""),
         "location": e.get("location", ""), "dress_code": e.get("dress_code", "")}
        for e in (fetch_calendar() or [])
    ]
    raw = list(fetch_airbnb_messages() or []) + list(fetch_va_messages() or [])
    verdicts = triage(raw) if raw else []
    priorities = [
        {"title": event.title, "source": event.source,
         "urgency": verdict.get("urgency"), "summary": verdict.get("summary") or ""}
        for event, verdict in zip(raw, verdicts)
        if verdict.get("urgency") in {"today", "urgent"}
    ]
    now = datetime.now(ZoneInfo(os.environ.get("MD_TZ", "Australia/Sydney")))
    return {
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(timespec="minutes"),
        "schedule": schedule,
        "priorities": priorities,
    }


def publish(token):
    payload = build()
    req = urllib.request.Request(
        BASE + "/api/brief", data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
    )
    resp = urllib.request.urlopen(req, timeout=30).read().decode()
    print(f"published {len(payload['schedule'])} events, {len(payload['priorities'])} priorities -> {resp}")


if __name__ == "__main__":
    token = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MD_KIOSK_TOKEN", "")
    if not token:
        sys.exit("usage: publish_brief.py <kiosk-token>  (or set MD_KIOSK_TOKEN)")
    publish(token)
