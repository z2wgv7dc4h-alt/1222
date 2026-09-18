"""Tests for src/boo_lab/sync.py -- tab-vs-audio clock witness. Synthetic
envelopes and tiny files under tmp_path; no real audio/torch."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from boo_lab import extract, sync
from boo_lab.catalogue import save_map

FIX_GPIF = Path(__file__).parent / "fixtures" / "tiny.gp"


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


def test_best_clock_fit_recovers_a_uniform_rate():
    g = _env([i * 1.0 for i in range(1, 10)], n=1200)
    a = _env([i * 1.1 for i in range(1, 10)], n=1200)
    ratio, _lag, score = sync.best_clock_fit(g, a, 0.01, span=0.12, step=0.01)
    assert ratio == pytest.approx(1.1, abs=0.01)
    assert score > 0.9


def _no_chroma(_path):
    raise RuntimeError("no chroma witness in this test")


def _rate_source(monkeypatch, rate):
    """Fake one audio source whose notes are spaced `rate` seconds while the
    tab's are spaced 1.0s. Returns `(env_gp, ev)` with chroma unavailable."""
    gp_times = [i * 1.0 for i in range(1, 30)]
    env_a = sync.envelope_from_times([i * rate for i in range(1, 30)], 4000, 0.01)
    monkeypatch.setattr(sync, "audio_envelope", lambda p: (env_a, 0.01))
    monkeypatch.setattr(sync, "audio_chroma", _no_chroma)
    ev = sync._evaluate_source(Path("x.flac"), Path("x.gp5"), gp_times)
    return gp_times, ev


def test_identical_envelopes_rate_is_one(monkeypatch):
    times = [1.0, 2.0, 3.0]
    env = sync.envelope_from_times(times, 400, 0.01)
    monkeypatch.setattr(sync, "audio_envelope", lambda p: (env, 0.01))
    monkeypatch.setattr(sync, "audio_chroma", _no_chroma)

    ev = sync._evaluate_source(Path("x.flac"), Path("x.gp5"), times)

    assert sync.decide(ev["lag"], ev["score"]) is True
    assert ev["ratio"] == pytest.approx(1.0, abs=0.01)
    assert sync._outcome(ev)[0] == "aligned"


def test_rate_fit_passes_2_7_percent_drift(monkeypatch):
    gp_times, ev = _rate_source(monkeypatch, 1.027)

    # The searched rate wins; ratio=1 alone does not decide.
    assert ev["ratio"] == pytest.approx(1.027, abs=0.01)
    lag0, score0 = sync.best_lag_and_score(
        sync.envelope_from_times(gp_times, 4000, 0.01),
        sync.envelope_from_times([i * 1.027 for i in range(1, 30)], 4000, 0.01), 0.01)
    assert not sync.decide(lag0, score0) or score0 < ev["rscore"]
    assert sync.decide(ev["rlag"], ev["rscore"]) is True
    assert ev["rate_ok"] is True
    assert sync._outcome(ev)[0] == "rate"


def test_twenty_percent_drift_still_fails(monkeypatch):
    _gp_times, ev = _rate_source(monkeypatch, 1.20)

    assert abs(ev["ratio"] - 1.0) <= sync.CLOCK_SPAN + 1e-9
    assert ev["rate_ok"] is False
    assert sync._outcome(ev)[0] == "fail"


def test_searched_ratio_alone_is_not_a_pass():
    # A searched ratio with a bad rate-adjusted lag must stay a fail.
    assert sync.decide(0.9, 0.5) is False
    ev = {"onset_ok": False, "chroma_ok": False, "rate_ok": False,
          "onset_leadin": False, "lag": 2.0, "clag": None,
          "ratio": 1.05, "rlag": 0.9, "rscore": 0.5}
    assert sync._outcome(ev)[0] == "fail"


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


