"""Choose a weather- and calendar-aware outfit from known wardrobe items."""
import json

from ai._llm import MODEL, available, client, text_of


OUTFIT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "items": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
    "required": ["headline", "items", "reason"],
    "additionalProperties": False,
}

SYSTEM = (
    "You are a professional fashion stylist assembling one cohesive outfit from the "
    "client's actual wardrobe. Use ONLY the provided item names — never invent an item.\n"
    "Style like a stylist, not a checklist:\n"
    "- Palette: build on a neutral base (1-2 neutrals) and add at most ONE accent colour. "
    "Keep colours harmonious — analogous or a considered complementary pop; never two "
    "competing brights. Earth tones (olive/tan/brown) pair together; navy and grey are "
    "safe anchors.\n"
    "- Contrast & depth: balance light and dark values so the outfit isn't flat; an all-"
    "tonal look is fine only if deliberate (e.g. layered greys).\n"
    "- Pattern: at most one patterned piece; everything else solid.\n"
    "- Texture: avoid stacking multiple statement textures (e.g. quilted + tweed + ribbed); "
    "use one textured focus and let smoother pieces support it.\n"
    "- Proportion & layering: a complete look is top + bottom + shoes; add a mid-layer or "
    "outerwear only when warmth or rain calls for it. Don't stack two bulky layers.\n"
    "- Accessories: include at most one bag.\n"
    "- Register: keep every piece in one formality lane — today's intent decides it "
    "(office/dress_to_impress leans 'smart casual'; work_from_home/off is 'casual'). Each "
    "item's 'formality' lists the settings it suits.\n"
    "- Weather: weight warmth/thickness/material to the temperature; prefer rain_ok pieces "
    "when rain is likely, but don't force puffers or boots for mild 'rain later'. Avoid "
    "'worn'-condition items when dressing to impress.\n"
    "- Cozy home means soft, comfortable, home-appropriate clothes; avoid jeans, stiff "
    "trousers, office shoes, and dresses unless explicitly anchored.\n"
    "Return a short evocative headline, 3-5 exact item names, and one tight reason that "
    "names the occasion and explains WHY the pieces work together (the colour/texture logic)."
)


def _formality_ok(item, target):
    """Formality may be a scalar (legacy) or a list of suitable settings."""
    value = item.get("formality")
    if isinstance(value, list):
        return target in value
    return value == target


def _anchor_name(anchor, wardrobe_items):
    """Resolve an anchor (a piece name or id) to the wardrobe item's exact name."""
    if not anchor:
        return None
    for item in wardrobe_items:
        if anchor in (item.get("name"), item.get("id")):
            return item.get("name")
    return None


def _anchor_item(anchor, wardrobe_items):
    if not anchor:
        return None
    for item in wardrobe_items:
        if anchor in (item.get("name"), item.get("id")):
            return item
    return None


def _anchor_items(request, wardrobe_items):
    anchors = []
    for anchor in (request or {}).get("anchors") or []:
        item = _anchor_item(anchor, wardrobe_items)
        if item:
            anchors.append(item)
    single = _anchor_item((request or {}).get("anchor"), wardrobe_items)
    if single:
        anchors.append(single)
    seen = set()
    result = []
    for item in anchors:
        key = item.get("name")
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


FORMALITY_RANK = {"athletic": 0, "casual": 1, "smart casual": 2, "business": 3, "formal": 4}
UPPER_CATEGORIES = {"top", "blouse", "knit"}
LAYER_CATEGORIES = {"midlayer", "cardigan"}
LOWER_CATEGORIES = {"bottom", "pants", "jeans", "skirt", "shorts"}
BAG_CATEGORIES = {"bag"}
BOOT_WORDS = ("boot", "boots")
PUFFER_WORDS = ("puffer", "down/synthetic fill", "synthetic fill")
COZY_WORDS = ("fleece", "sweat", "soft", "slipper", "ugg", "jersey")
TEXTURE_WORDS = ("ribbed", "quilted", "tweed", "suede", "velvet", "shearling", "ruffle", "cable", "chunky", "floral", "gingham", "striped")


def _category_in(item, categories):
    return item.get("category") in categories


def _best_formality_rank(item):
    value = item.get("formality")
    values = value if isinstance(value, list) else [value]
    ranks = [FORMALITY_RANK[v] for v in values if v in FORMALITY_RANK]
    return max(ranks) if ranks else 1


def _target_warmth(high):
    high = high if isinstance(high, (int, float)) else 18
    if high <= 10:
        return 5
    if high <= 14:
        return 4
    if high <= 19:
        return 3
    if high <= 24:
        return 2
    return 1


