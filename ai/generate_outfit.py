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
    "- Proportion & layering: a complete look is top + bottom + shoes; add layers only when "
    "warmth or rain calls for them. The stack runs base (thin top) -> mid (sweater/cardigan) "
    "-> outer (coat). On a cool day, reaching the target warmth by combining TWO lighter "
    "layers (e.g. a thin top under a knit, or a knit under a coat) is often better and more "
    "polished than one heavy piece. But only nest pieces that physically fit: never put a "
    "chunky/thick knit under a slim or tailored jacket, never stack two thick/bulky pieces, "
    "and don't layer a voluminous or ruffled top under a fitted layer (it bulks and pokes "
    "through). Use each item's thickness, sleeve and fit_notes to judge what nests.\n"
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
# Layering stack: base (worn against skin) -> mid (sweater/cardigan) -> outer (coat).
BASE_CATEGORIES = {"top", "blouse", "dress"}
MID_CATEGORIES = {"knit", "cardigan", "midlayer"}
BOOT_WORDS = ("boot", "boots")
PUFFER_WORDS = ("puffer", "down/synthetic fill", "synthetic fill")
COZY_WORDS = ("fleece", "sweat", "soft", "slipper", "ugg", "jersey")
TEXTURE_WORDS = ("ribbed", "quilted", "tweed", "suede", "velvet", "shearling", "ruffle", "cable", "chunky", "floral", "gingham", "striped")
BULK_WORDS = ("chunky", "cable", "fleece", "quilted", "puffer", "shearling", "sherpa", "fluffy", "down")
FITTED_WORDS = ("tailored", "slim", "fitted", "blazer", "structured", "slim-fit")
VOLUMINOUS_WORDS = ("ruffle", "puff", "balloon", "peplum", "cape", "voluminous", "tiered", "bishop")
_THICKNESS = {"thin": 1, "medium": 2, "thick": 3}


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


def _layer_role(item):
    """Where a torso piece sits in the stack: base < mid < outer (None if not torso)."""
    category = (item or {}).get("category")
    if category in BASE_CATEGORIES:
        return "base"
    if category in MID_CATEGORIES:
        return "mid"
    if category == "outerwear":
        return "outer"
    return None


def _thickness(item):
    return _THICKNESS.get((item or {}).get("thickness"), 2)


def _bulk(item):
    """Coarse volume 1-3 — heavy textures read thick even if 'thickness' says otherwise."""
    value = _thickness(item)
    if any(word in _text_fields(item) for word in BULK_WORDS):
        value = max(value, 3)
    return value


def _is_fitted(item):
    text = _text_fields(item) + " " + str((item or {}).get("fit_notes", "")).lower()
    return any(word in text for word in FITTED_WORDS)


def _can_nest(inner, outer):
    """True if `inner` can be worn under `outer` without bulk or poke-through problems."""
    inner_bulk, outer_bulk = _bulk(inner), _bulk(outer)
    if inner_bulk == 3 and _is_fitted(outer):
        return False  # chunky piece won't fit under a slim/tailored layer
    if inner_bulk == 3 and outer_bulk == 3:
        return False  # two thick layers don't nest
    if _is_fitted(outer) and any(w in _text_fields(inner) for w in VOLUMINOUS_WORDS):
        return False  # ruffles/volume bulk and poke out under a fitted outer
    return True


def _warmth(item):
    value = (item or {}).get("warmth")
    return int(value) if isinstance(value, (int, float)) else 2


def _stack_warmth(items):
    """Combined torso warmth — each extra layer adds less (two thin can rival one thick)."""
    warmths = sorted((_warmth(i) for i in items if i and _layer_role(i)), reverse=True)
    total, factor = 0.0, 1.0
    for warmth in warmths:
        total += warmth * factor
        factor *= 0.6
    return total


def _slot(item):
    category = (item or {}).get("category")
    if category == "dress":
        return "body"
    role = _layer_role(item)
    if role:
        return role  # base / mid / outer — distinct so a full stack can coexist
    if category in LOWER_CATEGORIES:
        return "lower"
    if category == "shoes":
        return "shoes"
    if category == "bag":
        return "bag"
    return category


