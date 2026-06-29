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
