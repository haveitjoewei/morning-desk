import json
import os
import struct
from datetime import datetime
from pathlib import Path

from config.runtime_env import load_environment


def configured_path(env_name, default):
    return Path(os.environ.get(env_name, default)).expanduser()


def png_size(path):
    if not path.exists():
        return None
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return list(struct.unpack(">II", header[16:24]))


def collect_status(root=None, home=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    home = Path(home) if home else Path.home()
    config_root = home / ".config" / "morning-desk"
    image = root / "renderer" / "latest.png"
    content = root / "content" / "latest.json"

    generated_at = None
    if content.exists():
        try:
            generated_at = json.loads(content.read_text()).get("generated_at")
        except (OSError, json.JSONDecodeError):
            pass

    gcal_credentials = configured_path(
        "MD_GCAL_CREDENTIALS",
        config_root / "gcal_credentials.json",
    )
    gcal_token = configured_path(
        "MD_GCAL_TOKEN",
        config_root / "gcal_token.json",
    )
    gmail_credentials = configured_path(
        "MD_GMAIL_CREDENTIALS",
        config_root / "gmail_credentials.json",
    )
    gmail_token = configured_path(
        "MD_GMAIL_TOKEN",
        config_root / "gmail_token.json",
    )

    return {
        "claude": {
            "configured": bool(
                os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            ),
            "model": os.environ.get("MD_CLAUDE_MODEL", "claude-opus-4-8"),
        },
        "google_calendar": {
            "credentials": gcal_credentials.exists(),
            "token": gcal_token.exists(),
        },
        "gmail": {
            "credentials": gmail_credentials.exists(),
            "token": gmail_token.exists(),
        },
        "image": {
            "ready": image.exists(),
            "size": png_size(image),
            "updated_at": (
                datetime.fromtimestamp(image.stat().st_mtime).isoformat(
                    timespec="seconds"
                )
                if image.exists()
                else None
            ),
            "generated_at": generated_at,
        },
        "server": {
            "host": os.environ.get("MD_SERVER_HOST", "0.0.0.0"),
            "port": int(os.environ.get("MD_SERVER_PORT", "8080")),
        },
    }


def main():
    load_environment()
    print(json.dumps(collect_status(), indent=2))


if __name__ == "__main__":
    main()
