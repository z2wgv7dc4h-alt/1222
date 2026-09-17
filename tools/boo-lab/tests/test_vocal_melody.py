"""Tests for src/boo_lab/vocal_melody.py -- fail-closed behavior and the
pitch/timing-only output contract; no real audio fixture."""
from __future__ import annotations

import json

import pytest

from boo_lab import vocal_melody as vm


def test_build_vocal_melody_ignores_non_keeper_rows(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 5.0, "role": "riff", "source": "human"}) + "\n"
        + json.dumps({"album": "A", "track": "T", "start": 6.0, "end": 9.0, "role": "intro", "source": "msa-draft"}) + "\n",
        encoding="utf-8",
    )
    vm.build_vocal_melody(lab, [], lab / "work" / "stems")
    rows = [json.loads(l) for l in (lab / "data" / "vocal_melody.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 1 and rows[0]["role"] == "riff"


def test_extract_vocal_melody_rejects_unknown_backend(tmp_path):
    with pytest.raises(ValueError):
        vm.extract_vocal_melody(tmp_path / "x.flac", tmp_path, backend="nope")


def test_extract_vocal_melody_no_cached_stem_returns_empty(tmp_path):
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"x")
    assert vm.extract_vocal_melody(flac, tmp_path / "cache", backend="pyin") == []


def test_output_shape_is_pitch_and_timing_only():
    # The exact schema contract: no word/lyric/text field can exist.
    expected_keys = {"time", "midi_pitch", "duration"}
    note = {"time": 1.0, "midi_pitch": 60, "duration": 0.2}
    assert set(note) == expected_keys
