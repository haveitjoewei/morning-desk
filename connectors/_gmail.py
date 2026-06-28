"""Shared Gmail (read-only) auth + search used by the Airbnb and VA connectors.

One token serves both Gmail connectors. The same OAuth client secrets file used
for Calendar works here too (enable the Gmail API on the project). One-time:

    python -m connectors.airbnb_gmail --auth

Env-configurable:
    MD_GMAIL_CREDENTIALS  OAuth client secrets json  (default ~/.config/morning-desk/gmail_credentials.json)
    MD_GMAIL_TOKEN        stored user token          (default ~/.config/morning-desk/gmail_token.json)
"""
from __future__ import annotations

import os
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _path(env, default):
    return Path(os.environ.get(env, default)).expanduser()


def token_path():
    return _path("MD_GMAIL_TOKEN", "~/.config/morning-desk/gmail_token.json")


def credentials_path():
    return _path("MD_GMAIL_CREDENTIALS", "~/.config/morning-desk/gmail_credentials.json")


def load_credentials():
    """Return valid Gmail credentials, or None if unavailable."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token = token_path()
    if not token.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token.write_text(creds.to_json())
    return creds if creds and creds.valid else None


def authorize():
    """One-time OAuth consent flow; persists the token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds_path = credentials_path()
    if not creds_path.exists():
        raise SystemExit(
            f"Missing OAuth client secrets at {creds_path}. Download it from Google "
            "Cloud Console (OAuth client, type 'Desktop app'), enable the Gmail API, "
            "and place it there — or set MD_GMAIL_CREDENTIALS."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token = token_path()
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json())
    print(f"Token written to {token}")


def search(query, max_results=10):
    """Return one item per matching thread whose LATEST message is inbound (i.e. you
    haven't replied yet). Threads where your reply is the most recent message are
    dropped, so already-handled conversations don't keep showing up. Returns [] for
    an empty authenticated search, or None when Gmail is unavailable."""
    if os.environ.get("MD_OFFLINE") == "1":
        return None
    try:
        creds = load_credentials()
        if not creds:
            return None
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        listing = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
            .get("messages", [])
        )

        seen = set()
        out = []
        for ref in listing:
            thread_id = ref.get("threadId")
            if not thread_id or thread_id in seen:
                continue
            seen.add(thread_id)
            thread = (
                service.users()
                .threads()
                .get(
                    userId="me",
                    id=thread_id,
                    format="metadata",
                    metadataHeaders=["Subject", "From"],
                )
                .execute()
            )
            messages = thread.get("messages", [])
            if not messages:
                continue
            last = messages[-1]
            # If my reply is the most recent message, the thread is handled — skip it.
            if "SENT" in last.get("labelIds", []):
                continue
            headers = {h["name"]: h["value"] for h in last.get("payload", {}).get("headers", [])}
            out.append(
                {
                    "id": last.get("id", ref["id"]),
                    "subject": headers.get("Subject", "(no subject)"),
                    "sender": headers.get("From", ""),
                    "snippet": last.get("snippet", ""),
                }
            )
        return out
    except Exception:
        return None
