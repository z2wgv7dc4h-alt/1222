"""Scoring honesty with empty (or holdout-only) gold.

compare / adapt / learn must not vote prefer= from holdout/VAL songs and must
not require the deleted Rebirth rows to exist.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from boo_lab import learn
from boo_lab.compare import compare, format_report

LAB = Path(__file__).resolve().parents[1]
HOLDOUT = LAB / "data" / "holdout.csv"
REBIRTH = ("2009 - A Higher Place", "01 - Rebirth")


def _lab(tmp_path: Path) -> Path:
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    shutil.copyfile(HOLDOUT, lab / "data" / "holdout.csv")  # the frozen seven
    return lab


def _write(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _keeper(album, track, start, end, role="riff", **extra):
    rec = {"album": album, "track": track, "start": start, "end": end,
           "role": role, "source": "human", "heard": True}
    rec.update(extra)
    return rec


def _draft(album, track, start, end, role="riff", source="msa-draft"):
    return {"album": album, "track": track, "start": start, "end": end,
            "role": role, "source": source, "heard": False}


# --- empty gold --------------------------------------------------------------


def test_empty_gold_plus_holdout_yields_prefer_none(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "sections.jsonl").write_text("", encoding="utf-8")
    _write(lab / "data" / "drafts.jsonl", [_draft("A", "T", 1.0, 2.0)])

    rank = learn.build_rank(lab)

    assert rank["prefer"] == "none"
    assert rank["n_voted"] == 0


# --- holdout-only gold -------------------------------------------------------


def test_only_holdout_rebirth_keepers_yield_prefer_none(tmp_path):
    lab = _lab(tmp_path)
    _write(lab / "data" / "sections.jsonl", [
        _keeper(*REBIRTH, 1.0, 2.0, role="intro"),
        _keeper(*REBIRTH, 3.0, 4.0, role="outro"),
    ])
    _write(lab / "data" / "drafts.jsonl", [
        _draft(*REBIRTH, 1.0, 2.0, role="intro"),
        _draft(*REBIRTH, 3.0, 4.0, role="outro"),
    ])

    rank = learn.build_rank(lab)

    assert rank["prefer"] == "none"
    assert rank["n_voted"] == 0
    assert rank["scores"] == {}


def test_holdout_song_is_not_in_the_vote_set():
    report = {"tracks": [
        {"album": "A", "track": "Fake Train", "split": "train", "source": "msa-draft",
         "n_keep": 1, "n_draft": 1},
        {"album": REBIRTH[0], "track": REBIRTH[1], "split": "holdout",
         "source": "msa-draft", "n_keep": 1, "n_draft": 1},
    ]}

    voted = learn._qualifying(report, include_holdout=False)

    assert [(t["album"], t["track"]) for t in voted] == [("A", "Fake Train")]


def test_non_holdout_keepers_can_vote_without_the_holdout_song(tmp_path):
    lab = _lab(tmp_path)
    train = [_keeper("A", f"Track {i:02d}", float(i), float(i) + 1.0) for i in range(5)]
    _write(lab / "data" / "sections.jsonl", train + [
        _keeper(*REBIRTH, 1.0, 2.0, role="intro"),
    ])
    _write(lab / "data" / "drafts.jsonl",
           [_draft("A", f"Track {i:02d}", float(i), float(i) + 1.0) for i in range(5)]
           + [_draft(*REBIRTH, 1.0, 2.0, role="intro")])

    rank = learn.build_rank(lab)

    assert rank["prefer"] == "msa-draft"     # a real vote may run
    assert rank["n_voted"] == 5              # the holdout Rebirth song is excluded


# --- compare labelling / safety ----------------------------------------------


def test_compare_labels_holdout_rows_not_used_for_prefer(tmp_path):
    lab = _lab(tmp_path)
    _write(lab / "data" / "sections.jsonl", [_keeper(*REBIRTH, 1.0, 2.0, role="intro")])
    _write(lab / "data" / "drafts.jsonl", [_draft(*REBIRTH, 1.0, 2.0, role="intro")])

    rep = compare(lab)

    assert rep["tracks"][0]["split"] == "holdout"
    assert rep["tracks"][0]["not_used_for_prefer"] is True
    assert "not used for prefer=" in format_report(rep)


def test_compare_skips_a_track_with_no_keepers(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "sections.jsonl").write_text("", encoding="utf-8")
    _write(lab / "data" / "drafts.jsonl", [_draft("A", "No Keepers", 1.0, 2.0)])

    rep = compare(lab)

    assert rep["tracks"] == []
    assert rep["micro"]["n_tracks"] == 0
