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
