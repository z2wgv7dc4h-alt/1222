"""audit warnings: schema gaps, function swallowing, snapshot drift.

Advisory only -- audit never rewrites a file and never fails Save.
"""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab.audit import audit_lab
from boo_lab.schema import stamp_box


def _write_rows(lab: Path, rows, name="sections.jsonl") -> Path:
    (lab / "data").mkdir(parents=True, exist_ok=True)
    p = lab / "data" / name
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return p


def _keeper(role="riff", start=0.0, end=4.0, **extra) -> dict:
    rec = {"album": "A", "track": "T", "start": start, "end": end,
           "role": role, "source": "human", "heard": True}
    rec.update(extra)
    return rec


# --- schema_gaps -------------------------------------------------------------


def test_schema_gaps_flag_missing_layer_and_empty_figure_id(tmp_path):
    _write_rows(tmp_path, [
        _keeper("intro", 0.0, 4.0),                       # missing layer only
        _keeper("pulse", 10.0, 14.0),                     # missing layer + empty figure_id
        stamp_box(20.0, 24.0, "riff", source="human", heard=True),  # stamped -> clean
    ])

    gaps = audit_lab(tmp_path)["schema_gaps"]

    reasons = {(g["role"], tuple(g["reasons"])) for g in gaps}
    assert ("intro", ("missing layer",)) in reasons
    assert ("pulse", ("missing layer", "figure-role empty figure_id")) in reasons
    assert len(gaps) == 2  # the stamped riff is not a gap


def test_schema_gaps_accepts_a_fully_stamped_keeper(tmp_path):
    _write_rows(tmp_path, [stamp_box(0.0, 4.0, "hook", source="human", heard=True)])

    assert audit_lab(tmp_path)["schema_gaps"] == []


# --- swallow_warnings --------------------------------------------------------


def test_swallow_warning_for_big_function_box_over_another_function(tmp_path):
    _write_rows(tmp_path, [
        _keeper("intro", 0.0, 100.0),
        _keeper("outro", 70.0, 100.0),
    ])

    warns = audit_lab(tmp_path)["swallow_warnings"]

    assert len(warns) == 1
    assert warns[0]["role"] == "intro"
    assert warns[0]["swallows"] == ["outro"]


def test_no_swallow_warning_when_big_box_is_a_figure(tmp_path):
    _write_rows(tmp_path, [
        _keeper("riff", 0.0, 100.0),   # a figure, not a function -> not a candidate
        _keeper("outro", 70.0, 100.0),
    ])

    assert audit_lab(tmp_path)["swallow_warnings"] == []


def test_no_swallow_warning_when_functions_do_not_nest(tmp_path):
    _write_rows(tmp_path, [
        _keeper("build", 0.0, 40.0),
        _keeper("outro", 70.0, 100.0),
    ])

    assert audit_lab(tmp_path)["swallow_warnings"] == []


# --- snapshot_drift ----------------------------------------------------------


def test_snapshot_drift_flags_a_window_only_in_the_snapshot(tmp_path):
    _write_rows(tmp_path, [
        _keeper("intro", 0.0, 10.0),
        _keeper("outro", 8.0, 10.0),
    ])
    _write_rows(tmp_path, [
        {"album": "A", "track": "T", "start": 0.0, "end": 10.0,
         "role": "intro", "source": "human", "heard": True},
        {"album": "A", "track": "T", "start": 8.0, "end": 10.0,
         "role": "outro", "source": "human", "heard": True},
        {"album": "A", "track": "T", "start": 99.0, "end": 100.0,
         "role": "build", "source": "human", "heard": True},
    ], name="rebirth-sections.jsonl")

    drift = audit_lab(tmp_path)["snapshot_drift"]

    assert drift["present"] is True
    assert drift["only_live"] == []
    assert drift["only_snapshot"] == [(99.0, 100.0, "build")]


def test_snapshot_drift_is_empty_for_matching_windows(tmp_path):
    rows = [_keeper("intro", 0.0, 10.0, heard=True)]
    _write_rows(tmp_path, rows)
    _write_rows(tmp_path, rows, name="rebirth-sections.jsonl")

    drift = audit_lab(tmp_path)["snapshot_drift"]

    assert drift["only_live"] == [] and drift["only_snapshot"] == []


def test_snapshot_missing_is_not_an_error(tmp_path):
    _write_rows(tmp_path, [stamp_box(0.0, 4.0, "riff", source="human", heard=True)])

    drift = audit_lab(tmp_path)["snapshot_drift"]

    assert drift["present"] is False
