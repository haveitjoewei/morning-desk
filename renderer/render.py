import json
import struct
import textwrap
import zlib
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None


FONT = {
    "A": ["010", "101", "101", "111", "101", "101", "101"],
    "B": ["110", "101", "101", "110", "101", "101", "110"],
    "C": ["011", "100", "100", "100", "100", "100", "011"],
    "D": ["110", "101", "101", "101", "101", "101", "110"],
    "E": ["111", "100", "100", "110", "100", "100", "111"],
    "F": ["111", "100", "100", "110", "100", "100", "100"],
    "G": ["011", "100", "100", "101", "101", "101", "011"],
    "H": ["101", "101", "101", "111", "101", "101", "101"],
    "I": ["111", "010", "010", "010", "010", "010", "111"],
    "J": ["001", "001", "001", "001", "101", "101", "010"],
    "K": ["101", "101", "110", "100", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101", "101", "101"],
    "N": ["101", "111", "111", "111", "101", "101", "101"],
    "O": ["010", "101", "101", "101", "101", "101", "010"],
    "P": ["110", "101", "101", "110", "100", "100", "100"],
    "Q": ["010", "101", "101", "101", "111", "011", "001"],
    "R": ["110", "101", "101", "110", "110", "101", "101"],
    "S": ["011", "100", "100", "010", "001", "001", "110"],
    "T": ["111", "010", "010", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "101", "101", "010"],
    "W": ["101", "101", "101", "101", "111", "111", "101"],
    "X": ["101", "101", "101", "010", "101", "101", "101"],
    "Y": ["101", "101", "101", "010", "010", "010", "010"],
    "Z": ["111", "001", "001", "010", "100", "100", "111"],
    "0": ["111", "101", "101", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "010", "010", "111"],
    "2": ["110", "001", "001", "010", "100", "100", "111"],
    "3": ["110", "001", "001", "010", "001", "001", "110"],
    "4": ["101", "101", "101", "111", "001", "001", "001"],
    "5": ["111", "100", "100", "110", "001", "001", "110"],
    "6": ["011", "100", "100", "110", "101", "101", "010"],
    "7": ["111", "001", "001", "010", "010", "100", "100"],
    "8": ["010", "101", "101", "010", "101", "101", "010"],
    "9": ["010", "101", "101", "011", "001", "001", "110"],
    ":": ["000", "010", "010", "000", "010", "010", "000"],
    "-": ["000", "000", "000", "111", "000", "000", "000"],
    ",": ["000", "000", "000", "000", "010", "010", "100"],
    ".": ["000", "000", "000", "000", "000", "010", "010"],
    "'": ["010", "010", "000", "000", "000", "000", "000"],
    "/": ["001", "001", "010", "010", "100", "100", "000"],
    "?": ["110", "001", "001", "010", "010", "000", "010"],
    "&": ["010", "101", "101", "010", "101", "101", "011"],
    "+": ["000", "010", "010", "111", "010", "010", "000"],
    "(": ["001", "010", "100", "100", "100", "010", "001"],
    ")": ["100", "010", "001", "001", "001", "010", "100"],
}


def _parse_value(value):
    value = value.strip()
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("{"):
        parsed = {}
        for part in value[1:-1].split(","):
            key, raw = part.split(":", 1)
            parsed[key.strip()] = _parse_value(raw)
        return parsed
    if value.startswith("["):
        return [part.strip() for part in value[1:-1].split(",") if part.strip()]
    if value.isdigit():
        return int(value)
    return value


def load_layout(path):
    layout = {"canvas": {}, "slots": []}
    current = None
    current_section = None

    for raw_line in Path(path).read_text().splitlines():
        if not raw_line.strip():
            continue
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped == "canvas:":
            current_section = "canvas"
            continue
        if stripped == "slots:":
            current_section = "slots"
            continue
        if stripped.startswith("- "):
            current = {}
            layout["slots"].append(current)
            key, value = stripped[2:].split(":", 1)
            current[key] = _parse_value(value)
            continue

        key, value = stripped.split(":", 1)
        target = layout["canvas"] if current_section == "canvas" else current
        target[key] = _parse_value(value)

    return layout


class Canvas:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.pixels = bytearray([255] * width * height)

    def rect(self, x, y, w, h, shade=0):
        for yy in range(max(0, y), min(self.height, y + h)):
            start = yy * self.width + max(0, x)
            end = yy * self.width + min(self.width, x + w)
            self.pixels[start:end] = bytes([shade]) * (end - start)

    def border(self, x, y, w, h):
        self.rect(x, y, w, 1)
        self.rect(x, y + h - 1, w, 1)
        self.rect(x, y, 1, h)
        self.rect(x + w - 1, y, 1, h)

    def text(self, x, y, text, scale=2, max_width=None, shade=0):
        cursor_x = x
        cursor_y = y
        char_w = 4 * scale
        limit = x + (max_width or self.width)
        for char in text.upper():
            if char == "\n" or cursor_x + char_w > limit:
                cursor_x = x
                cursor_y += 9 * scale
                if char == "\n":
                    continue
            glyph = FONT.get(char)
            if glyph:
                for row, bits in enumerate(glyph):
                    for col, bit in enumerate(bits):
                        if bit == "1":
                            self.rect(
                                cursor_x + col * scale,
                                cursor_y + row * scale,
                                scale,
                                scale,
                                shade,
                            )
            cursor_x += char_w

    def save_png(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = b"".join(
            b"\x00" + bytes(self.pixels[y * self.width : (y + 1) * self.width])
            for y in range(self.height)
        )

        def chunk(name, data):
            payload = name + data
            return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))

        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )
        path.write_bytes(png)


