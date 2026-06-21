"""Google Calendar connector — today's events as [{time, title}].

Standalone (no MCP in the loop): authenticates to the Google Calendar API with
a stored OAuth token. One-time setup mints the token via the local consent flow:

    python -m connectors.calendar_google --auth

Paths are env-configurable:
    MD_GCAL_CREDENTIALS  OAuth client secrets json   (default ~/.config/morning-desk/gcal_credentials.json)
    MD_GCAL_TOKEN        stored user token           (default ~/.config/morning-desk/gcal_token.json)
    MD_GCAL_ID           calendar id                 (default "primary")
    MD_TZ                IANA timezone for day bounds (default local)

Falls back to a stub schedule when libraries or a valid token are absent, so the
morning job and tests run without Google set up.
"""
from __future__ import annotations

import os
from datetime import datetime, time, timezone
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_STUB = [
    {"time": "09:30", "title": "Standup"},
    {"time": "12:00", "title": "Lunch"},
    {"time": "17:30", "title": "Badminton"},
]


def _path(env, default):
    return Path(os.environ.get(env, default)).expanduser()


def _token_path():
    return _path("MD_GCAL_TOKEN", "~/.config/morning-desk/gcal_token.json")


def _credentials_path():
    return _path("MD_GCAL_CREDENTIALS", "~/.config/morning-desk/gcal_credentials.json")


def _tzinfo():
    tz = os.environ.get("MD_TZ")
    if tz and tz != "auto":
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(tz)
        except Exception:
            pass
    return datetime.now().astimezone().tzinfo


def _load_credentials():
    """Return valid google credentials, or None if unavailable."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token = _token_path()
    if not token.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token.write_text(creds.to_json())
    return creds if creds and creds.valid else None


def fetch_calendar():
    try:
        creds = _load_credentials()
        if not creds:
            return list(_STUB)
        from googleapiclient.discovery import build

        tz = _tzinfo()
        today = datetime.now(tz).date()
        start = datetime.combine(today, time.min, tz)
        end = datetime.combine(today, time.max, tz)

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        events = (
            service.events()
            .list(
                calendarId=os.environ.get("MD_GCAL_ID", "primary"),
                timeMin=start.astimezone(timezone.utc).isoformat(),
                timeMax=end.astimezone(timezone.utc).isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
            .get("items", [])
        )

        out = []
        for ev in events:
            start_info = ev.get("start", {})
            dt = start_info.get("dateTime")
            if dt:
                label = datetime.fromisoformat(dt).astimezone(tz).strftime("%H:%M")
            else:
                label = "all-day"  # date-only event
            out.append({"time": label, "title": ev.get("summary", "(no title)")})
        return out
    except Exception:
        return list(_STUB)


def _authorize():
    """One-time: run the OAuth consent flow and persist the token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds_path = _credentials_path()
    if not creds_path.exists():
        raise SystemExit(
            f"Missing OAuth client secrets at {creds_path}. Download it from Google "
            "Cloud Console (OAuth client, type 'Desktop app') and place it there, or "
            "set MD_GCAL_CREDENTIALS."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token = _token_path()
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json())
    print(f"Token written to {token}")


if __name__ == "__main__":
    import sys

    if "--auth" in sys.argv:
        _authorize()
    else:
        import json

        print(json.dumps(fetch_calendar(), indent=2))
