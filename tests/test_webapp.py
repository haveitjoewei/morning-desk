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


def test_update_item_metadata_writes_correction(monkeypatch, tmp_path):
    monkeypatch.setenv("WARDROBE_PIN", "2468")
    monkeypatch.setenv("WARDROBE_SECRET", "s")
    monkeypatch.setenv("MD_OFFLINE", "1")
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    monkeypatch.setenv("WARDROBE_PROFILE", "eve")
    d = tmp_path / "eve"
    d.mkdir()
    (d / "items.json").write_text(json.dumps([
        {"name": "Cream Trousers", "id": "cream-trousers", "category": "pants", "formality": ["smart casual"], "warmth": 2}
    ]))
    (d / "config.json").write_text('{"categories":"womenswear","location":{"latitude":-33.8,"longitude":151.2,"timezone":"Australia/Sydney"}}')
    from fastapi.testclient import TestClient
    from webapp.app import app
    c = TestClient(app)
    tok = c.post("/api/unlock", json={"pin": "2468"}).json()["token"]

    r = c.post(
        "/api/wardrobe/cream-trousers",
        headers={"Authorization": f"Bearer {tok}"},
        json={"warmth": 3, "polish": 4, "comfort": 2, "home_ok": False, "office_ok": True},
    )

    assert r.status_code == 200
    corrections = json.loads((d / "corrections.json").read_text())
    assert corrections[0]["name"] == "Cream Trousers"
    assert corrections[0]["set"]["warmth"] == 3
    assert corrections[0]["set"]["polish"] == 4
    assert json.loads((d / "items.json").read_text())[0].get("polish") is None


def test_anchor_check_warns_on_conflicting_slots(monkeypatch, tmp_path):
    monkeypatch.setenv("WARDROBE_PIN", "2468")
    monkeypatch.setenv("WARDROBE_SECRET", "s")
    monkeypatch.setenv("MD_OFFLINE", "1")
    monkeypatch.setenv("MD_PROFILES_ROOT", str(tmp_path))
    monkeypatch.setenv("WARDROBE_PROFILE", "eve")
    d = tmp_path / "eve"
    d.mkdir()
    (d / "items.json").write_text(json.dumps([
        {"name": "Navy Sweater", "id": "navy-sweater", "category": "knit"},
        {"name": "Silk Blouse", "id": "silk-blouse", "category": "blouse"},
        {"name": "Taupe Bag", "id": "taupe-bag", "category": "bag"},
        {"name": "Black Bag", "id": "black-bag", "category": "bag"},
    ]))
    (d / "config.json").write_text('{"categories":"womenswear","location":{"latitude":-33.8,"longitude":151.2,"timezone":"Australia/Sydney"}}')
    from fastapi.testclient import TestClient
    from webapp.app import app
    c = TestClient(app)
    tok = c.post("/api/unlock", json={"pin": "2468"}).json()["token"]

    r = c.post(
        "/api/anchors/check",
        headers={"Authorization": f"Bearer {tok}"},
        json={"anchors": ["navy-sweater", "silk-blouse", "taupe-bag", "black-bag"]},
    )

    assert r.status_code == 200
    warnings = r.json()["warnings"]
    assert any("top" in w for w in warnings)
    assert any("bag" in w for w in warnings)


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
