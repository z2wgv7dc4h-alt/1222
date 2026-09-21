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


# --- beat-grid snapping of audio spans ---------------------------------------


def test_snap_to_grid_prefers_downbeat_then_beat():
    assert g._snap_to_grid(1.92, [0.0, 2.0], [1.9, 1.95]) == 2.0   # 80ms -> downbeat
    assert g._snap_to_grid(1.02, [0.0], [1.0, 1.05]) == 1.0       # no nearby downbeat -> beat
    assert g._snap_to_grid(5.0, [0.0, 2.0], [1.9, 1.95]) == 5.0   # too far -> unchanged


def test_guess_snaps_audio_breakdown_spans_to_the_grid(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "beats.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "beats": [1.0, 2.0, 3.0, 4.0],
                    "downbeats": [2.0], "source": "beat_this"}) + "\n",
        encoding="utf-8",
    )
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_gp5", lambda gp, track: None)
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans",
                        lambda beats, min_len=6.0: [{"role": "breakdown", "start": 1.93,
                                                     "end": 3.9, "source": "halftime"}])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])

    res = g.estimate_hybrid(flac, None, track="Fixture", cache=lab / "work" / "stems", album="A")

    bd = res["sections"][0]
    assert bd["start"] == 2.0 and bd["end"] == 4.0  # snapped to downbeat/beat
    assert any("snapped" in n for n in res["notes"])


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


# --- clock-ratio stretch of tab markers --------------------------------------


def _wire_gp_ratio(tmp_path, monkeypatch, *, sync_ok, ratio, markers=None):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    rec = {"album": "A", "track": "Fixture", "sync_ok": sync_ok}
    if ratio is not None:
        rec["clock_ratio"] = ratio
    (lab / "data" / "sync.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_gp5", lambda gp, track: tmp_path / "x.gp5")
    seed = markers if markers is not None else [
        {"role": "riff", "start": 10.0, "end": 14.0, "source": "gp-marker"}]
    import boo_lab.extract as ex
    monkeypatch.setattr(ex, "estimate_from_gp",
                        lambda p: {"bpm": 120, "duration": 100,
                                   "sections": [dict(s) for s in seed]})
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])
    return g.estimate_hybrid(flac, tmp_path / "x.gp5", track="Fixture",
                             cache=lab / "work" / "stems", album="A")


def test_guess_stretches_markers_by_clock_ratio(tmp_path, monkeypatch, capsys):
    res = _wire_gp_ratio(tmp_path, monkeypatch, sync_ok=True, ratio=1.027)

    gp = [s for s in res["sections"] if s.get("source") == "gp-marker"]
    assert len(gp) == 1
    assert gp[0]["start"] == pytest.approx(10.0 * 1.027, abs=1e-3)
    assert gp[0]["end"] == pytest.approx(14.0 * 1.027, abs=1e-3)
    assert "guess: clock_ratio=1.027 stretched 1 markers" in capsys.readouterr().out


def test_guess_drops_markers_when_not_sync_ok_even_with_ratio(tmp_path, monkeypatch):
    res = _wire_gp_ratio(tmp_path, monkeypatch, sync_ok=False, ratio=1.027)
    assert not any(s.get("source") == "gp-marker" for s in res["sections"])


def test_guess_ratio_one_leaves_marker_times_unchanged(tmp_path, monkeypatch):
    res = _wire_gp_ratio(tmp_path, monkeypatch, sync_ok=True, ratio=1.0)
    gp = [s for s in res["sections"] if s.get("source") == "gp-marker"][0]
    assert gp["start"] == 10.0 and gp["end"] == 14.0


def test_audio_breakdown_draft_is_not_stretched(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "sync_ok": True,
                    "clock_ratio": 1.027}) + "\n",
        encoding="utf-8",
    )
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_gp5", lambda gp, track: tmp_path / "x.gp5")
    import boo_lab.extract as ex
    monkeypatch.setattr(ex, "estimate_from_gp",
                        lambda p: {"bpm": 120, "duration": 100, "sections": []})
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans",
                        lambda beats, min_len=6.0: [{"role": "breakdown", "start": 20.0,
                                                     "end": 30.0, "source": "halftime"}])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])

    res = g.estimate_hybrid(flac, tmp_path / "x.gp5", track="Fixture",
                            cache=lab / "work" / "stems", album="A")

    bd = [s for s in res["sections"] if s.get("source") == "halftime"][0]
    assert bd["start"] == 20.0 and bd["end"] == 30.0


