import json
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
