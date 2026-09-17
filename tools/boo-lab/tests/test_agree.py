"""Tests for src/boo_lab/agree.py -- two-pass pin agreement. Synthetic boxes
under tmp_path; no real audio."""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab import agree


def _box(start, end, role, figure_id=None, source="human", heard=True):
    return {"album": "A", "track": "T", "start": start, "end": end, "role": role,
            "source": source, "heard": heard, "figure_id": figure_id or (role + "-A")}


def _lab(tmp_path, boxes):
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "sections.jsonl").write_text(
        "".join(json.dumps(b) + "\n" for b in boxes), encoding="utf-8"
    )
    return tmp_path


def test_snapshot_pass1_then_pass2(tmp_path):
    lab = _lab(tmp_path, [_box(0, 4, "riff")])
    first = agree.snapshot(lab, "A", "T")
    assert first["pass"] == 1 and len(first["boxes"]) == 1

    # re-pin next week with a second box
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps(_box(0, 4, "riff")) + "\n" + json.dumps(_box(4, 8, "hook")) + "\n",
        encoding="utf-8",
    )
    second = agree.snapshot(lab, "A", "T")
    assert second["pass"] == 2 and len(second["boxes"]) == 2
    assert sorted(p["pass"] for p in agree.load_passes(lab, "A", "T")) == [1, 2]


def test_snapshot_never_invents_third_pass(tmp_path):
    lab = _lab(tmp_path, [_box(0, 4, "riff")])
    agree.snapshot(lab, "A", "T")
    agree.snapshot(lab, "A", "T")
    agree.snapshot(lab, "A", "T")  # replaces pass 2, no pass 3
    assert sorted(p["pass"] for p in agree.load_passes(lab, "A", "T")) == [1, 2]


def test_snapshot_never_writes_sections(tmp_path):
    lab = _lab(tmp_path, [_box(0, 4, "riff")])
    before = (lab / "data" / "sections.jsonl").read_text(encoding="utf-8")
    agree.snapshot(lab, "A", "T")
    assert (lab / "data" / "sections.jsonl").read_text(encoding="utf-8") == before


def test_diff_identical_is_perfect():
    boxes = [_box(0, 4, "riff"), _box(5, 9, "hook")]
    d = agree.diff_passes(boxes, boxes)
    assert d["boundary_hit_0_5"] == 1.0 and d["boundary_hit_3_0"] == 1.0
    assert d["hit_pairs"] == 2
    assert d["role_agreement"] == 1.0 and d["figure_agreement"] == 1.0


def test_diff_detects_role_and_figure_change():
    p1 = [_box(0, 4, "riff", figure_id="riff-A")]
    p2 = [_box(0, 4, "hook", figure_id="hook-B")]
    d = agree.diff_passes(p1, p2)
    assert d["boundary_hit_0_5"] == 1.0
    assert d["role_agreement"] == 0.0 and d["figure_agreement"] == 0.0


def test_boundary_hit_rate_respects_tolerance():
    p1 = [_box(0, 4, "riff")]
    near = [_box(0.2, 4.2, "riff")]
    far = [_box(2, 6, "riff")]
    assert agree.diff_passes(p1, near)["boundary_hit_0_5"] == 1.0
    assert agree.diff_passes(p1, far)["boundary_hit_0_5"] == 0.0
    assert agree.diff_passes(p1, far)["boundary_hit_0_5"] == 0.0