def test_prefer_gpif_path_finds_a_sibling(tmp_path, monkeypatch):
    monkeypatch.delenv("BOO_GP_ROOT", raising=False)
    gp5 = tmp_path / "07 Test.gp5"
    gp5.write_bytes(b"x")
    gp = tmp_path / "07 - Test.gp"          # same stem, "07 -" vs "07 "
    shutil.copy(FIX_GPIF, gp)

    chosen = sync._prefer_gpif_path(gp5)

    assert chosen == gp and chosen.name.endswith(".gp")
    onsets = sync.gp_onset_times(chosen)     # the GPIF clock is now used
    assert onsets is not None and len(onsets) == 10


def test_prefer_gpif_path_lone_gp5_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("BOO_GP_ROOT", raising=False)
    gp5 = tmp_path / "Lone.gp5"
    gp5.write_bytes(b"x")

    assert sync._prefer_gpif_path(gp5) == gp5


def test_gp_path_clocks_gpif_first(tmp_path, monkeypatch):
    gp = tmp_path / "T.gp"
    shutil.copy(FIX_GPIF, gp)
    import guitarpro

    monkeypatch.setattr(guitarpro, "parse",
                        lambda p: (_ for _ in ()).throw(AssertionError("guitarpro tried first")))

    events = sync._tab_notes(gp)

    assert events and len(events) == 10 and len(events[0]) == 4
    assert sync._tab_play_seconds(gp) == pytest.approx(8.0)


def test_lone_gp5_goes_through_guitarpro(tmp_path, monkeypatch):
    gp5 = tmp_path / "Lone.gp5"
    gp5.write_bytes(b"x")
    import guitarpro

    calls = []

    def _boom(p):
        calls.append(p)
        raise RuntimeError("parse")

    monkeypatch.setattr(guitarpro, "parse", _boom)

    assert sync._tab_notes(gp5) is None      # not GPIF-first
    assert calls                             # guitarpro.parse was attempted


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


def _map_lab(tmp_path, rows):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    save_map(lab / "data" / "map.csv", rows)
    return lab


def test_sync_resolves_studio_names(tmp_path, monkeypatch):
    monkeypatch.delenv("BOO_GP_ROOT", raising=False)  # no real GP7 sibling
    gp = tmp_path / "07 Exist.gp5"
    gp.write_bytes(b"x")
    flac = tmp_path / "07 - Exist.flac"
    flac.write_bytes(b"x")
    lab = _map_lab(tmp_path, [{
        "album": "2009 - A Higher Place", "track": "07 - Exist",
        "flac": str(flac), "gp": str(gp),
    }])

    rec = sync.sync_track(lab, "A Higher Place", "07 - Exist")

    assert rec["note"] == "unreadable-gp"  # resolved the row and read the gp
    assert rec["album"] == "2009 - A Higher Place"
    assert rec["track"] == "07 - Exist"
    assert rec["gp"] == str(gp)


def test_sync_no_row_is_distinct_from_no_gp(tmp_path):
    lab = _map_lab(tmp_path, [{
        "album": "2009 - A Higher Place", "track": "07 - Exist",
        "flac": "", "gp": "",
    }])

    no_gp = sync.sync_track(lab, "A Higher Place", "07 - Exist")
    assert no_gp["note"] == "no-gp"
    assert no_gp["album"] == "2009 - A Higher Place"

    no_row = sync.sync_track(lab, "A Higher Place", "99 - Nope")
    assert no_row["note"] == "no-row"


def test_sync_fail_note_carries_durations(tmp_path, monkeypatch):
    gp = tmp_path / "x.gp5"
    gp.write_bytes(b"x")
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"x")
    lab = _lab(tmp_path, gp=gp, flac=flac)
    monkeypatch.setattr(sync, "gp_onset_times", lambda p: [0.0])
    monkeypatch.setattr(sync, "_evaluate_source", lambda src, g, o: {
        "lag": 27.0, "score": 0.2, "prom": 0.0, "ratio": 1.0, "rlag": 27.0,
        "rscore": 0.2, "clag": None, "cscore": None, "onset_ok": False,
        "chroma_ok": False, "rate_ok": False, "onset_leadin": False})
    monkeypatch.setattr(sync, "_tab_play_seconds", lambda p: 100.0)
    monkeypatch.setattr(sync, "_audio_seconds", lambda p: 97.3)

    rec = sync.sync_track(lab, "A", "T")

    assert rec["sync_ok"] is False  # a 27s lag stays a fail
    assert "tab_play=100.0s flac=97.3s dly=27.00s" in rec["note"]


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


