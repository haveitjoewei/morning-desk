import json

from ai.style_request import build_request, effective_high


def test_cold_and_warmer_lower_the_effective_temperature():
    assert effective_high(18, {"runs_cold": True}, {"temp_nudge": "warmer"}) == 13


def test_lighter_raises_effective_temperature():
    assert effective_high(18, {}, {"temp_nudge": "lighter"}) == 21


def test_request_carries_anchor_and_wish_and_occasion():
    r = build_request(
        {"style_notes": "soft neutrals", "love_colors": ["sage"]},
        {"occasion": "going out", "anchor": "green-cardigan", "wish": "something flowy"},
    )
    assert r["anchor"] == "green-cardigan"
    assert "smart casual" in r["formality_hint"]
    assert "something flowy" in r["instructions"]
    assert "soft neutrals" in r["instructions"]
    assert "sage" in r["instructions"]


def test_request_carries_multiple_anchors():
    r = build_request({}, {"anchors": ["green-cardigan", "loafers"]})
    assert r["anchors"] == ["green-cardigan", "loafers"]


def test_runs_cold_flag_and_default_occasion():
    r = build_request({"runs_cold": True}, {})
    assert r["runs_cold"] is True
    assert r["occasion"] == "casual"
    assert "thicker layers" in r["instructions"]


def test_fallback_outfit_includes_anchor_item():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 11}
    wardrobe = [
        {"name": "green cardigan", "category": "cardigan", "formality": ["casual", "smart casual"]},
        {"name": "white tee", "category": "top", "formality": ["casual"]},
        {"name": "blue jeans", "category": "bottom", "formality": ["casual"]},
        {"name": "white sneakers", "category": "shoes", "formality": ["casual"]},
    ]
    out = generate_outfit(weather, wardrobe, calendar=[], context={},
                          request={"anchor": "green cardigan", "instructions": "", "formality_hint": "casual"})
    assert "green cardigan" in out["items"]


def test_plan_outfit_for_profile_returns_pieces(tmp_path, monkeypatch):
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    monkeypatch.setenv("MD_OFFLINE", "1")
    d = tmp_path / "eve"
    d.mkdir()
    (d / "items.json").write_text('[{"name":"Red Dress","id":"red-dress","category":"dress","formality":["smart casual"],"warmth":2}]')
    (d / "config.json").write_text('{"categories":"womenswear","location":{"latitude":-33.8,"longitude":151.2,"timezone":"Australia/Sydney"}}')
    from core.outfit import plan_outfit
    result = plan_outfit("eve", prefs={}, day={"occasion": "dressy"})
    assert "headline" in result and "pieces" in result and "weather" in result


def test_plan_outfit_uses_profile_default_prefs(tmp_path, monkeypatch):
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    monkeypatch.setenv("MD_OFFLINE", "1")
    d = tmp_path / "eve"
    d.mkdir()
    (d / "items.json").write_text(json.dumps([
        {"name": "logo sweatshirt", "id": "logo", "category": "knit", "formality": ["smart casual"], "warmth": 2, "pattern": "graphic"},
        {"name": "silk blouse", "id": "silk", "category": "blouse", "formality": ["smart casual"], "warmth": 1, "material": "silk", "neutral": True},
        {"name": "black trousers", "id": "trousers", "category": "pants", "formality": ["smart casual"], "warmth": 2, "neutral": True},
        {"name": "loafers", "id": "loafers", "category": "shoes", "formality": ["smart casual"], "warmth": 1, "neutral": True},
    ]))
    (d / "config.json").write_text('{"categories":"womenswear","location":{"latitude":-33.8,"longitude":151.2,"timezone":"Australia/Sydney"}}')
    (d / "prefs.json").write_text('{"style_notes":"elegant classy"}')
    from core.outfit import plan_outfit

    result = plan_outfit("eve", prefs={}, day={"occasion": "work"})

    assert "silk blouse" in result["items"]
    assert "logo sweatshirt" not in result["items"]


def test_continuous_temp_step_warmer():
    # two "warmer" steps -> dress for 4C cooler
    assert effective_high(18, {}, {"temp_step": -2}) == 14


def test_dress_step_makes_it_dressier():
    r = build_request({}, {"occasion": "work", "dress_step": 1})
    assert r["formality_hint"] == "business"
    r2 = build_request({}, {"occasion": "casual", "dress_step": -1})
    assert r2["formality_hint"] == "casual"  # clamped at floor


def test_rejection_excludes_item_and_explains():
    r = build_request({}, {"rejections": [{"item": "linen shirt", "reason": "too cold"}]})
    assert "linen shirt" in r["avoid"]
    assert "too cold" in r["instructions"]


