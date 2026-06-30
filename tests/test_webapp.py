from webapp.auth import check_pin, make_token, verify_token
import json
from pathlib import Path


def test_pin_roundtrip(monkeypatch):
    monkeypatch.setenv("WARDROBE_PIN", "2468")
    monkeypatch.setenv("WARDROBE_SECRET", "s3cret")
    assert check_pin("2468")
    assert not check_pin("0000")
    tok = make_token()
    assert verify_token(tok)
    assert not verify_token(tok + "x")


def test_empty_pin_never_matches(monkeypatch):
    monkeypatch.delenv("WARDROBE_PIN", raising=False)
    assert not check_pin("")
    assert not check_pin("anything")


def test_unlock_and_outfit(monkeypatch, tmp_path):
    monkeypatch.setenv("WARDROBE_PIN", "2468")
    monkeypatch.setenv("WARDROBE_SECRET", "s")
    monkeypatch.setenv("MD_OFFLINE", "1")
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    monkeypatch.setenv("WARDROBE_PROFILE", "eve")
    d = tmp_path / "eve"
    d.mkdir()
    (d / "items.json").write_text('[{"name":"Red Dress","id":"red","category":"dress","formality":["smart casual"],"warmth":2}]')
    (d / "config.json").write_text('{"categories":"womenswear","location":{"latitude":-33.8,"longitude":151.2,"timezone":"Australia/Sydney"}}')
    from fastapi.testclient import TestClient
    from webapp.app import app
    c = TestClient(app)
    assert c.post("/api/unlock", json={"pin": "0000"}).status_code == 401
    tok = c.post("/api/unlock", json={"pin": "2468"}).json()["token"]
    r = c.post("/api/outfit", headers={"Authorization": f"Bearer {tok}"},
               json={"prefs": {}, "day": {"occasion": "dressy"}})
    assert r.status_code == 200 and "headline" in r.json()
    assert c.post("/api/outfit", json={"prefs": {}, "day": {}}).status_code == 401


def test_vercel_config_uses_modern_python_function_shape():
    cfg = json.loads(Path("vercel.json").read_text())

    assert "builds" not in cfg
    assert "routes" not in cfg
    assert cfg["rewrites"] == [{"source": "/(.*)", "destination": "/api/index"}]

    api = cfg["functions"]["api/index.py"]
    assert api["maxDuration"] == 10
    include = api["includeFiles"]
    assert "profiles/evangeline/cutouts/**" in include
    assert "profiles/evangeline/items.json" in include
    assert "profiles/evangeline/config.json" in include
    assert "profiles/evangeline/prefs.json" in include
    assert "images_clean" not in json.dumps(include)