def test_sync_track_reports_a_rate_pass(tmp_path, monkeypatch):
    gp = tmp_path / "x.gp5"
    gp.write_bytes(b"x")
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"x")
    lab = _lab(tmp_path, gp=gp, flac=flac)
    gp_times = [i * 1.0 for i in range(1, 30)]
    env_a = sync.envelope_from_times([i * 1.027 for i in range(1, 30)], 4000, 0.01)
    monkeypatch.setattr(sync, "gp_onset_times", lambda p: gp_times)
    monkeypatch.setattr(sync, "audio_envelope", lambda p: (env_a, 0.01))
    monkeypatch.setattr(sync, "audio_chroma", _no_chroma)

    rec = sync.sync_track(lab, "A", "T")

    assert rec["sync_ok"] is True
    assert rec["clock_ratio"] == pytest.approx(1.027, abs=0.01)
    assert rec["note"].startswith("ok (rate")


def test_chroma_lag_and_score_identical_matrices():
    import numpy as np

    c = np.random.default_rng(0).random((12, 300))
    lag, score = sync.chroma_lag_and_score(c, c, 0.01)
    assert abs(lag) < 1e-9 and score > 0.9


def test_chroma_co_witness_can_bless(tmp_path, monkeypatch):
    import numpy as np

    gp = tmp_path / "x.gp5"
    gp.write_bytes(b"x")
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"x")
    lab = _lab(tmp_path, gp=gp, flac=flac)
    # onset witness fails (impulse beyond the envelope)...
    monkeypatch.setattr(sync, "gp_onset_times", lambda p: [10.0])
    monkeypatch.setattr(
        sync, "audio_envelope",
        lambda p: (sync.envelope_from_times([0.0], 400, 0.01), 0.01))
    # ...but the chroma witness matches perfectly.
    monkeypatch.setattr(sync, "audio_chroma", lambda p: (np.ones((12, 400)), 0.01))
    monkeypatch.setattr(sync, "gp_chroma", lambda p, h, n: np.ones((12, n)))

    rec = sync.sync_track(lab, "A", "T")

    assert rec["sync_ok"] is True and rec["note"] == "ok (chroma)"


def test_best_alignment_reports_prominence_on_an_offset():
    env = _env([i * 0.5 for i in range(1, 12)], n=800)
    shifted = sync.envelope_from_times([0.5 + i * 0.5 for i in range(1, 12)], 800, 0.01)
    lag, score, prom = sync.best_alignment(env, shifted, 0.01)
    assert abs(abs(lag) - 0.5) < 0.05
    assert score > 0.3 and prom > sync.PROMINENCE_MIN


def test_outcome_lead_in_requires_corroboration():
    ev = {"onset_ok": False, "chroma_ok": False, "onset_leadin": True,
          "lag": 1.0, "clag": 1.05}
    assert sync._outcome(ev) == ("lead-in", 1.0)
    ev["clag"] = 3.0  # the other witness disagrees -> not a lead-in
    assert sync._outcome(ev)[0] == "fail"


def test_sync_track_marks_a_lead_in(tmp_path, monkeypatch):
    gp = tmp_path / "x.gp5"
    gp.write_bytes(b"x")
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"x")
    lab = _lab(tmp_path, gp=gp, flac=flac)
    monkeypatch.setattr(sync, "gp_onset_times", lambda p: [0.0, 1.0])
    monkeypatch.setattr(sync, "_evaluate_source", lambda src, g, o: {
        "lag": 0.8, "score": 0.2, "prom": 0.1, "ratio": 1.0, "rscore": 0.2,
        "clag": 0.82, "cscore": 0.2, "onset_ok": False, "chroma_ok": False,
        "onset_leadin": True})

    rec = sync.sync_track(lab, "A", "T")

    assert rec["sync_ok"] is True and rec["offset_sec"] == 0.8
    assert rec["note"] == "ok (lead-in 0.80s)"


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