def _style_tokens(request):
    text = " ".join(
        str((request or {}).get(key, ""))
        for key in ("style_notes", "instructions", "occasion")
    ).lower()
    return {
        "elegant": any(word in text for word in ("elegant", "classy", "polished", "refined")),
        "casual": any(word in text for word in ("cozy", "casual", "relaxed")),
    }


def _text_fields(item):
    return " ".join(
        str(item.get(key, ""))
        for key in ("name", "subtype", "material", "texture")
    ).lower()


def _is_boot(item):
    return any(word in _text_fields(item) for word in BOOT_WORDS)


def _is_puffer(item):
    return any(word in _text_fields(item) for word in PUFFER_WORDS)


def _is_cozy(item):
    text = _text_fields(item)
    return any(word in text for word in COZY_WORDS) or "home" in item.get("best_for", [])


def _texture_weight(item):
    text = _text_fields(item)
    value = 0
    for word in TEXTURE_WORDS:
        if word in text or item.get("pattern") == word:
            value += 1
    if item.get("pattern") and item.get("pattern") != "solid":
        value += 1
    return value


def _color_family(color):
    color = str(color).lower()
    for family, words in {
        "black": ("black", "charcoal"),
        "white": ("white", "cream", "ivory", "natural", "off-white", "oatmeal"),
        "brown": ("brown", "camel", "tan", "taupe", "beige", "chestnut"),
        "blue": ("blue", "navy", "denim"),
        "grey": ("grey", "gray", "silver"),
        "red": ("red", "burgundy", "rose", "pink", "blush"),
        "green": ("green", "olive", "sage", "lime"),
    }.items():
        if any(word in color for word in words):
            return family
    return color


def _style_penalty(items):
    penalty = 0
    colors = []
    textured = 0
    bags = 0
    for item in items:
        if not item:
            continue
        if item.get("category") == "bag":
            bags += 1
        colors.extend(_color_family(color) for color in item.get("colors", [])[:2])
        textured += 1 if _texture_weight(item) >= 2 else 0
    accents = {c for c in colors if c not in {"black", "white", "brown", "grey", "blue"}}
    if len(accents) > 1:
        penalty += (len(accents) - 1) * 4
    if textured > 1:
        penalty += (textured - 1) * 3
    if bags > 1:
        penalty += (bags - 1) * 20
    return penalty


def _slot(item):
    category = (item or {}).get("category")
    if category in UPPER_CATEGORIES:
        return "upper"
    if category in LAYER_CATEGORIES or category == "outerwear":
        return "layer"
    if category in LOWER_CATEGORIES:
        return "lower"
    if category == "dress":
        return "body"
    if category == "shoes":
        return "shoes"
    if category == "bag":
        return "bag"
    return category


