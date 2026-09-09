from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_presets_returns_real_presets():
    r = client.get("/api/presets")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert "metalcore" in ids


def test_compose_returns_real_song_summary():
    r = client.post("/api/compose", json={"preset_id": "metalcore", "seed": 1, "num_sections": 6})
    assert r.status_code == 200
    body = r.json()
    assert body["preset_id"] == "metalcore"
    assert len(body["sections"]) == 6


def test_compose_applies_real_edits():
    base = client.post("/api/compose", json={"preset_id": "metalcore", "seed": 1, "num_sections": 6}).json()
    order = list(range(len(base["sections"])))
    edited = client.post("/api/compose", json={
        "preset_id": "metalcore", "seed": 1, "num_sections": 6, "order": order,
        "edits": [{"section_position": 2, "mode": "full", "regen_seed": 42}],
    }).json()
    assert len(edited["sections"]) == len(base["sections"])
    # Real invariant every edited section must still satisfy.
    assert edited["sections"][2]["guitar_hits"] > 0


def test_export_midi_returns_real_midi_bytes():
    base = client.post("/api/compose", json={"preset_id": "metalcore", "seed": 1, "num_sections": 6}).json()
    order = list(range(len(base["sections"])))
    r = client.post("/api/export-midi", json={"preset_id": "metalcore", "seed": 1, "num_sections": 6, "order": order})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/midi"
    assert r.content[:4] == b"MThd"


def test_export_rpp_returns_real_reaper_project_text():
    base = client.post("/api/compose", json={"preset_id": "metalcore", "seed": 1, "num_sections": 6}).json()
    order = list(range(len(base["sections"])))
    r = client.post("/api/export-rpp", json={"preset_id": "metalcore", "seed": 1, "num_sections": 6, "order": order})
    assert r.status_code == 200
    assert r.content.startswith(b"<REAPER_PROJECT")


def test_compose_rejects_unknown_preset():
    r = client.post("/api/compose", json={"preset_id": "not-a-real-preset", "seed": 1})
    assert r.status_code == 404


def test_export_midi_rejects_out_of_range_order():
    r = client.post("/api/export-midi", json={"preset_id": "metalcore", "seed": 1, "num_sections": 4, "order": [0, 99]})
    assert r.status_code == 400
