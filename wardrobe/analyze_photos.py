import argparse
import base64
import json
from pathlib import Path

from ai._llm import MODEL, available, client, text_of


ALLOWED_FIELDS = {
    "name",
    "category",
    "colors",
    "warmth",
    "rain_ok",
    "wind_ok",
    "formality",
    "style_tags",
    "material_guess",
    "texture",
    "thickness",
    "fit",
    "best_for",
    "avoid_for",
    "confidence",
    "notes",
}

MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "category": {"type": "string"},
        "colors": {"type": "array", "items": {"type": "string"}},
        "warmth": {"type": "string"},
        "rain_ok": {"type": "boolean"},
        "wind_ok": {"type": "boolean"},
        "formality": {"type": "string"},
        "style_tags": {"type": "array", "items": {"type": "string"}},
        "material_guess": {"type": "string"},
        "texture": {"type": "string"},
        "thickness": {"type": "string"},
        "fit": {"type": "string"},
        "best_for": {"type": "array", "items": {"type": "string"}},
        "avoid_for": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string"},
        "notes": {"type": "string"},
    },
    "additionalProperties": False,
}

SYSTEM = (
    "Analyze one garment photo for a personal wardrobe catalog. Infer only what "
    "the image supports. If fit, material, warmth, or condition is uncertain, say "
    "so in notes and use low confidence. Return JSON only."
)


def image_content_block(path):
    path = Path(path)
    media_type = MEDIA_TYPES.get(path.suffix.lower())
    if not media_type:
        raise ValueError(f"Unsupported image type: {path.suffix}")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": data,
        },
    }


def merge_analysis(record, analysis):
    merged = dict(record)
    for key, value in analysis.items():
        if key in ALLOWED_FIELDS:
            merged[key] = value
    merged["review_status"] = "ai_reviewed"
    return merged


def analyze_record(record, root):
    image_path = root / record["image"]
    response = client().messages.create(
        model=MODEL,
        max_tokens=420,
        output_config={
            "format": {
                "type": "json_schema",
                "schema": ANALYSIS_SCHEMA,
            }
        },
        system=[
            {
                "type": "text",
                "text": SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe this garment for outfit recommendations. "
                            f"Existing draft: {json.dumps(record, ensure_ascii=False)}"
                        ),
                    },
                    image_content_block(image_path),
                ],
            }
        ],
    )
    return merge_analysis(record, json.loads(text_of(response)))


def analyze_drafts(drafts=None, output=None, limit=None):
    root = Path(__file__).resolve().parents[1]
    drafts = Path(drafts) if drafts else root / "wardrobe" / "drafts.json"
    output = Path(output) if output else drafts

    if not available():
        raise RuntimeError("Claude is not configured or MD_OFFLINE=1 is set.")

    records = json.loads(drafts.read_text())
    analyzed = []
    for record in records:
        if limit is not None and len(analyzed) >= limit:
            analyzed.extend(records[len(analyzed):])
            break
        try:
            analyzed.append(analyze_record(record, root))
        except Exception as exc:
            failed = dict(record)
            failed["analysis_error"] = str(exc)
            analyzed.append(failed)

    output.write_text(json.dumps(analyzed, indent=2) + "\n")
    return analyzed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    records = analyze_drafts(limit=args.limit)
    print(f"Analyzed {len(records)} wardrobe draft item(s)")


if __name__ == "__main__":
    main()
