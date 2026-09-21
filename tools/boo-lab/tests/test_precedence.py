import json
import shutil
from pathlib import Path

from boo_lab.precedence import resolve_precedence, tab_plan

FIX_GP7 = Path(__file__).parent / "fixtures" / "tiny.gp"
FIX_PACK = Path(__file__).parent / "fixtures" / "tabnotes_tiny"


def _lab(tmp_path, sync_ok=None):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    if sync_ok is not None:
        (lab / "data" / "sync.jsonl").write_text(
            json.dumps({"album": "A", "track": "Tiny Pack", "sync_ok": sync_ok}) + "\n",
            encoding="utf-8")
    return lab


def _with_pack(lab):
    (lab / "data" / "tabnotes").mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIX_PACK, lab / "data" / "tabnotes" / "tabnotes_tiny")


def test_tab_plan_no_sync_row_spine_is_human(tmp_path):
    lab = _lab(tmp_path, sync_ok=None)

    plan = tab_plan(lab, "A", "Tiny Pack", gp_path=FIX_GP7)

    assert plan["spine"] == "human"
    assert plan["sync_ok"] is False


def test_tab_plan_sync_ok_with_gp_marker_spine_is_gp_marker(tmp_path):
    lab = _lab(tmp_path, sync_ok=True)

    plan = tab_plan(lab, "A", "Tiny Pack", gp_path=FIX_GP7)

    assert plan["spine"] == "gp-marker"
    assert plan["notes"] == "gp"
    assert plan["markers"] is True


def test_tab_plan_sync_ok_with_only_a_pack_spine_is_pack(tmp_path):
    lab = _lab(tmp_path, sync_ok=True)
    _with_pack(lab)

    plan = tab_plan(lab, "A", "Tiny Pack")

    assert plan["spine"] == "pack"
    assert plan["notes"] == "pack"
    assert plan["pack_path"] is not None


def test_tab_plan_sync_ok_with_gp_no_markers_and_pack_spine_is_pack_notes_gp(tmp_path, monkeypatch):
    lab = _lab(tmp_path, sync_ok=True)
    _with_pack(lab)
    fake_gp5 = tmp_path / "unparseable.gp5"
    fake_gp5.write_bytes(b"x")
    from boo_lab import guess as g

    monkeypatch.setattr(g, "_prefer_tab", lambda p, track: p)

    plan = tab_plan(lab, "A", "Tiny Pack", gp_path=fake_gp5)

    assert plan["spine"] == "pack"
    assert plan["notes"] == "gp"


def test_no_sync_ok_spine_is_human():
    for sync_ok in (None, False):
        d = resolve_precedence(sync_ok=sync_ok, has_gp_markers=True,
                                has_pack=True, has_gp=True)
        assert d["spine"] == "human"
        assert d["sync_ok"] is False
        assert d["clock"] == "gp-notated"


def test_sync_ok_with_gp_markers_spine_is_gp_marker():
    d = resolve_precedence(sync_ok=True, has_gp_markers=True,
                            has_pack=True, has_gp=True)
    assert d["spine"] == "gp-marker"
    assert d["sync_ok"] is True
    assert d["clock"] == "clock_ratio"
    # A pack alongside markers doesn't demote the spine.
    d2 = resolve_precedence(sync_ok=True, has_gp_markers=True,
                             has_pack=False, has_gp=True)
    assert d2["spine"] == "gp-marker"


def test_sync_ok_with_pack_and_no_markers_spine_is_pack():
    d = resolve_precedence(sync_ok=True, has_gp_markers=False,
                            has_pack=True, has_gp=False)
    assert d["spine"] == "pack"
    assert d["clock"] == "pack-audio"


def test_sync_ok_with_gp_and_pack_no_markers_spine_pack_notes_gp():
    # Both a readable GP and a pack, but the GP carries no section markers:
    # the pack is still the structure spine, but notes read from GP (item 4
    # prefers gp over pack whenever a readable GP exists).
    d = resolve_precedence(sync_ok=True, has_gp_markers=False,
                            has_pack=True, has_gp=True)
    assert d["spine"] == "pack"
    assert d["notes_source"] == "gp"


def test_sync_ok_with_no_markers_and_no_pack_spine_is_human():
    d = resolve_precedence(sync_ok=True, has_gp_markers=False,
                            has_pack=False, has_gp=False)
    assert d["spine"] == "human"
    assert d["clock"] == "gp-notated"


def test_notes_source_precedence():
    assert resolve_precedence(sync_ok=True, has_gp_markers=False,
                               has_pack=True, has_gp=True)["notes_source"] == "gp"
    assert resolve_precedence(sync_ok=False, has_gp_markers=False,
                               has_pack=True, has_gp=False)["notes_source"] == "pack"
    assert resolve_precedence(sync_ok=False, has_gp_markers=False,
                               has_pack=False, has_gp=False)["notes_source"] is None
