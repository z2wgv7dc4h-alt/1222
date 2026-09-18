"""Tests for src/boo_lab/cells.py -- fake one-bar fragments + tmp lab_root.
No guitarpro, no FLAC, no network."""
from __future__ import annotations

from boo_lab import cells


def _frag(mi, pc=0, raw=None, role=None):
    return {
        "measure_index": mi,
        "cell": [{"duration": 1.0, "is_rest": False}],
        "deltas": [0],
        "chord_notes": [[pc]],
        "chord_frets": [[(6, 0)]],
        "role": role,
        "raw_marker": raw,
        "source_song": "S",
        "source_file": "s.gp5",
        "track": "Gtr",
        "instrument": "guitar",
        "source_type": "tab_verbatim",
    }


def _slots(n):
    return [(mi, mi * 2.0, mi + 1, 2.0) for mi in range(n)]


def test_long_human_box_becomes_short_window_cell():
    frags = [_frag(mi) for mi in range(8)]
    human = [{"figure_id": "riff-A", "start": 0.0, "end": 16.0}]
    figs = [{"figure_id": "riff-A", "n_bars": 2, "occurrences": [
        {"start": 0.0, "end": 4.0, "start_bar": 1, "end_bar": 2},
        {"start": 8.0, "end": 12.0, "start_bar": 5, "end_bar": 6},
    ]}]

    result, skipped_long = cells.assemble_cells(
        frags, _slots(8), human, figs, True,
        source_song="S", album="A", track="T")

    assert len(result) == 1
    cell = result[0]
    assert cell["figure_id"] == "riff-A" and cell["n_bars"] == 2  # not 8
    assert len(cell["cell"]) == 2
    assert [o["start_bar"] for o in cell["occurrences"]] == [1, 5]
    assert skipped_long == 1  # the 8-bar human span was reduced


def test_identical_run_without_figures_becomes_two_bars():
    frags = [_frag(0, pc=0), _frag(1, pc=0), _frag(2, pc=5)]

    result, _skipped = cells.assemble_cells(
        frags, _slots(3), [], [], False,
        source_song="S", album="A", track="T")

    two_bar = [c for c in result if c["n_bars"] == 2]
    assert len(two_bar) == 1
    assert len(two_bar[0]["cell"]) == 2  # the two identical bars, in order
    assert all(c["n_bars"] <= 2 for c in result)


def test_build_cells_zero_rows_does_not_blank_existing(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    out = lab / "data" / "riffs.jsonl"
    out.write_text('{"figure_id":"riff-A","n_bars":2}\n', encoding="utf-8")
    before = out.read_text(encoding="utf-8")

    report = cells.build_cells(lab, [])

    assert report["cells"] == 0
    assert out.read_text(encoding="utf-8") == before