def test_generate_outfit_never_picks_avoided_item():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 11}
    wardrobe = [
        {"name": "white tee", "category": "top", "formality": ["casual"]},
        {"name": "grey tee", "category": "top", "formality": ["casual"]},
        {"name": "blue jeans", "category": "bottom", "formality": ["casual"]},
        {"name": "white sneakers", "category": "shoes", "formality": ["casual"]},
    ]
    out = generate_outfit(weather, wardrobe, request={"avoid": ["white tee"], "instructions": "", "formality_hint": "casual"})
    assert "white tee" not in out["items"]


def test_recent_store_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    (tmp_path / "p").mkdir()
    from core.recent import record, recent_items
    record("p", "2026-06-28", ["a", "b"])
    record("p", "2026-06-29", ["b", "c"])
    assert set(recent_items("p", exclude_date="2026-06-29", days=5)) == {"a", "b"}


def test_request_includes_rules_and_recent():
    r = build_request({"rules": ["prefer sweats when home and cool"]}, {"recent": ["tan sneakers"]})
    assert "prefer sweats" in r["instructions"]
    assert "tan sneakers" in r["instructions"]
    assert r["recent"] == ["tan sneakers"]


def test_request_exposes_style_notes_for_fallback():
    r = build_request({"style_notes": "elegant classy"}, {})
    assert r["style_notes"] == "elegant classy"


def test_fallback_rotates_away_from_recent():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 11}
    wardrobe = [
        {"name": "tan sneakers", "category": "shoes", "formality": ["casual"]},
        {"name": "white sneakers", "category": "shoes", "formality": ["casual"]},
        {"name": "tee", "category": "top", "formality": ["casual"]},
        {"name": "jeans", "category": "bottom", "formality": ["casual"]},
    ]
    out = generate_outfit(weather, wardrobe, request={"recent": ["tan sneakers"], "instructions": "", "formality_hint": "casual"})
    assert "white sneakers" in out["items"] and "tan sneakers" not in out["items"]


def test_womenswear_fallback_includes_lower_body_piece():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "rain_later", "high": 18, "low": 12}
    wardrobe = [
        {"name": "cream puffer", "category": "outerwear", "formality": ["casual"], "rain_ok": True, "warmth": 4},
        {"name": "grey top", "category": "top", "formality": ["casual"], "warmth": 2},
        {"name": "camel skirt", "category": "skirt", "formality": ["casual", "smart casual"], "warmth": 2},
        {"name": "black boots", "category": "shoes", "formality": ["casual"], "warmth": 2},
    ]

    out = generate_outfit(weather, wardrobe, request={"formality_hint": "casual"})

    assert "camel skirt" in out["items"]


def test_warmer_step_prefers_warmer_piece():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 12, "low": 8}
    wardrobe = [
        {"name": "thin tee", "category": "top", "formality": ["casual"], "warmth": 1},
        {"name": "warm knit", "category": "knit", "formality": ["casual"], "warmth": 4},
        {"name": "jeans", "category": "pants", "formality": ["casual"], "warmth": 2},
        {"name": "boots", "category": "shoes", "formality": ["casual"], "warmth": 2},
    ]

    out = generate_outfit(weather, wardrobe, request={"formality_hint": "casual"})

    assert "warm knit" in out["items"]
    assert "thin tee" not in out["items"]


def test_dressier_step_prefers_more_formal_piece():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 12}
    wardrobe = [
        {"name": "casual tee", "category": "top", "formality": ["casual"], "warmth": 1},
        {"name": "silk blouse", "category": "blouse", "formality": ["smart casual", "business"], "warmth": 1},
        {"name": "black trousers", "category": "pants", "formality": ["smart casual", "business"], "warmth": 2},
        {"name": "loafers", "category": "shoes", "formality": ["smart casual", "business"], "warmth": 1},
    ]

    out = generate_outfit(weather, wardrobe, request={"formality_hint": "business"})

    assert "silk blouse" in out["items"]
    assert "casual tee" not in out["items"]


def test_bag_is_added_for_dressier_outfits():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 12}
    wardrobe = [
        {"name": "silk blouse", "category": "blouse", "formality": ["smart casual", "business"], "warmth": 1},
        {"name": "black skirt", "category": "skirt", "formality": ["smart casual", "business"], "warmth": 2},
        {"name": "loafers", "category": "shoes", "formality": ["smart casual", "business"], "warmth": 1},
        {"name": "saddle bag", "category": "bag", "formality": ["smart casual", "business"], "warmth": 0},
    ]

    out = generate_outfit(weather, wardrobe, request={"formality_hint": "business"})

    assert "saddle bag" in out["items"]