# --- figure-window drafts + breakdown gate -----------------------------------


def _wire_figures(tmp_path, monkeypatch, *, sync_ok, times_trusted=True):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "sync_ok": sync_ok}) + "\n",
        encoding="utf-8",
    )
    (lab / "data" / "figures.jsonl").write_text(json.dumps({
        "album": "A", "track": "Fixture", "figure_id": "riff-A",
        "times_trusted": times_trusted,
        "occurrences": [{"start": 1.0, "end": 3.0, "start_bar": 1, "end_bar": 2},
                        {"start": 10.0, "end": 12.0, "start_bar": 5, "end_bar": 6}],
    }) + "\n", encoding="utf-8")
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_gp5", lambda gp, track: None)
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])
    return g.estimate_hybrid(flac, None, track="Fixture",
                             cache=lab / "work" / "stems", album="A")


def test_guess_adds_figure_drafts_when_sync_ok(tmp_path, monkeypatch):
    res = _wire_figures(tmp_path, monkeypatch, sync_ok=True)

    figs = [s for s in res["sections"]
            if s.get("source") == "guess" and s.get("figure_id") == "riff-A"]
    assert len(figs) == 2
    assert all(s["heard"] is False for s in figs)


def test_guess_no_figure_drafts_when_not_sync_ok(tmp_path, monkeypatch):
    res = _wire_figures(tmp_path, monkeypatch, sync_ok=False)
    assert not [s for s in res["sections"] if s.get("source") == "guess"]


def test_guess_no_figure_drafts_when_times_not_trusted(tmp_path, monkeypatch):
    res = _wire_figures(tmp_path, monkeypatch, sync_ok=True, times_trusted=False)
    assert not [s for s in res["sections"] if s.get("source") == "guess"]


# --- tempo-automation hints (informational note, never a box) ---------------


def _wire_tempo_hints(tmp_path, monkeypatch, rows):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "tempo_hints.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_gp5", lambda gp, track: None)
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])
    return g.estimate_hybrid(flac, None, track="Fixture",
                             cache=lab / "work" / "stems", album="A")


def test_guess_notes_tempo_changes_as_text_not_a_box(tmp_path, monkeypatch):
    rows = [{"album": "A", "track": "Fixture", "sec": 12.5,
             "bpm_before": 135.0, "bpm_after": 141.0, "times_trusted": True}]

    res = _wire_tempo_hints(tmp_path, monkeypatch, rows)

    assert any("tempo changes x1" in n and "12.5s 135->141" in n for n in res["notes"])
    assert not [s for s in res["sections"] if s.get("source") == "tempo-automation"]


def test_guess_untrusted_tempo_hint_note_says_so(tmp_path, monkeypatch):
    rows = [{"album": "A", "track": "Fixture", "sec": None,
             "bpm_before": 135.0, "bpm_after": 141.0, "times_trusted": False}]

    res = _wire_tempo_hints(tmp_path, monkeypatch, rows)

    assert any("sync not ok" in n for n in res["notes"] if "tempo changes" in n)


def test_guess_no_tempo_note_when_no_hints(tmp_path, monkeypatch):
    res = _wire_tempo_hints(tmp_path, monkeypatch, [])
    assert not [n for n in res["notes"] if "tempo changes" in n]


# --- tab-notation kick spans (real kick notation beats a spectral guess) ----


def test_tab_kick_spans_filters_pitch_36_and_tags_kick_notation():
    from boo_lab.tabnotes import TabEvent, TabMeasure, TabNotesPack, TabTrack

    # Same known-good shape as test_half_time_spans_detects_a_known_half_time_stretch:
    # 24 dense (0.5s) kicks, then a real half-time stretch (16 kicks at 1.0s).
    times = [i * 0.5 for i in range(24)] + [12.0 + i * 1.0 for i in range(16)]
    tracks = [TabTrack(index=0, name="Drums", category="drums")]
    measures = [TabMeasure(measure=0, start_ms=0.0, start_sec_audio=0.0, duration_ms=40000.0)]
    events = [TabEvent(track=0, category="drums", measure=0, onset_ms=t * 1000.0, pitch=36)
             for t in times]
    # A non-kick drum hit (snare) interleaved -- the pitch filter must drop it.
    events.append(TabEvent(track=0, category="drums", measure=0, onset_ms=100.0, pitch=40))
    pack = TabNotesPack(id="p", title="P", tracks=tracks, events=events, measures=measures)

    spans = g._tab_kick_spans(pack)

    assert len(spans) == 1
    assert spans[0]["source"] == "kick-notation" and spans[0]["role"] == "breakdown"
    assert spans[0]["end"] - spans[0]["start"] >= 5.0


