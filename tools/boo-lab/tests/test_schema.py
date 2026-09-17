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


def test_audit_empty(tmp_path):
    (tmp_path / "data").mkdir()
    r = audit_lab(tmp_path)
    assert r["section_rows"] == 0
    assert r["same_role_overlaps"] == []
