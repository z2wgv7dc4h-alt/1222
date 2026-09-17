import json

from boo_lab.audit import audit_lab
from boo_lab.schema import (
    is_keeper,
    msa_label_to_lab,
    same_role_overlaps,
    stamp_box,
)


def test_msa_maps_to_lab_not_pop():
    assert msa_label_to_lab("verse") == "riff"
    assert msa_label_to_lab("chorus") == "hook"


def test_keepers():
    assert is_keeper(None)
    assert is_keeper("human")
    assert not is_keeper("msa-draft")
    assert not is_keeper("guess")
    assert not is_keeper("songformer-draft")


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


def test_stamp_box_identity_defaults():
    b = stamp_box(0, 4, "riff")
    assert b["form"] == "A"
    assert b["unique"] is False
    assert b["instrument"] == ""
    assert b["start_bar"] is None and b["end_bar"] is None


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