def _resolve(content, source):
    value = content
    for part in source.split("."):
        value = value[part]
    return value


def slot_text(value, fields=None, max_items=None):
    if isinstance(value, list):
        lines = []
        for item in value[: max_items or len(value)]:
            lines.append(" - ".join(str(item[field]) for field in fields))
        return "\n".join(lines)
    if isinstance(value, dict) and fields:
        lines = []
        for field in fields:
            field_value = value.get(field, "")
            if isinstance(field_value, list):
                field_value = ", ".join(str(item) for item in field_value)
            lines.append(str(field_value))
        return "\n".join(lines)
    return str(value)


def _slot_text(value, fields=None, max_items=None):
    return slot_text(value, fields, max_items)


def _label_text(content, label):
    if not label:
        return ""
    if "." in label:
        return str(_resolve(content, label))
    return label


def attention_text(value, max_items=None):
    if not value:
        return "ALL CLEAR\nNothing needs your attention right now."
    items = value[: max_items or len(value)]
    noun = "THING" if len(value) == 1 else "THINGS"
    lines = [f"{len(value)} {noun} NEED ATTENTION"]
    lines.extend(item["title"] for item in items)
    return "\n".join(lines)


def _wrap(text, width):
    wrapped = []
    for line in text.splitlines():
        wrapped.extend(textwrap.wrap(line, width=width) or [""])
    return "\n".join(wrapped)


def _draw_slot_chrome(canvas, slot, pos):
    chrome = slot.get("style", {}).get("chrome", "line")
    if chrome == "solid":
        canvas.rect(pos["x"], pos["y"], pos["w"], pos["h"], 0)
    elif chrome == "line":
        canvas.rect(pos["x"], pos["y"], pos["w"], 2)


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size)


def _wrap_pillow(draw, text, font, width):
    lines = []
    for raw_line in text.splitlines():
        words = raw_line.split()
        if not words:
            lines.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if draw.textlength(candidate, font=font) <= width:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def _draw_pillow_text(draw, xy, text, font, width, fill=0, leading=1.18):
    x, y = xy
    lines = _wrap_pillow(draw, text, font, width)
    line_height = int(font.size * leading)
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_height), line, font=font, fill=fill)


def _draw_pillow_fields(draw, xy, value, fields, width, fonts):
    x, y = xy
    title_font, item_font, reason_font = fonts
    values = []
    for field in fields:
        field_value = value.get(field, "")
        if isinstance(field_value, list):
            field_value = ", ".join(str(item) for item in field_value)
        values.append(str(field_value))
    values += [""] * (3 - len(values))

    draw.text((x, y), values[0], font=title_font, fill=0)

    item_y = y + round(title_font.size * 1.35)
    item_line_height = round(item_font.size * 1.2)
    items = values[1]
    for index, line in enumerate(_wrap_pillow(draw, items, item_font, width)):
        draw.text(
            (x, item_y + index * item_line_height),
            line,
            font=item_font,
            fill=0,
        )

    reason_y = (
        item_y
        + min(2, len(_wrap_pillow(draw, items, item_font, width)))
        * item_line_height
        + round(reason_font.size * 0.3)
    )
    reason = values[2]
    reason_line_height = round(reason_font.size * 1.15)
    for index, line in enumerate(_wrap_pillow(draw, reason, reason_font, width)):
        draw.text(
            (x, reason_y + index * reason_line_height),
            line,
            font=reason_font,
            fill=0,
        )


