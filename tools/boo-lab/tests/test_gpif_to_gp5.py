"""Tests for src/boo_lab/gpif_to_gp5.py + the sync GPIF fallback.

Uses the hand-made `tests/fixtures/tiny.gp`; no commercial tab is vendored.
Round-trips through real pyguitarpro write/parse.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boo_lab import gpif, gpif_to_gp5, sync

FIX = Path(__file__).parent / "fixtures" / "tiny.gp"


def test_round_trips_the_tiny_gpif(tmp_path):
    import guitarpro

    score = gpif.load_score(FIX)
    out = tmp_path / "tiny.from-gpif.gp5"

    written, drops = gpif_to_gp5.gpif_to_gp5(score, out)

    assert written == out and out.exists()
    assert drops == []
    parsed = guitarpro.parse(str(out))
    assert parsed.title == "Tiny"
    assert len(parsed.measureHeaders) == 2
    assert len(parsed.tracks) == 1
    # repeats survived as GP5 repeat flags
    assert parsed.measureHeaders[0].isRepeatOpen is True
    assert parsed.measureHeaders[1].repeatClose == 1
    beats = [b for m in parsed.tracks[0].measures for b in m.voices[0].beats]
    assert sum(len(b.notes) for b in beats) == 4


def test_drum_track_skipped_and_guitar_kept(tmp_path):
    import guitarpro

    score = gpif.GpifScore(
        title="TwoTracks", tempo=120.0,
        tracks=[gpif.GpifTrack("Drums", []), gpif.GpifTrack("Guitar", [40, 45, 50, 55, 59, 64])],
        masterbars=[gpif.GpifMasterBar(4, 4, False, False, 0, None)],
        notes=[gpif.GpifNote(1, 0, 0.0, 1, 3, 1.0, False)],
    )
    out = tmp_path / "two.gp5"

    written, drops = gpif_to_gp5.gpif_to_gp5(score, out)

    assert any("drum" in d.lower() for d in drops)
    parsed = guitarpro.parse(str(written))
    assert [t.name for t in parsed.tracks] == ["Guitar"]


def test_out_of_range_string_is_dropped(tmp_path):
    score = gpif.GpifScore(
        title="Eight", tempo=120.0,
        tracks=[gpif.GpifTrack("Guitar", [40, 45, 50, 55, 59, 64])],
        masterbars=[gpif.GpifMasterBar(4, 4, False, False, 0, None)],
        notes=[gpif.GpifNote(0, 0, 0.0, 1, 3, 1.0, False),
               gpif.GpifNote(0, 0, 1.0, 8, 1, 1.0, False)],
    )
    out = tmp_path / "eight.gp5"

    written, drops = gpif_to_gp5.gpif_to_gp5(score, out)

    assert any("string 8" in d for d in drops)
    assert written.exists()


def test_no_playable_tracks_raises(tmp_path):
    score = gpif.GpifScore(
        title="OnlyDrums", tempo=120.0,
        tracks=[gpif.GpifTrack("Percussion", [])],
        masterbars=[gpif.GpifMasterBar(4, 4, False, False, 0, None)],
        notes=[gpif.GpifNote(0, 0, 0.0, 1, 1, 1.0, False)],
    )
    with pytest.raises(ValueError):
        gpif_to_gp5.gpif_to_gp5(score, tmp_path / "drums.gp5")


def test_sync_falls_back_to_gpif_onsets_and_duration():
    # pyguitarpro cannot read the zip, so the GPIF path clocks the tab.
    onsets = sync.gp_onset_times(FIX)
    assert onsets is not None
    assert len(onsets) == 8  # 4 notes x 2 repeat passes
    assert onsets[0] == 0.0
    assert sync._tab_play_seconds(FIX) == pytest.approx(8.0)


def test_gpif_events_none_for_a_non_gp_suffix(tmp_path):
    other = tmp_path / "x.gp5"
    other.write_bytes(b"nope")
    assert sync._gpif_events(other) is None
