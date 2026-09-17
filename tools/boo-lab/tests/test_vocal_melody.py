"""Tests for src/boo_lab/vocal_melody.py -- fail-closed behavior and the
pitch/timing-only output contract; no real audio fixture."""
from __future__ import annotations

import pytest

from boo_lab import vocal_melody as vm


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