def _render_with_pillow(content, layout, output_path):
    canvas_config = layout["canvas"]
    width = canvas_config["width"]
    height = canvas_config["height"]
    scale_x = width / canvas_config.get("design_width", width)
    scale_y = height / canvas_config.get("design_height", height)
    font_scale = min(scale_x, scale_y)
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)

    def size(value):
        return max(1, round(value * font_scale))

    display = _font("/System/Library/Fonts/NewYork.ttf", size(42))
    body = _font("/System/Library/Fonts/SFNS.ttf", size(18))
    body_small = _font("/System/Library/Fonts/SFNS.ttf", size(15))
    body_tiny = _font("/System/Library/Fonts/SFNS.ttf", size(13))
    label_font = _font("/System/Library/Fonts/SFNSMono.ttf", size(13))
    attention_label = _font("/System/Library/Fonts/SFNSMono.ttf", size(21))
    attention_item = _font("/System/Library/Fonts/SFNS.ttf", size(21))

    for slot in layout["slots"]:
        pos = slot["position"]
        x = round(pos["x"] * scale_x)
        y = round(pos["y"] * scale_y)
        w = round(pos["w"] * scale_x)
        h = round(pos["h"] * scale_y)
        chrome = slot.get("style", {}).get("chrome", "line")
        value = _resolve(content, slot["source"])

        if slot["type"] == "hero":
            draw.text((x, y - round(2 * scale_y)), str(value), font=display, fill=0)
            weather = _label_text(content, slot.get("label"))
            weather_width = draw.textlength(weather, font=body)
            draw.text(
                (x + w - weather_width, y + round(10 * scale_y)),
                weather,
                font=body,
                fill=0,
            )
            draw.line((x, y + h - 1, x + w, y + h - 1), fill=0, width=1)
            continue

        if chrome == "solid":
            if not value:
                draw.line((x, y, x + w, y), fill=0, width=2)
                draw.text(
                    (x, y + round(18 * scale_y)),
                    "ALL CLEAR",
                    font=attention_label,
                    fill=0,
                )
                draw.text(
                    (x, y + round(55 * scale_y)),
                    "Nothing needs your attention right now.",
                    font=attention_item,
                    fill=0,
                )
                continue

            draw.rectangle((x, y, x + w, y + h), fill=0)
            items = value[: slot.get("max_items", len(value))]
            noun = "THING" if len(value) == 1 else "THINGS"
            draw.text(
                (x + round(18 * scale_x), y + round(14 * scale_y)),
                f"{len(value)} {noun} NEED ATTENTION",
                font=attention_label,
                fill=255,
            )
            item_y = y + round(48 * scale_y)
            for item in items:
                draw.text(
                    (x + round(18 * scale_x), item_y),
                    item["title"],
                    font=attention_item,
                    fill=255,
                )
                item_y += round(26 * scale_y)
            continue

        if chrome == "line":
            draw.line((x, y, x + w, y), fill=0, width=2)

        label = _label_text(content, slot.get("label"))
        text_y = y + round((35 if label else 12) * scale_y)
        if label:
            draw.text(
                (x, y + round(9 * scale_y)),
                label,
                font=label_font,
                fill=0,
            )

        font = body if slot.get("style", {}).get("font_size", 14) >= 15 else body_small
        if isinstance(value, dict) and slot.get("fields"):
            _draw_pillow_fields(
                draw,
                (x + round(14 * scale_x), text_y),
                value,
                slot["fields"],
                w - round(28 * scale_x),
                (body, body_small, body_tiny),
            )
        else:
            text = _slot_text(value, slot.get("fields"), slot.get("max_items"))
            _draw_pillow_text(
                draw,
                (x + round(14 * scale_x), text_y),
                text,
                font,
                w - round(28 * scale_x),
            )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def render(content, layout, output_path):
    if Image is not None:
        _render_with_pillow(content, layout, output_path)
        return

    canvas_config = layout["canvas"]
    width = canvas_config["width"]
    height = canvas_config["height"]
    scale_x = width / canvas_config.get("design_width", width)
    scale_y = height / canvas_config.get("design_height", height)
    canvas = Canvas(width, height)

    for slot in layout["slots"]:
        raw_pos = slot["position"]
        pos = {
            "x": round(raw_pos["x"] * scale_x),
            "y": round(raw_pos["y"] * scale_y),
            "w": round(raw_pos["w"] * scale_x),
            "h": round(raw_pos["h"] * scale_y),
        }
        style = slot.get("style", {})
        value = _resolve(content, slot["source"])
        if value or slot["type"] != "attention":
            _draw_slot_chrome(canvas, slot, pos)
        size = style.get("font_size", 14)
        scale = 5 if slot["type"] == "hero" else 3 if size >= 18 else 2
        shade = 255 if style.get("chrome") == "solid" and value else 0

        if slot["type"] == "hero":
            canvas.text(pos["x"], pos["y"], str(value), scale, pos["w"] - 190)
            canvas.text(pos["x"] + pos["w"] - 178, pos["y"] + 8, _label_text(content, slot.get("label")), 2, 178)
            canvas.rect(pos["x"], pos["y"] + pos["h"] - 1, pos["w"], 1)
            continue

        if slot["type"] == "attention":
            text = attention_text(value, slot.get("max_items"))
        else:
            text = _slot_text(value, slot.get("fields"), slot.get("max_items"))

        label = _label_text(content, slot.get("label"))
        if label and slot["type"] != "attention":
            canvas.text(pos["x"], pos["y"] + 10, label, 2, pos["w"])
            text_y = pos["y"] + 34
        else:
            text_y = pos["y"] + 16

        line_width = max(10, (pos["w"] - 28) // (4 * scale))
        text = _wrap(text, line_width)
        canvas.text(pos["x"] + 14, text_y, text, scale, pos["w"] - 28, shade)

    canvas.save_png(output_path)


def main():
    root = Path(__file__).resolve().parents[1]
    content = json.loads((root / "content" / "latest.json").read_text())
    layout = load_layout(root / "renderer" / "layout.yaml")
    render(content, layout, root / "renderer" / "latest.png")


if __name__ == "__main__":
    main()