def test_work_outfit_prefers_separates_over_dress():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 12}
    wardrobe = [
        {"name": "black dress", "category": "dress", "formality": ["smart casual", "business"], "warmth": 2},
        {"name": "silk blouse", "category": "blouse", "formality": ["smart casual", "business"], "warmth": 1},
        {"name": "black trousers", "category": "pants", "formality": ["smart casual", "business"], "warmth": 2},
        {"name": "loafers", "category": "shoes", "formality": ["smart casual", "business"], "warmth": 1},
    ]

    out = generate_outfit(
        weather,
        wardrobe,
        request={"formality_hint": "smart casual", "occasion": "work"},
    )

    assert "black dress" not in out["items"]
    assert "black trousers" in out["items"]


def test_lighter_rain_later_can_drop_heavy_puffer():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "rain_later", "high": 27, "low": 19}
    wardrobe = [
        {"name": "heavy puffer", "category": "outerwear", "formality": ["casual"], "rain_ok": True, "warmth": 5},
        {"name": "light blouse", "category": "blouse", "formality": ["casual", "smart casual"], "warmth": 1},
        {"name": "linen skirt", "category": "skirt", "formality": ["casual", "smart casual"], "warmth": 1},
        {"name": "flats", "category": "shoes", "formality": ["casual", "smart casual"], "warmth": 1},
    ]

    out = generate_outfit(weather, wardrobe, request={"formality_hint": "smart casual"})

    assert "heavy puffer" not in out["items"]


def test_variety_changes_fallback_choice():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 12}
    wardrobe = [
        {"name": "navy knit", "category": "knit", "formality": ["casual"], "warmth": 2},
        {"name": "cream knit", "category": "knit", "formality": ["casual"], "warmth": 2},
        {"name": "black skirt", "category": "skirt", "formality": ["casual"], "warmth": 2},
        {"name": "camel skirt", "category": "skirt", "formality": ["casual"], "warmth": 2},
        {"name": "black boots", "category": "shoes", "formality": ["casual"], "warmth": 2},
        {"name": "brown boots", "category": "shoes", "formality": ["casual"], "warmth": 2},
    ]

    base = generate_outfit(weather, wardrobe, request={"formality_hint": "casual"})
    surprise = generate_outfit(weather, wardrobe, request={"formality_hint": "casual", "variety": True})

    assert base["items"] != surprise["items"]


def test_elegant_style_notes_prefer_polished_items():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 12}
    wardrobe = [
        {"name": "logo sweatshirt", "category": "knit", "formality": ["casual"], "warmth": 2, "pattern": "graphic"},
        {"name": "silk blouse", "category": "blouse", "formality": ["smart casual", "business"], "warmth": 1, "neutral": True},
        {"name": "black trousers", "category": "pants", "formality": ["smart casual", "business"], "warmth": 2, "neutral": True},
        {"name": "loafers", "category": "shoes", "formality": ["smart casual", "business"], "warmth": 1, "neutral": True},
    ]

    out = generate_outfit(
        weather,
        wardrobe,
        request={"formality_hint": "smart casual", "style_notes": "elegant classy"},
    )

    assert "silk blouse" in out["items"]
    assert "logo sweatshirt" not in out["items"]


def test_elegant_style_notes_prefer_polished_bag():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 12}
    wardrobe = [
        {"name": "silk blouse", "category": "blouse", "formality": ["smart casual"], "warmth": 1, "neutral": True},
        {"name": "black trousers", "category": "pants", "formality": ["smart casual"], "warmth": 2, "neutral": True},
        {"name": "loafers", "category": "shoes", "formality": ["smart casual"], "warmth": 1, "neutral": True},
        {"name": "canvas tote", "category": "bag", "formality": ["smart casual"], "warmth": 0, "material": "cotton canvas"},
        {"name": "leather saddle bag", "category": "bag", "formality": ["smart casual"], "warmth": 0, "material": "pebbled leather", "neutral": True},
    ]

    out = generate_outfit(
        weather,
        wardrobe,
        request={"formality_hint": "smart casual", "style_notes": "elegant classy"},
    )

    assert "leather saddle bag" in out["items"]
    assert "canvas tote" not in out["items"]