def fallback_outfit(weather, wardrobe_items, calendar=None, context=None, request=None):
    calendar = calendar or []
    context = context or {}
    wants_rain = weather.get("condition") in {"rain_later", "rain_likely", "storm"}
    smart_casual = any(event.get("dress_code") == "smart casual" for event in calendar)
    athletic_events = [event for event in calendar if event.get("dress_code") == "athletic"]
    office_day = context.get("work_mode") == "office" or context.get("intent") == "work"
    dress_to_impress = context.get("intent") == "dress_to_impress" or office_day
    recent = set((request or {}).get("recent") or [])
    requested_formality = (request or {}).get("formality_hint")
    style = _style_tokens(request)
    variety = bool((request or {}).get("variety"))
    cozy_home = (request or {}).get("occasion") == "cozy home"
    condition = weather.get("condition", "weather").replace("_", " ")
    target_warmth = _target_warmth(weather.get("high"))
    temperature_note = "mild temperature"
    if weather.get("high", 0) <= 14:
        temperature_note = "cool day"
    elif weather.get("high", 0) >= 26:
        temperature_note = "warm day"

    def score(item, formality=None):
        value = 0
        if item.get("name") in recent:
            value -= 5  # rotate away from recently worn pieces
        if formality and _formality_ok(item, formality):
            value += 6
        if formality in FORMALITY_RANK:
            value -= abs(_best_formality_rank(item) - FORMALITY_RANK[formality])
        if item.get("polish") is not None and formality in FORMALITY_RANK:
            value -= abs(int(item.get("polish", 2)) - (FORMALITY_RANK[formality] + 1))
        if item.get("warmth") is not None:
            value -= abs(int(item.get("warmth", target_warmth)) - target_warmth)
        if item.get("wear_frequency") is not None:
            value += int(item.get("wear_frequency", 3)) - 3
        if item.get("avoid_often"):
            value -= 5
        if athletic_events:
            if _formality_ok(item, "athletic"):
                value += 2
        elif _formality_ok(item, "athletic") and not _formality_ok(item, "casual"):
            value -= 5
        if dress_to_impress and "dress_to_impress" in item.get("style_tags", []):
            value += 3
        if office_day and "office" in item.get("best_for", []):
            value += 2
        if office_day and item.get("office_ok") is True:
            value += 3
        if office_day and item.get("office_ok") is False:
            value -= 5
        if context.get("occasion") and context["occasion"] in item.get("best_for", []):
            value += 2
        if style["elegant"]:
            text = _text_fields(item)
            if item.get("neutral"):
                value += 1
            if item.get("category") in {"blouse", "pants", "skirt", "dress", "bag"}:
                value += 1
            if any(word in text for word in ("leather", "silk", "tailored", "wool", "quilted")):
                value += 2
            if any(word in text for word in ("canvas", "sweatshirt", "sweatpants", "puffer")):
                value -= 2
            if item.get("pattern") == "graphic":
                value -= 3
        if item.get("category") == "outerwear" and _is_puffer(item):
            value -= 4 if target_warmth < 4 else 1
        if item.get("category") == "shoes" and _is_boot(item):
            value -= 3 if target_warmth < 4 else 1
        if cozy_home:
            if _is_cozy(item):
                value += 6
            if item.get("comfort") is not None:
                value += int(item.get("comfort", 3)) - 2
            if item.get("home_ok") is True:
                value += 5
            if item.get("home_ok") is False:
                value -= 8
            if item.get("category") in {"jeans", "dress"}:
                value -= 8
            if item.get("category") == "shoes" and not _is_cozy(item):
                value -= 4
        if (
            item.get("category") in {"bottom", "shorts"}
            and "short" in item.get("subtype", "").lower()
            and weather.get("high", 0) < 24
        ):
            value -= 3
        return value

    def first(categories, *, rain_ok=None, formality=None):
        categories = {categories} if isinstance(categories, str) else set(categories)
        matches = []
        for item in wardrobe_items:
            if item.get("category") not in categories:
                continue
            if rain_ok is not None and item.get("rain_ok") != rain_ok:
                continue
            matches.append(item)
        if not matches:
            return None
        matches.sort(key=lambda item: score(item, formality), reverse=True)
        best = matches[1] if variety and len(matches) > 1 else matches[0]
        if formality and not _formality_ok(best, formality) and score(best, formality) == 0:
            return None
        return best["name"]

    formality = requested_formality or ("smart casual" if smart_casual or dress_to_impress else "casual")
    dressy_rank = FORMALITY_RANK.get(formality, 1)
    layer_needed = target_warmth >= 4

    anchor_items = _anchor_items(request, wardrobe_items)
    anchor_item = anchor_items[0] if anchor_items else None
    dress_occasion = (request or {}).get("occasion") in {"dressy", "going out", "formal"}
    dress_allowed = dress_occasion or formality == "formal" or (
        anchor_item and anchor_item.get("category") == "dress"
    )
    dress = first("dress", formality=formality) if dress_allowed else None
    items = []
    rain_layer_required = weather.get("condition") in {"rain_likely", "storm"} or target_warmth >= 4
    if wants_rain and rain_layer_required:
        items.append(first("outerwear", rain_ok=True, formality=formality) or first("outerwear", rain_ok=True))
    elif layer_needed:
        items.append(first(LAYER_CATEGORIES | {"outerwear"}, formality=formality))

    if dress:
        items.append(dress)
    else:
        items.extend([
            first(UPPER_CATEGORIES, formality=formality) or first(UPPER_CATEGORIES),
            first(LOWER_CATEGORIES, formality=formality) or first(LOWER_CATEGORIES),
        ])

    items.append(
        first("shoes", rain_ok=True, formality=formality) or first("shoes", formality=formality)
        if weather.get("condition") in {"rain_likely", "storm"}
        else first("shoes", formality=formality)
    )
    if dressy_rank >= FORMALITY_RANK["smart casual"]:
        items.append(first(BAG_CATEGORIES, formality=formality) or first(BAG_CATEGORIES))
    items = [item for item in items if item]

    by_name = {item.get("name"): item for item in wardrobe_items}
    anchored = []
    used_bag = False
    for item in anchor_items:
        if item.get("category") == "bag":
            if used_bag:
                continue
            used_bag = True
        anchored.append(item.get("name"))
    chosen = anchored + [name for name in items if name not in anchored]
    final = []
    used_categories = set()
    used_slots = set()
    used_bag = False
    anchored_names = set(anchored)
    for name in chosen:
        item = by_name.get(name)
        if not item:
            continue
        category = item.get("category")
        slot = _slot(item)
        if category == "bag":
            if used_bag:
                continue
            used_bag = True
        if slot in used_slots and name not in anchored_names:
            continue
        if category in {"dress"} and any(by_name.get(n, {}).get("category") in LOWER_CATEGORIES for n in final):
            continue
        if category in UPPER_CATEGORIES and any(by_name.get(n, {}).get("category") == "dress" for n in final):
            continue
        if category in LOWER_CATEGORIES and any(by_name.get(n, {}).get("category") == "dress" for n in final):
            continue
        final.append(name)
        used_categories.add(category)
        used_slots.add(slot)
        if len(final) >= 5:
            break
    if _style_penalty([by_name.get(name) for name in final]) >= 8:
        final = [name for name in final if _texture_weight(by_name.get(name, {})) < 2 or name in anchored]
    items = final

    headline = "Rain-ready casual" if wants_rain else "Easy casual layers"
    calendar_note = "smart casual calendar" if smart_casual else "casual calendar"
    if smart_casual:
        headline = "Smart casual layers"
    elif office_day:
        headline = "Office polish"
        calendar_note = "office day, dress to impress"
    athletic_note = ""
    if athletic_events:
        athletic_note = f" Bring athletic kit for {athletic_events[0]['title']}."

    return {
        "headline": headline,
        "items": items,
        "reason": (
            f"{condition.capitalize()}, {temperature_note}, {calendar_note}."
            f"{athletic_note}"
        ),
    }


