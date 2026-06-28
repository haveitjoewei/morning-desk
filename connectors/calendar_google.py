"""Google Calendar connector with a local JSON fallback."""
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _path(env, default):
    return Path(os.environ.get(env, default)).expanduser()


def token_path():
    return _path("MD_GCAL_TOKEN", "~/.config/morning-desk/gcal_token.json")


def credentials_path():
    return _path(
        "MD_GCAL_CREDENTIALS",
        "~/.config/morning-desk/gcal_credentials.json",
    )


def timezone_name():
    return os.environ.get("MD_TZ", "Australia/Sydney")


def tzinfo(name=None):
    try:
        return ZoneInfo(name or timezone_name())
    except Exception:
        return datetime.now().astimezone().tzinfo


def default_events_path():
    return Path(__file__).resolve().parents[1] / "calendar" / "events.json"


def load_calendar_events(path=None):
    path = Path(path) if path else default_events_path()
    if not path.exists():
        return []
    return json.loads(path.read_text())


def infer_dress_code(event):
    private = event.get("extendedProperties", {}).get("private", {})
    if private.get("dress_code"):
        return private["dress_code"]

    text = " ".join(
        [
            event.get("summary", ""),
            event.get("description", ""),
            event.get("location", ""),
        ]
    ).lower()
    if any(word in text for word in ["badminton", "gym", "run", "training", "athletic"]):
        return "athletic"
    if any(word in text for word in ["smart casual", "client", "dinner", "formal"]):
        return "smart casual"
    return "casual"


def parse_calendar_events(events, today=None, timezone_value=None):
    timezone_value = timezone_value or tzinfo()
    today = today or datetime.now(timezone_value).date()
    parsed = []

    for event in events:
        if "start" in event:
            start = datetime.fromisoformat(event["start"])
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone_value)
            start = start.astimezone(timezone_value)
            end = event.get("end", "")
        else:
            event_date = today + timedelta(days=event.get("day_offset", 0))
            hour, minute = map(int, event["time"].split(":"))
            start = datetime.combine(
                event_date,
                time(hour, minute),
                timezone_value,
            )
            end = (
                start + timedelta(minutes=event.get("duration_minutes", 60))
            ).isoformat()

        if start.date() != today:
            continue
        parsed.append(
            {
                "time": start.strftime("%H:%M"),
                "title": event["title"],
                "start": start.isoformat(),
                "end": end,
                "location": event.get("location", ""),
                "dress_code": event.get("dress_code", "casual"),
            }
        )

    return sorted(parsed, key=lambda event: event["start"])


def parse_google_events(events, timezone_name=None):
    local_tz = tzinfo(timezone_name)
    parsed = []

    for event in events:
        start_info = event.get("start", {})
        end_info = event.get("end", {})
        date_time = start_info.get("dateTime")
        if date_time:
            start = datetime.fromisoformat(date_time).astimezone(local_tz)
            end_value = end_info.get("dateTime", "")
            if end_value:
                end_value = datetime.fromisoformat(end_value).astimezone(local_tz).isoformat()
            label = start.strftime("%H:%M")
            start_value = start.isoformat()
        else:
            start_value = start_info.get("date", "")
            end_value = end_info.get("date", "")
            label = "all-day"

        parsed.append(
            {
                "time": label,
                "title": event.get("summary", "(no title)"),
                "start": start_value,
                "end": end_value,
                "location": event.get("location", ""),
                "dress_code": infer_dress_code(event),
            }
        )

    return parsed


def load_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    path = token_path()
    if not path.exists():
        return None
    credentials = Credentials.from_authorized_user_file(str(path), SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        path.write_text(credentials.to_json())
    return credentials if credentials.valid else None


def fetch_google_calendar(today=None):
    try:
        credentials = load_credentials()
        if not credentials:
            return None

        from googleapiclient.discovery import build

        local_tz = tzinfo()
        today = today or datetime.now(local_tz).date()
        start = datetime.combine(today, time.min, local_tz)
        end = start + timedelta(days=1)
        events = (
            build(
                "calendar",
                "v3",
                credentials=credentials,
                cache_discovery=False,
            )
            .events()
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
        return parse_google_events(events, timezone_name())
    except Exception:
        return None


def is_excluded(title):
    """Drop calendar entries that aren't personal appointments — e.g. Airbnb guest
    reservations synced into Google Calendar. Configurable via MD_CALENDAR_EXCLUDE
    (comma-separated, case-insensitive substrings)."""
    raw = os.environ.get(
        "MD_CALENDAR_EXCLUDE", "reserved,reservation,airbnb,not available,stay at"
    )
    keys = [k.strip().lower() for k in raw.split(",") if k.strip()]
    text = (title or "").lower()
    return any(k in text for k in keys)


def fetch_calendar(path=None, today=None):
    if path is not None:
        events = parse_calendar_events(load_calendar_events(path), today=today)
    elif os.environ.get("MD_OFFLINE") == "1":
        events = parse_calendar_events(load_calendar_events(), today=today)
    else:
        google_events = fetch_google_calendar(today=today)
        events = (
            google_events
            if google_events is not None
            else parse_calendar_events(load_calendar_events(), today=today)
        )
    return [event for event in events if not is_excluded(event.get("title", ""))]


def authorize():
    from google_auth_oauthlib.flow import InstalledAppFlow

    source = credentials_path()
    if not source.exists():
        raise SystemExit(
            f"Missing OAuth client secrets at {source}. Download a Google OAuth "
            "Desktop app credential and place it there, or set MD_GCAL_CREDENTIALS."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(source), SCOPES)
    credentials = flow.run_local_server(port=0)
    target = token_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(credentials.to_json())
    print(f"Token written to {target}")


if __name__ == "__main__":
    import sys

    if "--auth" in sys.argv:
        authorize()
    else:
        print(json.dumps(fetch_calendar(), indent=2))
