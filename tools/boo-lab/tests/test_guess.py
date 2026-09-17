"""Tests for src/boo_lab/guess.py -- synthetic beats/sections only, no real
audio fixture. Covers the half-time detector, the section cleaner, and the
coverage-note logic (threshold + exact message format)."""
from __future__ import annotations

import json
import types

import pytest

soundfile = pytest.importorskip("soundfile")

from boo_lab import guess as g  # noqa: E402


# --- _norm -------------------------------------------------------------------


def test_norm_strips_leading_track_number_and_accents():
    assert g._norm("03 - ∆eon III") == "aeoniii"
    assert g._norm("Born_Of_Osiris-Recreate") == "bornofosirisrecreate"
    assert g._norm(None) == ""
    assert g._norm("") == ""


# --- _scalar / _flist bad input ---------------------------------------------


def test_scalar_and_flist_handle_bad_input():
    assert g._scalar([3.5]) == 3.5
    assert g._scalar(None) is None
    assert g._flist([1, 2]) == [1.0, 2.0]
    assert g._flist(None) == []


# --- _half_time_spans --------------------------------------------------------


def test_half_time_spans_detects_a_known_half_time_stretch():
    # 24 eighth-note beats at 0.5s spacing, then a real half-time stretch at
    # 1.0s spacing (16 beats). med IOI = 0.5s; the stretch clears the 1.65x
    # threshold and lasts well past the 6.0s minimum.
    beats = [i * 0.5 for i in range(24)] + [12.0 + i * 1.0 for i in range(16)]
    spans = g._half_time_spans(beats)

    assert len(spans) == 1
    assert spans[0]["role"] == "breakdown"
    assert spans[0]["source"] == "halftime"
    assert spans[0]["end"] - spans[0]["start"] >= 6.0


def test_half_time_spans_bad_input_is_empty():
    assert g._half_time_spans([]) == []
    assert g._half_time_spans([1.0] * 10) == []  # fewer than 24 beats
    assert g._half_time_spans([5.0] * 30) == []  # zero IOI -> median guard


def test_half_time_spans_ignores_a_too_short_stretch():
    # A single doubled IOI is well under the 6.0s min_len.
    beats = [i * 0.5 for i in range(24)] + [12.0, 13.0]
    assert g._half_time_spans(beats) == []


# --- _clean ------------------------------------------------------------------


def test_clean_merges_overlapping_same_role():
    # overlap 3.0 / span 4.0 = 0.75, above the 0.7 merge threshold.
    sections = [
        {"role": "breakdown", "start": 0.0, "end": 5.0},
        {"role": "breakdown", "start": 2.0, "end": 6.0},
    ]
    out = g._clean(sections)
    assert len(out) == 1
    assert out[0]["start"] == 0.0
    assert out[0]["end"] == 6.0


def test_clean_keeps_different_roles_separate():
    sections = [
        {"role": "breakdown", "start": 0.0, "end": 5.0},
        {"role": "solo", "start": 4.0, "end": 9.0},
    ]
    assert len(g._clean(sections)) == 2


def test_clean_does_not_merge_below_overlap_threshold():
    # overlap 2.0 / span 4.0 = 0.5, at or below the 0.7 merge threshold.
    sections = [
        {"role": "verse", "start": 0.0, "end": 10.0},
        {"role": "verse", "start": 8.0, "end": 12.0},
    ]
    assert len(g._clean(sections)) == 2


def test_clean_drops_invalid_and_malformed_entries():
    sections = [
        {"role": "intro", "start": 5.0, "end": 5.0},   # end <= start
        {"role": "intro", "start": 10.0, "end": 2.0},  # end < start
        {"role": "intro"},                              # missing start/end
        "not a dict",
        {"role": "intro", "start": 0.0, "end": 1.0},
    ]
    assert g._clean(sections) == [{"role": "intro", "start": 0.0, "end": 1.0}]


# --- coverage-note logic (via estimate_hybrid) -------------------------------


def _wire_estimate(monkeypatch, tmp_path, covered_end, real_duration=100.0):
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    fake_info = types.SimpleNamespace(frames=int(22050 * real_duration), samplerate=22050)
    monkeypatch.setattr(soundfile, "info", lambda *a, **k: fake_info)
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_gp5", lambda gp, track: None)
    monkeypatch.setattr(g, "_drum_stem", lambda flac: None)
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [i * 0.5 for i in range(30)], "bpm": 120.0})
    monkeypatch.setattr(
        g, "_half_time_spans",
        lambda beats, min_len=6.0: [{"role": "breakdown", "start": 0.0, "end": covered_end, "source": "halftime"}],
    )
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])
    return g.estimate_hybrid(flac, None, track="Fixture", cache=None)


def test_coverage_note_flags_uncovered_tail_with_exact_message(tmp_path, monkeypatch):
    result = _wire_estimate(monkeypatch, tmp_path, covered_end=40.0)
    expected = (
        "Guess reached 40.0s of 100.0s (40%) -- 60.0s uncovered at the end, paint it by hand"
    )
    assert expected in result["notes"]


def test_coverage_note_suppressed_within_five_seconds_of_end(tmp_path, monkeypatch):
    result = _wire_estimate(monkeypatch, tmp_path, covered_end=96.0)  # 4.0s uncovered
    assert not any(n.startswith("Guess reached") for n in result["notes"])


# --- tab-marker sync gate ----------------------------------------------------


def _wire_gp_estimate(tmp_path, monkeypatch, sync_ok):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "sync_ok": sync_ok, "lag_sec": 0.05}) + "\n",
        encoding="utf-8",
    )
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_gp5", lambda gp, track: tmp_path / "x.gp5")
    import boo_lab.extract as ex
    monkeypatch.setattr(ex, "estimate_from_gp", lambda p: {
        "bpm": 120, "duration": 10,
        "sections": [{"role": "riff", "start": 0, "end": 5, "source": "gp-marker"}],
    })
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [i * 0.5 for i in range(30)], "bpm": 120.0})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])
    return g.estimate_hybrid(flac, tmp_path / "x.gp5", track="Fixture",
                             cache=lab / "work" / "stems", album="A")


def test_guess_drops_tab_markers_when_sync_not_ok(tmp_path, monkeypatch):
    res = _wire_gp_estimate(tmp_path, monkeypatch, sync_ok=False)
    assert not any(s.get("source") == "gp-marker" for s in res["sections"])
    assert any("sync not ok" in n for n in res["notes"])


def test_guess_keeps_tab_markers_when_sync_ok(tmp_path, monkeypatch):
    res = _wire_gp_estimate(tmp_path, monkeypatch, sync_ok=True)
    assert any(s.get("source") == "gp-marker" for s in res["sections"])
    assert any("gp markers (sync ok)" in n for n in res["notes"])
