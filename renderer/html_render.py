"""HTML render — the same content JSON as a crisp, responsive page.

This is the Raspberry Pi's primary display: Chromium in kiosk mode loads it
fullscreen. No external assets, inline CSS, sized for 1280x720 but fluid. Unlike
the e-ink PNG there's no font/ellipsis limit, and it's the seam for future touch.

    from renderer.html_render import render_html
    html = render_html(content_dict)
"""
from __future__ import annotations

import html as _html


def _esc(value):
    return _html.escape(str(value), quote=True)


def _calendar_rows(calendar):
    if not calendar:
        return '<li class="empty">Nothing scheduled</li>'
    rows = []
    for event in calendar:
        rows.append(
            f'<li><span class="time">{_esc(event.get("time", ""))}</span>'
            f'<span class="title">{_esc(event.get("title", ""))}</span></li>'
        )
    return "\n".join(rows)


def _attention_block(priority_items):
    if not priority_items:
        return (
            '<section class="attention clear">'
            '<h2>ALL CLEAR</h2>'
            '<p>Nothing needs your attention right now.</p></section>'
        )
    count = len(priority_items)
    noun = "THING" if count == 1 else "THINGS"
    rows = "\n".join(
        f'<li><span class="u u-{_esc(item.get("urgency", "today"))}"></span>'
        f'{_esc(item.get("title", ""))}'
        f'<span class="action">{_esc(item.get("suggested_action", ""))}</span></li>'
        for item in priority_items
    )
    return (
        f'<section class="attention"><h2>{count} {noun} NEED ATTENTION</h2>'
        f'<ul>{rows}</ul></section>'
    )


def _outfit_block(outfit):
    if not isinstance(outfit, dict):
        return f'<p>{_esc(outfit)}</p>'
    items = outfit.get("items", [])
    items_html = "".join(f"<li>{_esc(i)}</li>" for i in items)
    return (
        f'<p class="headline">{_esc(outfit.get("headline", ""))}</p>'
        f'<ul class="items">{items_html}</ul>'
        f'<p class="reason">{_esc(outfit.get("reason", ""))}</p>'
    )


CSS = """
:root { --ink:#111; --muted:#666; --line:#e2e2e2; --bg:#fff; }
* { box-sizing:border-box; margin:0; padding:0; }
html,body { height:100%; }
body { background:var(--bg); color:var(--ink); font-family:-apple-system,"SF Pro Text",
  "Segoe UI",Roboto,"DejaVu Sans",sans-serif; padding:28px 36px;
  display:grid; grid-template-rows:auto auto 1fr auto; gap:20px; min-height:100vh; }
.hero { display:flex; justify-content:space-between; align-items:baseline;
  border-bottom:2px solid var(--ink); padding-bottom:16px; }
.hero h1 { font-family:Georgia,"Times New Roman","DejaVu Serif",serif; font-weight:600;
  font-size:54px; letter-spacing:-0.5px; }
.hero .weather { font-size:26px; color:var(--ink); }
.attention { background:var(--ink); color:#fff; border-radius:8px; padding:20px 26px; }
.attention.clear { background:#fff; color:var(--ink); border:2px solid var(--ink); }
.attention h2 { font-family:"SF Mono","DejaVu Sans Mono",monospace; font-size:22px;
  letter-spacing:3px; margin-bottom:10px; }
.attention ul { list-style:none; }
.attention li { font-size:26px; line-height:1.5; display:flex; align-items:center; gap:12px; }
.attention .u { width:10px; height:10px; border-radius:50%; background:#fff; flex:none; }
.attention .u-urgent { background:#ff5c5c; }
.attention .action { color:#bbb; font-size:18px; margin-left:auto; }
.cols { display:grid; grid-template-columns:1fr 1fr; gap:36px; }
.panel { border-top:2px solid var(--ink); padding-top:12px; }
.panel h3 { font-family:"SF Mono","DejaVu Sans Mono",monospace; font-size:14px;
  letter-spacing:2px; color:var(--muted); margin-bottom:12px; }
.cal { list-style:none; }
.cal li { font-size:22px; line-height:1.6; display:flex; gap:14px; }
.cal .time { font-variant-numeric:tabular-nums; color:var(--muted); min-width:64px; }
.cal .empty { color:var(--muted); }
.wear .headline { font-size:26px; font-weight:600; margin-bottom:6px; }
.wear .items { list-style:none; font-size:18px; color:#333; display:flex; flex-wrap:wrap; gap:6px 14px; }
.wear .items li::after { content:"·"; margin-left:14px; color:var(--line); }
.wear .items li:last-child::after { content:""; }
.wear .reason { font-size:16px; color:var(--muted); margin-top:10px; line-height:1.4; }
.bottom { display:grid; grid-template-columns:2fr 1fr; gap:36px; }
.bottom p { font-size:18px; line-height:1.5; }
.ask p { font-style:italic; }
"""


def render_html(content, refresh_seconds=900):
    weather = content.get("weather", {})
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<meta http-equiv='refresh' content='{int(refresh_seconds)}'>",
        f"<title>Morning Desk — {_esc(content.get('date_label',''))}</title>",
        f"<style>{CSS}</style></head><body>",
        "<header class='hero'>"
        f"<h1>{_esc(content.get('date_label',''))}</h1>"
        f"<span class='weather'>{_esc(weather.get('summary',''))}</span></header>",
        _attention_block(content.get("priority_items", [])),
        "<div class='cols'>"
        f"<section class='panel'><h3>TODAY</h3><ul class='cal'>{_calendar_rows(content.get('calendar', []))}</ul></section>"
        f"<section class='panel wear'><h3>WEAR</h3>{_outfit_block(content.get('outfit', {}))}</section>"
        "</div>",
        "<div class='bottom'>"
        f"<section class='panel'><h3>READ</h3><p>{_esc(content.get('briefing',''))}</p></section>"
        f"<section class='panel ask'><h3>ASK</h3><p>{_esc(content.get('journal_prompt',''))}</p></section>"
        "</div>",
        "</body></html>",
    ]
    return "".join(parts)


def main():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    content = json.loads((root / "content" / "latest.json").read_text())
    out = root / "renderer" / "latest.html"
    out.write_text(render_html(content))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
