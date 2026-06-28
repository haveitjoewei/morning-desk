"""Generate the evening view — tomorrow's prep + end-of-day reflection.

Writes the same content store the morning job uses (with mode='evening'), so the
server/display shows whichever ran most recently. HTML is the Pi's display path;
a static latest.html is written for `open`-ing locally too.

    ./venv/bin/python -m scripts.evening
"""
import json
from pathlib import Path

from config.runtime_env import load_environment

load_environment()

from orchestrator.run_evening_job import build_evening_content
from orchestrator.run_morning_job import write_content
from renderer.html_render import render_html
from wardrobe.compose import write_outfit_cutouts


def run_evening(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    content = build_evening_content()
    json_path = root / "content" / "latest.json"
    html_path = root / "renderer" / "latest.html"

    write_content(content, json_path)
    write_outfit_cutouts(content, root)
    html_path.write_text(render_html(content))
    return {
        "weather": content.get("weather", {}).get("summary", "weather unavailable"),
        "date": content.get("date_label", ""),
        "json": str(json_path),
        "html": str(html_path),
    }


def main():
    result = run_evening()
    print(f"Evening view for {result['date']} — {result['weather']}")
    print(f"Wrote: {result['json']}")
    print(f"Rendered: {result['html']}")


if __name__ == "__main__":
    main()
