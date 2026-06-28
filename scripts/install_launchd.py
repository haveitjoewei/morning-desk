import argparse
import os
import plistlib
import subprocess
from pathlib import Path


GENERATE_LABEL = "com.morningdesk.generate"
EVENING_LABEL = "com.morningdesk.generate.evening"
SERVE_LABEL = "com.morningdesk.serve"

ALL_LABELS = (GENERATE_LABEL, EVENING_LABEL, SERVE_LABEL)


def build_plists(root, hour=5, minute=45, evening_hour=21, evening_minute=0):
    root = Path(root).resolve()
    python = root / "venv" / "bin" / "python"
    logs = root / "logs"
    environment = {
        "PYTHONPATH": str(root),
        "MD_SERVER_HOST": "0.0.0.0",
    }

    generator = {
        "Label": GENERATE_LABEL,
        "ProgramArguments": [
            str(python),
            str(root / "scripts" / "morning.py"),
        ],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": environment,
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "RunAtLoad": True,
        "StandardOutPath": str(logs / "generate.log"),
        "StandardErrorPath": str(logs / "generate.error.log"),
    }
    evening = {
        "Label": EVENING_LABEL,
        "ProgramArguments": [
            str(python),
            str(root / "scripts" / "evening.py"),
        ],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": environment,
        "StartCalendarInterval": {"Hour": evening_hour, "Minute": evening_minute},
        "RunAtLoad": False,
        "StandardOutPath": str(logs / "evening.log"),
        "StandardErrorPath": str(logs / "evening.error.log"),
    }
    server = {
        "Label": SERVE_LABEL,
        "ProgramArguments": [
            str(python),
            str(root / "server" / "app.py"),
        ],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": environment,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(logs / "server.log"),
        "StandardErrorPath": str(logs / "server.error.log"),
    }
    return {
        GENERATE_LABEL: generator,
        EVENING_LABEL: evening,
        SERVE_LABEL: server,
    }


def agent_directory():
    return Path.home() / "Library" / "LaunchAgents"


def agent_path(label):
    return agent_directory() / f"{label}.plist"


def launch_domain():
    return f"gui/{os.getuid()}"


def unload(label):
    subprocess.run(
        ["launchctl", "bootout", launch_domain(), str(agent_path(label))],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def install(root, hour=5, minute=45, evening_hour=21, evening_minute=0):
    root = Path(root).resolve()
    (root / "logs").mkdir(parents=True, exist_ok=True)
    agent_directory().mkdir(parents=True, exist_ok=True)

    for label, payload in build_plists(root, hour, minute, evening_hour, evening_minute).items():
        path = agent_path(label)
        unload(label)
        with path.open("wb") as file:
            plistlib.dump(payload, file)
        subprocess.run(
            ["launchctl", "bootstrap", launch_domain(), str(path)],
            check=True,
        )
        print(f"Installed {label}: {path}")


def uninstall():
    for label in ALL_LABELS:
        path = agent_path(label)
        unload(label)
        if path.exists():
            path.unlink()
        print(f"Removed {label}")


def main():
    parser = argparse.ArgumentParser(
        description="Install Morning Desk launchd services."
    )
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--hour", type=int, default=5)
    parser.add_argument("--minute", type=int, default=45)
    parser.add_argument("--evening-hour", type=int, default=21)
    parser.add_argument("--evening-minute", type=int, default=0)
    args = parser.parse_args()

    if args.uninstall:
        uninstall()
        return
    install(
        Path(__file__).resolve().parents[1],
        args.hour,
        args.minute,
        args.evening_hour,
        args.evening_minute,
    )


if __name__ == "__main__":
    main()