def _wire_kick(tmp_path, monkeypatch, *, sync_ok, pack_found=True):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "sync_ok": sync_ok}) + "\n",
        encoding="utf-8")
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_gp5", lambda gp, track: None)
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [])
    monkeypatch.setattr(g, "_tab_kick_spans", lambda pack: [
        {"role": "breakdown", "start": 5.0, "end": 12.0, "source": "kick-notation"}])

    from boo_lab import tabnotes as tn
    monkeypatch.setattr(tn, "discover_pack",
                        lambda lab_root, album, track: ("fake-path" if pack_found else None))
    monkeypatch.setattr(tn, "load_pack", lambda path: object())
    return lab, flac


def test_guess_prefers_tab_kick_notation_over_audio_when_sync_ok(tmp_path, monkeypatch):
    lab, flac = _wire_kick(tmp_path, monkeypatch, sync_ok=True)
    monkeypatch.setattr(g, "_kick_spans",
                        lambda wav: (_ for _ in ()).throw(
                            AssertionError("audio kick path must not run when tab notation is used")))

    res = g.estimate_hybrid(flac, None, track="Fixture", cache=lab / "work" / "stems", album="A")

    kicks = [s for s in res["sections"] if s.get("source") == "kick-notation"]
    assert kicks and kicks[0]["start"] == 5.0
    assert any("kick notation x1" in n for n in res["notes"])


def test_guess_falls_back_to_audio_kick_when_sync_not_ok(tmp_path, monkeypatch):
    lab, flac = _wire_kick(tmp_path, monkeypatch, sync_ok=False)
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [
        {"role": "breakdown", "start": 1.0, "end": 9.0, "source": "kick"}])

    res = g.estimate_hybrid(flac, None, track="Fixture", cache=lab / "work" / "stems", album="A")

    assert not [s for s in res["sections"] if s.get("source") == "kick-notation"]
    assert [s for s in res["sections"] if s.get("source") == "kick"]


def test_guess_falls_back_to_audio_kick_when_no_pack(tmp_path, monkeypatch):
    lab, flac = _wire_kick(tmp_path, monkeypatch, sync_ok=True, pack_found=False)
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [
        {"role": "breakdown", "start": 1.0, "end": 9.0, "source": "kick"}])

    res = g.estimate_hybrid(flac, None, track="Fixture", cache=lab / "work" / "stems", album="A")

    assert not [s for s in res["sections"] if s.get("source") == "kick-notation"]
    assert [s for s in res["sections"] if s.get("source") == "kick"]


def _wire_breakdown(tmp_path, monkeypatch, album, med=8.0, blob_album=None):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    key = album if blob_album is None else blob_album
    if key:
        (lab / "data" / "adapt.json").write_text(
            json.dumps({key: {"n_pairs": 0,
                              "breakdowns": {"n": 2, "median_span_sec": med}}}) + "\n",
            encoding="utf-8",
        )
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_gp5", lambda gp, track: None)
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [
        {"role": "breakdown", "start": 0.0, "end": 8.0, "source": "halftime"},
        {"role": "breakdown", "start": 20.0, "end": 22.0, "source": "halftime"},
    ])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])
    return g.estimate_hybrid(flac, None, track="Fixture",
                             cache=lab / "work" / "stems", album=album)


def test_breakdown_gate_is_per_album(tmp_path, monkeypatch):
    res_a = _wire_breakdown(tmp_path, monkeypatch, "A")
    res_b = _wire_breakdown(tmp_path, monkeypatch, "B", blob_album="A")

    a = [s for s in res_a["sections"] if s.get("source") == "halftime"]
    b = [s for s in res_b["sections"] if s.get("source") == "halftime"]
    assert len(a) == 1 and [round(s["start"]) for s in a] == [0]  # 8.0 kept, 2.0 dropped
    assert len(b) == 2  # album B has no blob -> unchanged


def test_guess_never_writes_sections_jsonl(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    sec = lab / "data" / "sections.jsonl"
    sec.write_text('{"album":"A","track":"Fixture","role":"riff"}\n', encoding="utf-8")
    before = sec.read_text(encoding="utf-8")

    _wire_figures(tmp_path, monkeypatch, sync_ok=True)

    assert sec.read_text(encoding="utf-8") == before