def test_mild_rain_later_does_not_force_puffer_or_boots():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "rain_later", "high": 18, "low": 12}
    wardrobe = [
        {"name": "cream puffer", "category": "outerwear", "formality": ["smart casual"], "rain_ok": True, "warmth": 5, "material": "nylon puffer"},
        {"name": "taupe cardigan", "category": "cardigan", "formality": ["smart casual"], "rain_ok": False, "warmth": 3, "material": "cotton knit"},
        {"name": "silk blouse", "category": "blouse", "formality": ["smart casual"], "warmth": 1, "material": "silk", "neutral": True},
        {"name": "cream trousers", "category": "pants", "formality": ["smart casual"], "warmth": 2, "material": "tailored cotton", "neutral": True},
        {"name": "black boots", "category": "shoes", "formality": ["smart casual"], "rain_ok": True, "warmth": 3, "material": "leather"},
        {"name": "cream loafers", "category": "shoes", "formality": ["smart casual"], "rain_ok": False, "warmth": 1, "material": "leather"},
    ]

    out = generate_outfit(
        weather,
        wardrobe,
        request={"formality_hint": "smart casual", "style_notes": "elegant classy", "recent": ["black boots"]},
    )

    assert "cream puffer" not in out["items"]
    assert "black boots" not in out["items"]


def test_cozy_home_prefers_soft_home_clothes_over_jeans_or_dresses():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 16, "low": 10}
    wardrobe = [
        {"name": "soft sweatshirt", "category": "knit", "formality": ["casual"], "warmth": 3, "material": "brushed fleece", "best_for": ["home"]},
        {"name": "oatmeal sweatpants", "category": "pants", "formality": ["casual"], "warmth": 3, "material": "fleece", "best_for": ["home"]},
        {"name": "straight jeans", "category": "jeans", "formality": ["casual"], "warmth": 2, "material": "denim"},
        {"name": "black midi dress", "category": "dress", "formality": ["casual", "smart casual"], "warmth": 2},
        {"name": "house slides", "category": "shoes", "formality": ["casual"], "warmth": 1, "best_for": ["home"]},
    ]

    out = generate_outfit(weather, wardrobe, request={"formality_hint": "casual", "occasion": "cozy home"})

    assert "oatmeal sweatpants" in out["items"]
    assert "straight jeans" not in out["items"]
    assert "black midi dress" not in out["items"]


def test_multiple_anchors_are_included_without_multiple_bags():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 18, "low": 12}
    wardrobe = [
        {"name": "navy cardigan", "id": "navy-cardigan", "category": "cardigan", "formality": ["smart casual"], "warmth": 3},
        {"name": "silk blouse", "id": "silk-blouse", "category": "blouse", "formality": ["smart casual"], "warmth": 1},
        {"name": "cream trousers", "id": "cream-trousers", "category": "pants", "formality": ["smart casual"], "warmth": 2},
        {"name": "loafers", "id": "loafers", "category": "shoes", "formality": ["smart casual"], "warmth": 1},
        {"name": "taupe bag", "id": "taupe-bag", "category": "bag", "formality": ["smart casual"], "warmth": 0},
        {"name": "black bag", "id": "black-bag", "category": "bag", "formality": ["smart casual"], "warmth": 0},
    ]

    out = generate_outfit(
        weather,
        wardrobe,
        request={"formality_hint": "smart casual", "anchors": ["navy-cardigan", "taupe-bag", "black-bag"]},
    )

    assert "navy cardigan" in out["items"]
    assert len([name for name in out["items"] if "bag" in name]) == 1


def test_anchored_accessories_still_return_complete_outfit():
    from ai.generate_outfit import generate_outfit
    weather = {"condition": "cloudy", "high": 9, "low": 3}
    wardrobe = [
        {"name": "cream puffer", "id": "cream-puffer", "category": "outerwear", "formality": ["casual"], "warmth": 5, "material": "nylon puffer"},
        {"name": "wool beanie", "id": "wool-beanie", "category": "accessory", "formality": ["casual"], "warmth": 4, "material": "ribbed wool"},
        {"name": "plaid scarf", "id": "plaid-scarf", "category": "accessory", "formality": ["casual"], "warmth": 3, "material": "plaid wool"},
        {"name": "canvas tote", "id": "canvas-tote", "category": "bag", "formality": ["casual"], "warmth": 1, "material": "canvas"},
        {"name": "black boots", "id": "black-boots", "category": "shoes", "formality": ["casual"], "warmth": 4, "material": "leather"},
        {"name": "striped thermal top", "id": "thermal-top", "category": "top", "formality": ["casual"], "warmth": 4, "material": "ribbed cotton", "pattern": "striped"},
        {"name": "gingham fleece pants", "id": "fleece-pants", "category": "pants", "formality": ["casual"], "warmth": 4, "material": "floral fleece", "pattern": "gingham"},
    ]

    out = generate_outfit(
        weather,
        wardrobe,
        request={
            "formality_hint": "casual",
            "anchors": ["cream-puffer", "wool-beanie", "plaid-scarf", "canvas-tote", "black-boots"],
        },
    )

    assert "striped thermal top" in out["items"]
    assert "gingham fleece pants" in out["items"]


