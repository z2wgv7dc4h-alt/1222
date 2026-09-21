import json

import pytest

from boo_lab.audit import audit_lab
from boo_lab.schema import (
    FIGURE_ROLES,
    FUNCTION_ROLES,
    SOURCES,
    canonical_role,
    is_keeper,
    layer_for,
    load_section_rows,
    msa_label_to_lab,
    same_role_overlaps,
    stamp_box,
)


def test_msa_maps_to_lab_not_pop():
    assert msa_label_to_lab("verse") == "riff"
    assert msa_label_to_lab("chorus") == "hook"


def test_keepers_fail_closed():
    assert not is_keeper(None)
    assert not is_keeper("")
    assert not is_keeper("   ")
    assert is_keeper("human")
    assert is_keeper("guess-accepted")
    assert not is_keeper("msa-draft")
    assert not is_keeper("guess")
    assert not is_keeper("songformer-draft")
    assert not is_keeper("not-a-real-source")


def test_canonical_role_returns_none_for_unmappable():
    assert canonical_role(None) is None
    assert canonical_role("") is None
    assert canonical_role("   ") is None
    assert canonical_role("bogus") is None
    assert canonical_role("verse") == "riff"
    assert all(canonical_role(r) == r for r in
                ("intro", "build", "riff", "hook", "breakdown", "blast", "solo", "chill", "pulse", "outro"))


def test_sources_contains_gp_marker_and_figure_hash():
    assert "gp-marker" in SOURCES
    assert "figure-hash" in SOURCES
    assert "human" in SOURCES
    assert "guess-accepted" in SOURCES
    for s in ("guess", "msa-draft", "songformer-draft", "keeper-model",
              "tabnotes-density", "tabnotes-structure", "tabnotes-phrase",
              "blast-hint"):
        assert s in SOURCES
    assert "adapt" not in SOURCES


def test_stamp_box_rejects_unknown_role_and_source():
    with pytest.raises(ValueError):
        stamp_box(0, 1, None)
    with pytest.raises(ValueError):
        stamp_box(0, 1, "not-a-role")
    with pytest.raises(ValueError):
        stamp_box(0, 1, "riff", source="not-a-real-source")
    with pytest.raises(ValueError):
        stamp_box(0, 1, "riff", source=None)


def test_load_section_rows_keeps_keepers_drops_drafts_and_malformed(tmp_path):
    p = tmp_path / "sections.jsonl"
    p.write_text(
        json.dumps({"album": "A", "track": "T", "role": "riff", "source": "human", "heard": True}) + "\n"
        + json.dumps({"album": "A", "track": "T", "role": "riff", "source": "human", "heard": False}) + "\n"  # unheard human: not a keeper
        + json.dumps({"album": "A", "track": "T", "role": "riff", "source": "msa-draft", "heard": True}) + "\n"
        + json.dumps({"album": "A", "track": "U", "role": "intro", "heard": True}) + "\n"  # no source: not keeper
        + "{ not json\n",
        encoding="utf-8",
    )
    rows = load_section_rows(p)
    assert len(rows) == 1
    assert rows[0]["source"] == "human" and rows[0]["track"] == "T" and rows[0]["heard"] is True


def test_same_role_overlap_detected():
    boxes = [
        {"role": "riff", "start": 0, "end": 4},
        {"role": "riff", "start": 2, "end": 6},
        {"role": "breakdown", "start": 2, "end": 6},
    ]
    hits = same_role_overlaps(boxes)
    assert hits == [(0, 1, "riff")]


def test_stamp_box():
    b = stamp_box(0, 1, "hook", source="msa-draft")
    assert b["layer"] == "figure" and b["source"] == "msa-draft"


def test_blast_is_a_function_role_not_a_figure():
    assert canonical_role("blast") == "blast"
    assert canonical_role("Blast") == "blast"
    assert canonical_role("blast-beat") == "blast"
    assert canonical_role("blastbeat") == "blast"
    assert "blast" in FUNCTION_ROLES and "blast" not in FIGURE_ROLES
    assert layer_for("blast") == "function"


def test_stamp_box_carries_the_optional_on_figure_link():
    b = stamp_box(0, 4, "blast", source="guess", on_figure=" riff-A ")
    assert b["on_figure"] == "riff-A"
    assert b["layer"] == "function"
    assert stamp_box(0, 4, "riff")["on_figure"] == ""


def test_stamp_box_identity_defaults():
    b = stamp_box(0, 4, "riff")
    assert b["form"] == "A"
    assert b["figure_id"] == "riff-A"
    assert b["unique"] is False
    assert b["instrument"] == ""
    assert b["start_bar"] is None and b["end_bar"] is None


def test_stamp_box_function_role_keeps_blank_figure_id():
    for role in ("intro", "build", "breakdown", "blast", "chill", "outro"):
        b = stamp_box(0, 4, role)
        assert b["figure_id"] == "", role
    # human-typed figure_id is kept even on a function role
    typed = stamp_box(0, 4, "breakdown", figure_id="custom-A")
    assert typed["figure_id"] == "custom-A"


def test_stamp_box_figure_roles_default_figure_id_when_blank():
    for role in ("riff", "hook", "solo", "pulse"):
        assert stamp_box(0, 4, role)["figure_id"] == f"{role}-A"
        assert stamp_box(0, 4, role, figure_id="X")["figure_id"] == "X"


def test_stamp_box_identity_round_trip():
    b = stamp_box(1, 3, "solo", form="b", unique=True, instrument="Lead",
                  start_bar=17, end_bar=20)
    assert b["form"] == "B"
    assert b["unique"] is True
    assert b["instrument"] == "lead"
    assert b["start_bar"] == 17 and b["end_bar"] == 20
    assert json.loads(json.dumps(b))["end_bar"] == 20


def test_stamp_box_rejects_bad_instrument_and_bars():
    b = stamp_box(0, 1, "riff", instrument="kazoo", start_bar="x", end_bar=-3)
    assert b["instrument"] == ""
    assert b["start_bar"] is None and b["end_bar"] is None


def test_audit_empty(tmp_path):
    (tmp_path / "data").mkdir()
    r = audit_lab(tmp_path)
    assert r["section_rows"] == 0
    assert r["same_role_overlaps"] == []
