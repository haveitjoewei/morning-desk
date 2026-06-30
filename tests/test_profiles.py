import json
from types import SimpleNamespace
from core.profiles import profile_dir, load_config, DEFAULT_PROFILE

def test_default_profile_is_joseph():
    assert DEFAULT_PROFILE == "joseph"

def test_profile_dir_points_under_profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    assert profile_dir("evangeline") == tmp_path / "evangeline"

def test_load_config_returns_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    cfg = load_config("evangeline")
    assert "categories" in cfg and "location" in cfg

def test_correction_writes_selected_profile_only(tmp_path, monkeypatch):
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    joseph = tmp_path / "joseph"
    evangeline = tmp_path / "evangeline"
    joseph.mkdir()
    evangeline.mkdir()

    base = {
        "id": "black-loafers",
        "name": "black loafers",
        "category": "shoes",
        "subtype": "loafers",
        "brand": None,
        "colors": ["black"],
        "neutral": True,
        "pattern": "solid",
        "sleeve": "na",
        "material": "leather",
        "texture": "smooth",
        "thickness": "medium",
        "warmth": 2,
        "formality": ["smart casual"],
        "rain_ok": False,
        "season": ["autumn"],
        "condition": "good",
        "fit_notes": "normal",
        "confidence": "high",
        "learned": [],
    }
    (joseph / "items.json").write_text(json.dumps([dict(base, name="joseph loafers")]))
    (evangeline / "items.json").write_text(json.dumps([base]))

    corrected = dict(base, formality=["business"], learned_note="Too dressy for casual looks.")
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=json.dumps(corrected))]
    )
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kwargs: response)
    )

    monkeypatch.setattr("wardrobe.correct.available", lambda: True)
    monkeypatch.setattr("wardrobe.correct.client", lambda timeout=None: fake_client)

    from wardrobe.correct import correct

    correct("loafers", "these are dressier than smart casual", profile="evangeline")

    assert json.loads((joseph / "items.json").read_text())[0]["formality"] == ["smart casual"]
    saved = json.loads((evangeline / "items.json").read_text())[0]
    assert saved["formality"] == ["business"]
    assert saved["learned"] == [
        {
            "correction": "these are dressier than smart casual",
            "note": "Too dressy for casual looks.",
        }
    ]