def _complete_slots(items):
    slots = {_slot(item) for item in items if item}
    torso = bool(slots & {"base", "mid", "body"})
    covered = "body" in slots or (torso and "lower" in slots)
    return covered and "shoes" in slots


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
    by_name = {item.get("name"): item for item in wardrobe_items}

    anchor_items = _anchor_items(request, wardrobe_items)
    anchor_item = anchor_items[0] if anchor_items else None
    dress_occasion = (request or {}).get("occasion") in {"dressy", "going out", "formal"}
    dress_allowed = dress_occasion or formality == "formal" or (
        anchor_item and anchor_item.get("category") == "dress"
    )
    dress = first("dress", formality=formality) if dress_allowed else None

    def _pick(categories, *, rain_ok=None, nest_over=None, exclude=None):
        cats = {categories} if isinstance(categories, str) else set(categories)
        exclude = exclude or set()
        cands = []
        for item in wardrobe_items:
            if item.get("category") not in cats or item.get("name") in exclude:
                continue
            if rain_ok is not None and item.get("rain_ok") != rain_ok:
                continue
            if nest_over and not all(_can_nest(inner, item) for inner in nest_over):
                continue
            cands.append(item)
        if not cands:
            return None
        cands.sort(key=lambda item: score(item, formality), reverse=True)
        return cands[1] if variety and len(cands) > 1 else cands[0]

    # Torso stack: base -> optional mid -> optional outer, layered up until it clears
    # the day's target warmth. Two lighter layers can beat one heavy piece, and every
    # added layer is checked so it physically nests (no chunky knit under a slim coat).
    items = []
    layer_needed = target_warmth >= 4  # only stack extra torso layers when it's genuinely cool
    rain_layer_required = weather.get("condition") in {"rain_likely", "storm"} or target_warmth >= 4
    if dress:
        torso = [by_name.get(dress)]
    else:
        torso = [item for item in anchor_items if _layer_role(item)]
        if not any(_layer_role(item) == "base" for item in torso):
            base = _pick(UPPER_CATEGORIES, exclude={i.get("name") for i in torso})
            if base:
                torso.append(base)

    def warm_enough():
        return _stack_warmth(torso) >= target_warmth

    def has_role(role):
        return any(_layer_role(item) == role for item in torso if item)

    if wants_rain and rain_layer_required and not has_role("outer"):
        shell = _pick("outerwear", rain_ok=True, nest_over=[i for i in torso if i]) or _pick(
            "outerwear", rain_ok=True
        )
        if shell:
            torso.append(shell)
    if layer_needed and not warm_enough() and not has_role("mid"):
        mids = {"cardigan"} if any(i and i.get("category") == "knit" for i in torso) else MID_CATEGORIES
        mid = _pick(
            mids,
            nest_over=[i for i in torso if i and _layer_role(i) == "base"],
            exclude={i.get("name") for i in torso if i},
        )
        if mid:
            torso.append(mid)
    if layer_needed and not warm_enough() and not has_role("outer"):
        outer = _pick("outerwear", nest_over=[i for i in torso if i],
                      exclude={i.get("name") for i in torso if i})
        if outer:
            torso.append(outer)

    items.extend(item.get("name") for item in torso if item)
    if not dress:
        lower = first(LOWER_CATEGORIES, formality=formality) or first(LOWER_CATEGORIES)
        if lower:
            items.append(lower)

    items.append(
        first("shoes", rain_ok=True, formality=formality) or first("shoes", formality=formality)
        if weather.get("condition") in {"rain_likely", "storm"}
        else first("shoes", formality=formality)
    )
    if dressy_rank >= FORMALITY_RANK["smart casual"]:
        items.append(first(BAG_CATEGORIES, formality=formality) or first(BAG_CATEGORIES))
    items = [item for item in items if item]

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
        if len(final) >= 6:
            break
    if _style_penalty([by_name.get(name) for name in final]) >= 8:
        final = [
            name for name in final
            if _texture_weight(by_name.get(name, {})) < 2
            or name in anchored
            or _slot(by_name.get(name)) in {"base", "mid", "outer", "lower", "body", "shoes"}
        ]

    def make_room(names):
        if len(names) < 6:
            return names
        for removable_slot in ("accessory", "bag", "outer", "mid"):
            for idx, name in enumerate(names):
                if _slot(by_name.get(name)) == removable_slot:
                    return names[:idx] + names[idx + 1:]
        return names[:-1]

    def add_required(names, categories):
        existing_slots = {_slot(by_name.get(name)) for name in names}
        candidate = first(categories, formality=formality) or first(categories)
        if not candidate or candidate in names:
            return names
        slot = _slot(by_name.get(candidate))
        if slot in existing_slots:
            return names
        names = make_room(names)
        names.append(candidate)
        return names

    if not _complete_slots([by_name.get(name) for name in final]):
        slots = {_slot(by_name.get(name)) for name in final}
        if "body" not in slots:
            if not (slots & {"base", "mid"}):
                final = add_required(final, UPPER_CATEGORIES)
            if "lower" not in slots:
                final = add_required(final, LOWER_CATEGORIES)
        if "shoes" not in {_slot(by_name.get(name)) for name in final}:
            final = add_required(final, "shoes")
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
         "warmth", "thickness", "sleeve", "fit_notes", "rain_ok", "condition",
         "pattern", "material", "texture", "polish", "comfort", "home_ok",
         "office_ok", "wear_frequency", "avoid_often")


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
        and 2 <= len(outfit["items"]) <= 6
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

    # Stable prefix (styling rules + wardrobe) is cached so rapid adjustments — warmer,
    # dressier, surprise-me — reuse it instead of re-sending 100+ items each tap.
    system_blocks = [
        {"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}},
        {
            "type": "text",
            "text": "Client wardrobe — choose ONLY from these exact item names:\n"
            + json.dumps(_compact(usable), ensure_ascii=False),
            "cache_control": {"type": "ephemeral"},
        },
    ]
    directives = []
    if request.get("instructions"):
        directives.append("Wearer preferences for today: " + request["instructions"])
    if anchor:
        directives.append(f"You MUST build the outfit around this exact item and include it: {anchor}.")
    if anchors:
        directives.append("Include these anchor items if they can coexist in one styled outfit: " + ", ".join(anchors) + ".")
    if directives:
        system_blocks.append({"type": "text", "text": "\n".join(directives)})

    try:
        payload = {
            "weather": weather,
            "calendar": calendar,
            "context": context,
            "request": request,
        }
        response = client().messages.create(
            model=MODEL,
            max_tokens=260,
            output_config={"format": {"type": "json_schema", "schema": OUTFIT_SCHEMA}},
            system=system_blocks,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        outfit = json.loads(text_of(response))
        if not valid_outfit(outfit, usable):
            return fallback
        required_anchors = [name for name in anchors if name not in outfit["items"]]
        if anchor and anchor not in outfit["items"]:
            return fallback  # anchor is non-negotiable
        if required_anchors:
            return fallback  # the fallback force-includes every anchor
        return outfit
    except Exception:
        return fallback
