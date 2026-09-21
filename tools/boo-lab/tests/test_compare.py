"""Tests for src/boo_lab/compare.py -- drafts vs keepers, synthetic jsonl
under tmp_path; no real audio."""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab import compare


def _keeper(role, start, end, figure_id=None, heard=True, source="human"):
    return {"album": "A", "track": "T", "start": start, "end": end, "role": role,
            "source": source, "heard": heard, "figure_id": figure_id or (role + "-A")}


def _draft(role, start, end, source="msa-draft", figure_id=None):
    return {"album": "A", "track": "T", "start": start, "end": end, "role": role,
            "source": source, "figure_id": figure_id or (role + "-A")}


def _lab(tmp_path, keepers, drafts):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "sections.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in keepers), encoding="utf-8")
    (lab / "data" / "drafts.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in drafts), encoding="utf-8")
    return lab


def test_perfect_match_f_is_one(tmp_path):
    lab = _lab(tmp_path, [_keeper("riff", 0, 4)], [_draft("riff", 0, 4)])
    report = compare.compare(lab)
    assert report["micro"]["n_tracks"] == 1
    t = report["tracks"][0]
    assert t["n_keep"] == 1 and t["n_draft"] == 1
    assert t["source"] == "msa-draft"
    assert t["f_0_5"] == 1.0 and t["f_3_0"] == 1.0
    assert t["role_agree_3_0"] == 1.0


def test_two_draft_sources_emit_two_rows(tmp_path):
    lab = _lab(tmp_path,
               [_keeper("riff", 0, 4)],
               [_draft("riff", 0, 4, source="msa-draft"),
                _draft("hook", 0, 4, source="songformer-draft")])
    report = compare.compare(lab)
    assert report["micro"]["n_tracks"] == 1
    assert report["micro"]["n_rows"] == 2
    assert {t["source"] for t in report["tracks"]} == {"msa-draft", "songformer-draft"}


def test_tabnotes_structure_draft_is_scored_against_keeper(tmp_path):
    lab = _lab(tmp_path,
               [_keeper("riff", 0, 4)],
               [_draft("riff", 0, 4, source="tabnotes-structure")])
    report = compare.compare(lab)
    t = report["tracks"][0]
    assert t["source"] == "tabnotes-structure"
    assert t["f_0_5"] > 0.0 and t["f_3_0"] > 0.0


def test_offset_two_seconds_low_f05_high_f3(tmp_path):
    lab = _lab(tmp_path, [_keeper("riff", 0, 4)], [_draft("riff", 2, 6)])
    t = compare.compare(lab)["tracks"][0]
    assert t["f_0_5"] == 0.0
    assert t["f_3_0"] == 1.0
    assert t["role_agree_3_0"] == 1.0  # starts within 3s -> hit pair, same role


def test_role_mismatch_lowers_role_agreement(tmp_path):
    lab = _lab(tmp_path, [_keeper("riff", 0, 4)], [_draft("hook", 0, 4)])
    t = compare.compare(lab)["tracks"][0]
    assert t["f_3_0"] == 1.0
    assert t["role_agree_3_0"] == 0.0


def test_msa_and_canonical_roles_agree(tmp_path):
    lab = _lab(tmp_path, [_keeper("hook", 0, 4)], [_draft("chorus", 0, 4)])
    t = compare.compare(lab)["tracks"][0]
    assert t["role_agree_3_0"] == 1.0


def test_skips_songs_missing_a_side(tmp_path):
    keepers_only = _lab(tmp_path / "a", [_keeper("riff", 0, 4)], [])
    assert compare.compare(keepers_only)["micro"]["n_tracks"] == 0

    drafts_only = _lab(tmp_path / "b", [], [_draft("riff", 0, 4)])
    assert compare.compare(drafts_only)["micro"]["n_tracks"] == 0


def test_legacy_missing_heard_is_filtered_by_keeper_law(tmp_path):
    legacy = {"album": "A", "track": "T", "start": 0, "end": 4, "role": "riff"}
    lab = _lab(tmp_path, [legacy], [_draft("riff", 0, 4)])
    report = compare.compare(lab)
    assert report["warned_legacy_heard_missing"] == 0
    assert report["micro"]["n_tracks"] == 0


def test_unheard_and_non_keeper_are_not_keepers(tmp_path):
    rows = [
        _keeper("riff", 0, 4, heard=False),           # unheard -> not keeper
        _keeper("hook", 5, 9, source="msa-draft"),    # draft source -> not keeper
    ]
    lab = _lab(tmp_path, rows, [_draft("riff", 0, 4), _draft("hook", 5, 9)])
    assert compare.compare(lab)["micro"]["n_tracks"] == 0


def test_holdout_is_marked_not_skipped(tmp_path):
    from boo_lab.holdout import write_holdout

    lab = _lab(tmp_path, [_keeper("riff", 0, 4)], [_draft("riff", 0, 4)])
    write_holdout(lab, {("A", "T")})
    t = compare.compare(lab)["tracks"][0]
    assert t["split"] == "holdout"


def test_write_report_and_format(tmp_path):
    lab = _lab(tmp_path, [_keeper("riff", 0, 4)], [_draft("riff", 0, 4)])
    report = compare.compare(lab)
    out = compare.write_report(report, tmp_path / "compare.json")
    assert json.loads(out.read_text(encoding="utf-8"))["micro"]["n_tracks"] == 1
    assert "micro" in compare.format_report(report)