def test_anchor_warnings_formality_pattern_warmth():
    from core.outfit import anchor_warnings
    wardrobe = [
        {"id": "gown", "name": "silk gown", "category": "dress", "formality": ["formal"], "warmth": 1},
        {"id": "sweats", "name": "grey sweatpants", "category": "pants", "formality": ["athletic", "casual"], "warmth": 3},
        {"id": "leo", "name": "leopard midi skirt", "category": "skirt", "pattern": "animal", "warmth": 2},
        {"id": "floral", "name": "floral blouse", "category": "blouse", "pattern": "floral", "warmth": 2},
        {"id": "puffer", "name": "down puffer", "category": "outerwear", "warmth": 5},
        {"id": "tank", "name": "linen tank", "category": "top", "warmth": 1},
        {"id": "lightcardi", "name": "sheer cardigan", "category": "cardigan", "warmth": 1},
    ]
    w1 = anchor_warnings(wardrobe, ["gown", "sweats"])
    assert any("dressiness" in x for x in w1)
    w2 = anchor_warnings(wardrobe, ["leo", "floral"])
    assert any("bold patterns" in x for x in w2)
    # A light base under a warm coat is valid layering — no temperature warning.
    assert not any("temperatures" in x for x in anchor_warnings(wardrobe, ["puffer", "tank"]))
    # Two pieces competing for the same layer slot at opposite warmths still clash.
    assert any("temperatures" in x for x in anchor_warnings(wardrobe, ["puffer", "lightcardi"]))


def test_cool_days_stack_compatible_layers_not_one_heavy_piece():
    from ai.generate_outfit import fallback_outfit, _slot

    wardrobe = [
        {"id": "t", "name": "thin tee", "category": "top", "thickness": "thin", "warmth": 2, "formality": ["casual"]},
        {"id": "c", "name": "fine cardigan", "category": "cardigan", "thickness": "medium", "warmth": 3, "formality": ["casual"]},
        {"id": "co", "name": "wool coat", "category": "outerwear", "thickness": "medium", "warmth": 4, "formality": ["casual"]},
        {"id": "p", "name": "jeans", "category": "jeans", "thickness": "medium", "warmth": 2, "formality": ["casual"]},
        {"id": "s", "name": "sneakers", "category": "shoes", "warmth": 2, "formality": ["casual"]},
    ]
    cold = fallback_outfit({"high": 8, "condition": "clear"}, wardrobe)["items"]
    torso = [_slot({**w, **{}}) for w in wardrobe if w["name"] in cold]
    # a cold day layers up: at least two distinct torso layers coexist
    layered = {s for s in (_slot(next(w for w in wardrobe if w["name"] == n)) for n in cold)
               if s in {"base", "mid", "outer"}}
    assert len(layered) >= 2

    mild = fallback_outfit({"high": 24, "condition": "clear"}, wardrobe)["items"]
    mild_layers = {_slot(next(w for w in wardrobe if w["name"] == n)) for n in mild}
    assert mild_layers & {"base", "mid", "outer"}  # has a top
    assert "mid" not in mild_layers and "outer" not in mild_layers  # but no forced extra layers


def test_incompatible_layers_are_not_nested():
    from ai.generate_outfit import _can_nest, _stack_warmth

    thin_top = {"category": "top", "thickness": "thin", "warmth": 2}
    chunky = {"category": "knit", "thickness": "thick", "texture": "chunky cable knit", "warmth": 4}
    slim_blazer = {"category": "outerwear", "subtype": "tailored slim blazer", "warmth": 2}
    coat = {"category": "outerwear", "thickness": "medium", "warmth": 4}

    assert _can_nest(thin_top, coat)
    assert not _can_nest(chunky, slim_blazer)   # chunky won't fit under a slim jacket
    assert not _can_nest(chunky, {"category": "outerwear", "thickness": "thick", "warmth": 5})  # two thick
    # two light layers combine toward, but stay below, one genuinely warm piece
    assert _stack_warmth([thin_top, {"category": "cardigan", "warmth": 2}]) < _stack_warmth([{"category": "outerwear", "warmth": 5}])