_KEEP = ("name", "id", "category", "subtype", "colors", "neutral", "formality",
         "warmth", "rain_ok", "condition", "pattern", "material", "texture",
         "polish", "comfort", "home_ok", "office_ok", "wear_frequency", "avoid_often")


def _compact(wardrobe_items):
    """Trim each item to the fields the stylist needs — smaller, faster prompts."""
    return [{k: it[k] for k in _KEEP if k in it} for it in wardrobe_items]


def valid_outfit(outfit, wardrobe_items):
    known = {item["name"] for item in wardrobe_items}
    by_name = {item["name"]: item for item in wardrobe_items}
    bags = [item for item in outfit.get("items", []) if by_name.get(item, {}).get("category") == "bag"]
    return (
        isinstance(outfit, dict)
        and isinstance(outfit.get("headline"), str)
        and isinstance(outfit.get("reason"), str)
        and isinstance(outfit.get("items"), list)
        and 2 <= len(outfit["items"]) <= 5
        and all(isinstance(item, str) and item in known for item in outfit["items"])
        and len(bags) <= 1
    )


def generate_outfit(weather, wardrobe_items, calendar=None, context=None, request=None):
    calendar = calendar or []
    context = context or {}
    request = request or {}

    avoid = set(request.get("avoid") or [])
    usable = [w for w in wardrobe_items if w.get("name") not in avoid]
    fallback = fallback_outfit(weather, usable, calendar, context, request)
    if not available():
        return fallback

    anchors = [item.get("name") for item in _anchor_items(request, usable)]
    anchor = _anchor_name(request.get("anchor"), usable)
    system_text = SYSTEM
    if request.get("instructions"):
        system_text += "\nWearer preferences for today: " + request["instructions"]
    if anchor:
        system_text += f"\nYou MUST build the outfit around this exact item and include it: {anchor}."
    if anchors:
        system_text += "\nInclude these anchor items if they can coexist in one styled outfit: " + ", ".join(anchors) + "."

    try:
        payload = {
            "weather": weather,
            "calendar": calendar,
            "context": context,
            "request": request,
            "wardrobe": _compact(usable),
        }
        response = client().messages.create(
            model=MODEL,
            max_tokens=260,
            output_config={"format": {"type": "json_schema", "schema": OUTFIT_SCHEMA}},
            system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        outfit = json.loads(text_of(response))
        if not valid_outfit(outfit, usable):
            return fallback
        required_anchors = [name for name in anchors if name not in outfit["items"]]
        if anchor and anchor not in outfit["items"]:
            return fallback  # anchor is non-negotiable
        if required_anchors and not any(name in fallback["items"] for name in required_anchors):
            return fallback
        return outfit
    except Exception:
        return fallback
