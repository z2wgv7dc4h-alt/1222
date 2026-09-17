"""Tests for src/boo_lab/sync.py -- tab-vs-audio clock witness. Synthetic
envelopes and tiny files under tmp_path; no real audio/torch."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from boo_lab import extract, sync
from boo_lab.catalogue import save_map


def _env(times, n=400, hop=0.01):
    return sync.envelope_from_times(times, n, hop)


def test_identical_envelopes_are_sync_ok():
    times = [1.0, 1.5, 2.0, 2.5, 3.0]
    env = _env(times)
    lag, score = sync.best_lag_and_score(env, env, 0.01)
    assert abs(lag) < 1e-9 and score > 0.9
    assert sync.decide(lag, score) is True


def test_two_second_shift_is_not_ok():
    import numpy as np

    env = _env([1.0, 1.5, 2.0, 2.5, 3.0])
    shifted = np.concatenate([np.zeros(200), env[:-200]])  # +2.0s at hop=0.01
    lag, score = sync.best_lag_and_score(env, shifted, 0.01)
    assert abs(lag) >= sync.LAG_TOLERANCE
    assert sync.decide(lag, score) is False


def test_low_score_is_not_ok():
    import numpy as np

    rng = np.random.default_rng(0)
    assert sync.decide(0.0, float(rng.random() * 0.01)) is False


def test_sync_refuses_without_track(tmp_path):
    with pytest.raises(ValueError):
        sync.sync_track(tmp_path, "A", None)


class _H:
    def __init__(self, **kw):
        self.isRepeatOpen = kw.get("isRepeatOpen", False)
        self.repeatAlternative = kw.get("repeatAlternative", 0)
        self.repeatClose = kw.get("repeatClose", -1)


class _M:
    def __init__(self, **kw):
        self.header = _H(**kw)


def test_playback_order_expands_a_simple_repeat():
    measures = [_M(), _M(isRepeatOpen=True), _M(repeatClose=1), _M()]
    assert sync._playback_order(measures) == [0, 1, 2, 1, 2, 3]


def test_playback_order_handles_alternative_endings():
    measures = [
        _M(),
        _M(isRepeatOpen=True),
        _M(repeatClose=1, repeatAlternative=1),
        _M(repeatAlternative=2),
        _M(),
    ]
    assert sync._playback_order(measures) == [0, 1, 2, 1, 3, 4]


def test_gp_onset_times_uses_song_tempo(monkeypatch):
    class _Dur:
        value = 4
        isDotted = False

    class _Beat:
        notes = [1]
        duration = _Dur()

    class _Voice:
        beats = [_Beat(), _Beat(), _Beat(), _Beat()]

    class _Header:
        tempo = None

    class _Measure:
        header = _Header()
        voices = [_Voice()]

    class _Track:
        name = "Guitar"
        measures = [_Measure(), _Measure()]

    class _Song:
        tempo = 195
        tracks = [_Track()]

    class _FakeGP:
        @staticmethod
        def parse(_p):
            return _Song()

    monkeypatch.setitem(sys.modules, "guitarpro", _FakeGP)
    monkeypatch.setattr(extract, "_rhythm_track", lambda song: song.tracks[0])

    onsets = sync.gp_onset_times(Path("x.gp5"))

    beat = 60.0 / 195  # song.tempo, NOT the old 120 default
    assert len(onsets) == 8
    assert onsets[0] == 0.0
    assert onsets[4] == pytest.approx(4 * beat, abs=1e-4)


def _lab(tmp_path, gp=None, flac=None):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    save_map(lab / "data" / "map.csv", [{
        "album": "A", "track": "T",
        "flac": str(flac) if flac else "",
        "gp": str(gp) if gp else "",
    }])
    return lab


def test_sync_missing_gp_is_false(tmp_path):
    lab = _lab(tmp_path)
    rec = sync.sync_track(lab, "A", "T")
    assert rec["sync_ok"] is False and rec["note"] == "no-gp"
    rows = [json.loads(l) for l in (lab / "data" / "sync.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 1 and rows[0]["track"] == "T"


def test_sync_unreadable_gp_is_false(tmp_path):
    gp = tmp_path / "bad.gp5"
    gp.write_bytes(b"not a guitar pro file")
    lab = _lab(tmp_path, gp=gp)
    rec = sync.sync_track(lab, "A", "T")
    assert rec["sync_ok"] is False and rec["note"] == "unreadable-gp"


def test_sync_ok_with_mocked_envelopes(tmp_path, monkeypatch):
    gp = tmp_path / "x.gp5"
    gp.write_bytes(b"x")
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"x")
    lab = _lab(tmp_path, gp=gp, flac=flac)
    times = [1.0, 2.0, 3.0]
    monkeypatch.setattr(sync, "gp_onset_times", lambda p: times)
    monkeypatch.setattr(sync, "audio_envelope", lambda p: (sync.envelope_from_times(times, 400, 0.01), 0.01))

    rec = sync.sync_track(lab, "A", "T")

    assert rec["sync_ok"] is True and rec["used_stem"] == "mix"
    assert rec["lag_sec"] == 0.0


def test_sync_uses_cached_guitar_stem(tmp_path, monkeypatch):
    gp = tmp_path / "x.gp5"
    gp.write_bytes(b"x")
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"x")
    lab = _lab(tmp_path, gp=gp, flac=flac)
    stem_dir = lab / "work" / "stems" / "htdemucs_6s" / "x"
    stem_dir.mkdir(parents=True)
    (stem_dir / "guitar.wav").write_bytes(b"RIFF")
    times = [1.0, 2.0]
    monkeypatch.setattr(sync, "gp_onset_times", lambda p: times)
    monkeypatch.setattr(sync, "audio_envelope", lambda p: (sync.envelope_from_times(times, 400, 0.01), 0.01))

    rec = sync.sync_track(lab, "A", "T")

    assert rec["used_stem"] == "guitar"
