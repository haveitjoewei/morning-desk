import argparse
import json
from pathlib import Path

from orchestrator.run_morning_job import build_content, write_content
from renderer.render import load_layout, render


def render_latest(content, output_path):
    root = output_path.parents[1]
    layout = load_layout(root / "renderer" / "layout.yaml")
    render(content, layout, output_path)


def run_morning(root=None, *, build_content_fn=build_content, render_fn=render_latest):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    content = build_content_fn()
    json_path = root / "content" / "latest.json"
    png_path = root / "renderer" / "latest.png"

    write_content(content, json_path)
    render_fn(content, png_path)

    return {
        "weather": content.get("weather", {}).get("summary", "weather unavailable"),
        "json": str(json_path),
        "png": str(png_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate the latest Morning Desk briefing.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    args = parser.parse_args()

    result = run_morning()
    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"Weather: {result['weather']}")
    print(f"Wrote: {result['json']}")
    print(f"Rendered: {result['png']}")


if __name__ == "__main__":
    main()
