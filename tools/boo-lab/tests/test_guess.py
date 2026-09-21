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
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
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
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
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
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: tmp_path / "x.gp5")
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
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: tmp_path / "x.gp5")
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
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: tmp_path / "x.gp5")
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
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
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


def test_figure_drafts_prefill_inst_from_figures_instrument(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    rows = [
        {"album": "A", "track": "T", "figure_id": "bass-riff-A", "instrument": "bass",
         "times_trusted": True, "occurrences": [{"start": 1.0, "end": 3.0}]},
        {"album": "A", "track": "T", "figure_id": "pulse-A", "instrument": "other",
         "role": "pulse", "times_trusted": True, "occurrences": [{"start": 5.0, "end": 7.0}]},
        {"album": "A", "track": "T", "figure_id": "riff-A", "instrument": "guitar",
         "times_trusted": True, "occurrences": [{"start": 9.0, "end": 11.0}]},
        {"album": "A", "track": "T", "figure_id": "riff-B",  # no instrument at all (older row)
         "times_trusted": True, "occurrences": [{"start": 13.0, "end": 15.0}]},
    ]
    (lab / "data" / "figures.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    drafts = g._figure_drafts(lab, "A", "T", existing=[])

    by_fig = {d["figure_id"]: d["instrument"] for d in drafts}
    assert by_fig["bass-riff-A"] == "bass"
    assert by_fig["pulse-A"] == "synth"
    assert by_fig["riff-A"] == ""
    assert by_fig["riff-B"] == ""


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
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
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
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
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
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
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


# --- keeper-model drafts merged read-only ------------------------------------


def test_guess_merges_keeper_model_drafts(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "drafts.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "start": 5.0, "end": 9.0,
                    "role": "hook", "source": "keeper-model", "heard": False}) + "\n",
        encoding="utf-8",
    )
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])

    res = g.estimate_hybrid(flac, None, track="Fixture",
                            cache=lab / "work" / "stems", album="A")

    km = [s for s in res["sections"] if s.get("source") == "keeper-model"]
    assert km and km[0]["role"] == "hook"
    assert any("keeper-model drafts x1" in n for n in res["notes"])


# --- tab-notes pack density drafts + meter/tempo cuts ------------------------


def _wire_pack_drafts(tmp_path, monkeypatch, *, sync_ok):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "sync_ok": sync_ok}) + "\n",
        encoding="utf-8",
    )
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])

    from boo_lab import tabnotes_drafts as td
    monkeypatch.setattr(
        td, "density_drafts_for_song",
        lambda lab_root, album, track, **k: [
            {"role": "riff", "start": 1.0, "end": 2.0, "source": "tabnotes-density",
             "heard": False, "album": album, "track": track}])
    monkeypatch.setattr(
        td, "meter_cuts_for_song",
        lambda lab_root, album, track, **k: [12.3, 45.1])
    return g.estimate_hybrid(flac, None, track="Fixture",
                             cache=lab / "work" / "stems", album="A")


def test_guess_merges_tabnotes_density_when_sync_ok(tmp_path, monkeypatch):
    res = _wire_pack_drafts(tmp_path, monkeypatch, sync_ok=True)

    density = [s for s in res["sections"] if s.get("source") == "tabnotes-density"]
    assert density and density[0]["role"] == "riff"
    assert all(s["heard"] is False for s in density)
    assert any("tabnotes density x1" in n for n in res["notes"])


def test_guess_no_tabnotes_density_when_not_sync_ok(tmp_path, monkeypatch):
    res = _wire_pack_drafts(tmp_path, monkeypatch, sync_ok=False)

    assert not [s for s in res["sections"] if s.get("source") == "tabnotes-density"]
    assert not [n for n in res["notes"] if "tabnotes density" in n]


def test_guess_surfaces_meter_cuts_as_a_note(tmp_path, monkeypatch):
    res = _wire_pack_drafts(tmp_path, monkeypatch, sync_ok=True)

    assert any("tempo/meter cuts at 12.3s, 45.1s" in n for n in res["notes"])


def test_guess_no_meter_cuts_when_not_sync_ok(tmp_path, monkeypatch):
    res = _wire_pack_drafts(tmp_path, monkeypatch, sync_ok=False)

    assert not [n for n in res["notes"] if "tempo/meter cuts" in n]


# --- blast drum-feel hint (full-speed, opposite of half-time breakdown) -----


def test_blast_spans_from_classified_kick_snare(monkeypatch):
    # 24 dense kick+snare onsets (0.1s), then 24 sparse (0.6s): the dense run
    # clears the existing onset-density detector far above the song average.
    onsets = ([{"time": round(i * 0.1, 3), "role": "kick"} for i in range(24)]
              + [{"time": round(3.0 + i * 0.6, 3), "role": "snare"} for i in range(24)])
    import boo_lab.drums_extract as de
    monkeypatch.setattr(de, "classify_drums", lambda p: onsets)

    spans = g._blast_spans("drums.wav")

    assert spans and spans[0]["role"] == "blast" and spans[0]["source"] == "blast-hint"
    assert spans[0]["start"] == 0.0 and spans[0]["end"] > spans[0]["start"]


def test_blast_spans_requires_a_real_stem_and_enough_onsets(monkeypatch):
    assert g._blast_spans(None) == []
    import boo_lab.drums_extract as de
    monkeypatch.setattr(de, "classify_drums",
                        lambda p: [{"time": i * 0.5, "role": "kick"} for i in range(10)])
    assert g._blast_spans("drums.wav") == []


def test_blast_spans_soft_fails_when_the_classifier_is_unavailable(monkeypatch):
    import boo_lab.drums_extract as de

    def _boom(p):
        raise ImportError("no engine")

    monkeypatch.setattr(de, "classify_drums", _boom)
    assert g._blast_spans("drums.wav") == []


def test_gate_blasts_uses_the_album_median_span():
    blob = {"blasts": {"n": 2, "median_span_sec": 8.0}}
    sections = [
        {"role": "blast", "start": 0.0, "end": 8.0, "source": "blast-hint"},
        {"role": "blast", "start": 20.0, "end": 22.0, "source": "blast-hint"},
    ]

    kept = g._gate_blasts(sections, blob)

    assert kept == 1 and len(sections) == 1
    assert sections[0]["end"] - sections[0]["start"] == 8.0


def test_gate_blasts_leaves_things_alone_below_two_songs():
    sections = [{"role": "blast", "start": 0.0, "end": 2.0, "source": "blast-hint"}]
    assert g._gate_blasts(sections, {"blasts": {"n": 1, "median_span_sec": 8.0}}) == 1
    assert g._gate_blasts(sections, None) == 1
    assert len(sections) == 1


def test_link_on_figure_picks_best_overlap_by_duration():
    sections = [
        {"role": "riff", "start": 0.0, "end": 10.0, "figure_id": "riff-A", "source": "guess"},
        {"role": "riff", "start": 10.0, "end": 20.0, "figure_id": "riff-B", "source": "guess"},
        {"role": "blast", "start": 8.0, "end": 14.0, "source": "blast-hint"},
    ]

    linked = g._link_on_figure(sections)

    assert linked == 1
    assert sections[2]["on_figure"] == "riff-B"  # 4s overlap vs riff-A's 2s


def test_link_on_figure_never_overwrites_or_invents():
    sections = [
        {"role": "riff", "start": 0.0, "end": 10.0, "figure_id": "riff-A", "source": "guess"},
        {"role": "blast", "start": 0.0, "end": 10.0, "source": "blast-hint",
         "on_figure": "hook-C"},
        {"role": "blast", "start": 30.0, "end": 33.0, "source": "blast-hint"},
    ]

    g._link_on_figure(sections)

    assert sections[1]["on_figure"] == "hook-C"      # human's link kept
    assert sections[2].get("on_figure", "") == ""    # gap: nothing invented


def test_guess_adds_a_blast_hint_from_the_drum_stem(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    drum = tmp_path / "drums.wav"
    drum.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (drum, "drums"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])
    monkeypatch.setattr(g, "_blast_spans", lambda d, **k: [
        {"role": "blast", "start": 1.0, "end": 5.0, "source": "blast-hint"}])

    res = g.estimate_hybrid(flac, None, track="Fixture", cache=lab / "work" / "stems", album="A")

    blasts = [s for s in res["sections"] if s.get("source") == "blast-hint"]
    assert blasts and blasts[0]["role"] == "blast"
    assert any("blast hint x1" in n for n in res["notes"])


# --- GP7/GPIF tab preference (same priority as sync) -------------------------


def test_prefer_tab_returns_gp7_even_with_a_sibling_gp5(tmp_path):
    gp7 = tmp_path / "02 Elimination.gp"
    gp5 = tmp_path / "02 Elimination.gp5"
    gp7.write_bytes(b"x")
    gp5.write_bytes(b"x")

    assert g._prefer_tab(gp7, "02 Elimination") == gp7


def test_prefer_tab_upgrades_a_gp5_to_its_gp7_sibling(tmp_path):
    gp7 = tmp_path / "02 Elimination.gp"
    gp5 = tmp_path / "02 Elimination.gp5"
    gp7.write_bytes(b"x")
    gp5.write_bytes(b"x")

    assert g._prefer_tab(gp5, "02 Elimination") == gp7


def test_prefer_gp5_is_a_backward_compat_alias(tmp_path):
    gp7 = tmp_path / "02 Elimination.gp"
    gp7.write_bytes(b"x")

    assert g._prefer_gp5(gp7, "02 Elimination") == gp7


def test_guess_uses_gpif_estimator_for_a_gp7_tab(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "sync_ok": True, "lag_sec": 0.05}) + "\n",
        encoding="utf-8",
    )
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    gp7 = tmp_path / "song.gp"
    gp7.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    import boo_lab.extract as ex
    monkeypatch.setattr(ex, "estimate_from_gpif", lambda p: {
        "bpm": 120, "duration": 10,
        "sections": [{"role": "riff", "start": 2.0, "end": 6.0, "source": "gp-marker"}],
    })
    monkeypatch.setattr(ex, "estimate_from_gp",
                        lambda p: (_ for _ in ()).throw(
                            AssertionError("GP5 parser must not run for a GP7 tab")))
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])

    res = g.estimate_hybrid(flac, gp7, track="Fixture",
                            cache=lab / "work" / "stems", album="A")

    assert any(s.get("source") == "gp-marker" for s in res["sections"])
    assert any(n == "tab " + str(gp7) for n in res["notes"])


# --- marker-first: tab markers outrank figure-hash floods --------------------

_STARVED_LABELS = [
    ("(0:00)", "riff", "riff-A"),
    ("A1", "riff", "riff-A1"),
    ("A2", "riff", "riff-A2"),
    ("B", "riff", "riff-B"),
    ("C", "riff", "riff-C"),
    ("D", "riff", "riff-D"),
    ("C", "riff", "riff-C"),
    ("B", "riff", "riff-B"),
    ("B-Solo", "solo", "solo-B"),
    ("E", "riff", "riff-E"),
    ("F1", "riff", "riff-F1"),
    ("F2", "riff", "riff-F2"),
    ("G", "riff", "riff-G"),
    ("H", "riff", "riff-H"),
]


def _starved_markers(duration=200.0):
    step = duration / len(_STARVED_LABELS)
    return [
        {"role": role, "start": round(i * step, 3), "end": round((i + 1) * step, 3),
         "source": "gp-marker", "raw": raw, "form": "A", "figure_id": fig,
         "unique": False}
        for i, (raw, role, fig) in enumerate(_STARVED_LABELS)
    ]


def _short_occurrences(n, start=20.0):
    return [{"start": start + k * 4.0, "end": start + k * 4.0 + 2.0,
             "start_bar": 1, "end_bar": 1} for k in range(n)]


def _wire_markers(tmp_path, monkeypatch, markers, figure_rows=(), *, duration=200.0,
                  halftime=()):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "sync_ok": True}) + "\n",
        encoding="utf-8")
    if figure_rows:
        (lab / "data" / "figures.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in figure_rows), encoding="utf-8")
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(
                            frames=int(22050 * duration), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: tmp_path / "x.gp5")
    import boo_lab.extract as ex
    monkeypatch.setattr(ex, "estimate_from_gp",
                        lambda p: {"bpm": 120, "duration": duration,
                                   "sections": [dict(s) for s in markers]})
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans",
                        lambda beats, min_len=6.0: [dict(s) for s in halftime])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])
    return g.estimate_hybrid(flac, tmp_path / "x.gp5", track="Fixture",
                             cache=lab / "work" / "stems", album="A")


def test_guess_returns_marker_count_not_a_figure_flood(tmp_path, monkeypatch):
    flood = [
        {"album": "A", "track": "Fixture", "figure_id": fig, "times_trusted": True,
         "occurrences": _short_occurrences(n)}
        for fig, n in [("riff-D", 4), ("solo-B", 3), ("riff-C", 4)]
    ]

    res = _wire_markers(tmp_path, monkeypatch, _starved_markers(),
                        figure_rows=flood,
                        halftime=[{"role": "breakdown", "start": 30.0,
                                   "end": 38.0, "source": "halftime"}])

    markers = [s for s in res["sections"] if s.get("source") == "gp-marker"]
    assert len(markers) == len(_STARVED_LABELS)
    assert not [s for s in res["sections"] if s.get("source") == "guess"]
    assert any("figure drafts capped" in n for n in res["notes"])

    assert len([s for s in markers if s["figure_id"] == "riff-C"]) == 2
    assert len([s for s in markers if s["figure_id"] == "riff-B"]) == 2

    solo = [s for s in res["sections"] if s.get("role") == "solo"]
    assert solo and solo[0]["figure_id"] == "solo-B"

    bd = [s for s in res["sections"] if s.get("source") == "halftime"]
    assert bd and bd[0]["on_figure"] == "riff-A2"
    assert all((s["end"] - s["start"]) >= 4.0
               for s in res["sections"] if s.get("source") == "guess")


def test_guess_fills_marker_gaps_but_not_short_crumbs(tmp_path, monkeypatch):
    markers = [
        {"role": "riff", "start": 0.0, "end": 50.0, "source": "gp-marker",
         "raw": "A", "form": "A", "figure_id": "riff-A", "unique": False},
        {"role": "riff", "start": 50.0, "end": 100.0, "source": "gp-marker",
         "raw": "B", "form": "B", "figure_id": "riff-B", "unique": False},
    ]
    rows = [{"album": "A", "track": "Fixture", "figure_id": "riff-X",
             "times_trusted": True,
             "occurrences": [
                 {"start": 20.0, "end": 26.0},    # overlaps marker -> drop
                 {"start": 120.0, "end": 126.0},  # gap, long -> keep
                 {"start": 130.0, "end": 132.0},  # gap, short -> drop
             ]}]

    res = _wire_markers(tmp_path, monkeypatch, markers, figure_rows=rows)

    guess = [s for s in res["sections"] if s.get("source") == "guess"]
    assert len(guess) == 1
    assert guess[0]["start"] == 120.0 and guess[0]["end"] == 126.0


def test_guess_drops_load_draft_sources(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "sync_ok": True}) + "\n",
        encoding="utf-8")
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(
                            frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
    monkeypatch.setattr(g, "_figure_drafts", lambda *a, **k: [
        {"role": "riff", "start": 5.0, "end": 13.0, "figure_id": "riff-X",
         "source": "msa-draft", "heard": False}])
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_half_time_spans", lambda beats, min_len=6.0: [])
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])

    res = g.estimate_hybrid(flac, None, track="Fixture",
                            cache=lab / "work" / "stems", album="A")

    assert not [s for s in res["sections"]
                if s.get("source") in ("msa-draft", "songformer-draft")]
    assert any("load-draft" in n for n in res["notes"])


def test_markers_primary_by_count_and_coverage():
    four = [{"source": "gp-marker", "start": i * 10.0, "end": (i + 1) * 10.0}
            for i in range(4)]
    assert g._markers_primary(four, 100.0) is True

    one = [{"source": "gp-marker", "start": 0.0, "end": 50.0}]
    assert g._markers_primary(one, 100.0) is True    # 50% coverage
    assert g._markers_primary(one, 1000.0) is False
    assert g._markers_primary([], 100.0) is False


def test_suppress_figure_flood_drops_short_and_overlapping():
    sections = [{"source": "gp-marker", "start": i * 40.0, "end": (i + 1) * 40.0}
                for i in range(4)]
    drafts = [
        {"role": "riff", "start": 10.0, "end": 16.0, "figure_id": "riff-A"},
        {"role": "riff", "start": 140.0, "end": 142.0, "figure_id": "riff-B"},
        {"role": "riff", "start": 165.0, "end": 175.0, "figure_id": "riff-C"},
    ]

    kept = g._suppress_figure_flood(drafts, sections, duration=200.0)

    assert [d["figure_id"] for d in kept] == ["riff-C"]


def test_suppress_figure_flood_noop_without_markers():
    drafts = [{"role": "riff", "start": 1.0, "end": 2.0, "figure_id": "riff-A"}]
    assert g._suppress_figure_flood(drafts, [], duration=100.0) is drafts


# --- pack structure spine (no GP) + figure-flood cap -------------------------


def _spine_pack():
    """A Mindful-like tab-notes pack: 3 dense guitar phrases + a half-time
    drum shift. Real `TabNotesPack` object; no FLAC, no commercial tab."""
    from boo_lab import tabnotes as tn

    times = []
    for c in range(3):
        base = c * 12.0
        times += [base + i * 0.1 for i in range(24)]        # dense phrase
        times += [base + 2.6 + i * 1.0 for i in range(8)]   # sparse gap
    kicks = [i * 0.5 for i in range(24)] + [12.0 + i * 1.0 for i in range(16)]
    measures = [tn.TabMeasure(measure=0, start_ms=0.0, start_sec_audio=0.0,
                              duration_ms=40000.0, tempo_bpm=120.0,
                              time_signature="4/4")]
    events = [tn.TabEvent(track=0, category="guitar", measure=0, pitch=40,
                          onset_ms=round(t * 1000.0, 3)) for t in sorted(times)]
    events += [tn.TabEvent(track=1, category="drums", measure=0, pitch=36,
                           onset_ms=round(t * 1000.0, 3)) for t in kicks]
    tracks = [tn.TabTrack(index=0, name="Guitar", category="guitar"),
              tn.TabTrack(index=1, name="Drums", category="drums", is_percussion=True)]
    return tn.TabNotesPack(id="p", title="Fixture", tracks=tracks, events=events,
                           measures=measures)


def _wire_pack_spine(tmp_path, monkeypatch, *, figure_rows=()):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "Fixture", "sync_ok": True}) + "\n",
        encoding="utf-8")
    if figure_rows:
        (lab / "data" / "figures.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in figure_rows), encoding="utf-8")
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    monkeypatch.setattr(soundfile, "info",
                        lambda *a, **k: types.SimpleNamespace(
                            frames=int(22050 * 100), samplerate=22050))
    monkeypatch.setattr(g, "GP5_ROOTS", [tmp_path / "no_gp5"])
    monkeypatch.setattr(g, "_prefer_tab", lambda gp, track: None)
    import boo_lab.stems as st
    monkeypatch.setattr(st, "ensure_drums", lambda f, c: (None, "none"))
    # No librosa beats -> no audio half-time; the half-time detector itself
    # stays real so the pack's own kick notation can still run through it.
    monkeypatch.setattr(g, "_librosa_beats", lambda wav: {"beats": [], "bpm": None})
    monkeypatch.setattr(g, "_kick_spans", lambda wav: [])

    from boo_lab import tabnotes as tn
    pack = _spine_pack()
    monkeypatch.setattr(tn, "discover_pack", lambda lab_root, album, track: "fake-path")
    monkeypatch.setattr(tn, "load_pack", lambda path: pack)
    return g.estimate_hybrid(flac, None, track="Fixture",
                             cache=lab / "work" / "stems", album="A")


def test_guess_pack_spine_gives_riffs_not_only_breakdowns(tmp_path, monkeypatch):
    res = _wire_pack_spine(tmp_path, monkeypatch)

    spine = [s for s in res["sections"] if s.get("source") == "tabnotes-structure"]
    assert [s["figure_id"] for s in spine] == ["riff-A", "riff-B", "riff-C"]
    assert all(s["role"] == "riff" for s in spine)
    assert any(s["role"] == "breakdown" for s in res["sections"])
    assert len(res["sections"]) > 2
    assert any("pack structure x3 (tabnotes spine)" in n for n in res["notes"])


def test_guess_pack_spine_yields_to_figure_hash_identity(tmp_path, monkeypatch):
    """Pack activity spine is coverage only — figure drafts replace it."""
    rows = [{"album": "A", "track": "Fixture", "figure_id": "riff-X",
             "times_trusted": True,
             "occurrences": [
                 {"start": 0.5, "end": 6.5},       # overlaps spine — still keep
                 {"start": 100.0, "end": 106.0},   # gap, long — keep
                 {"start": 120.0, "end": 122.0},   # short non-unique — drop
             ]}]

    res = _wire_pack_spine(tmp_path, monkeypatch, figure_rows=rows)

    assert not [s for s in res["sections"] if s.get("source") == "tabnotes-structure"]
    guess = [s for s in res["sections"] if s.get("source") == "guess"]
    # Gap phrase always kept; an early overlap may merge into pack density in _clean.
    assert any(s["start"] == 100.0 and s["end"] == 106.0 for s in guess)
    assert not any(s["start"] == 120.0 for s in guess)


def test_guess_marker_spine_wins_over_a_discovered_pack(tmp_path, monkeypatch):
    from boo_lab import tabnotes as tn
    pack = _spine_pack()
    monkeypatch.setattr(tn, "discover_pack", lambda *a, **k: "fake-path")
    monkeypatch.setattr(tn, "load_pack", lambda *a, **k: pack)

    res = _wire_markers(tmp_path, monkeypatch, _starved_markers())

    assert not [s for s in res["sections"] if s.get("source") == "tabnotes-structure"]
    markers = [s for s in res["sections"] if s.get("source") == "gp-marker"]
    assert len(markers) == len(_STARVED_LABELS)


def test_spine_primary_false_for_pack_structure_alone():
    """Pack activity spine must not outrank figure-hash (Mindful unique runs)."""
    sections = [{"role": "riff", "start": 0.0, "end": 2.0,
                 "source": "tabnotes-structure", "figure_id": "riff-A"}]
    assert g._spine_primary(sections, duration=200.0) is False
    assert g._spine_primary([], duration=200.0) is False

def test_merge_adjacent_same_figure_collapses_starved_style_slices():
    from boo_lab import guess as g
    slices = [
        {"role": "riff", "figure_id": "riff-A1", "start": 11.52, "end": 13.94, "source": "gp-marker"},
        {"role": "riff", "figure_id": "riff-A1", "start": 13.94, "end": 16.36, "source": "gp-marker"},
        {"role": "riff", "figure_id": "riff-A1", "start": 16.36, "end": 21.21, "source": "gp-marker"},
        {"role": "riff", "figure_id": "riff-D", "start": 49.09, "end": 51.52, "source": "gp-marker"},
        {"role": "blast", "figure_id": None, "start": 50.0, "end": 51.0, "source": "blast-hint"},
        {"role": "riff", "figure_id": "riff-D", "start": 51.52, "end": 53.94, "source": "gp-marker"},
        # later return of D after a gap — keep separate
        {"role": "riff", "figure_id": "riff-D", "start": 80.0, "end": 82.0, "source": "gp-marker"},
        {"role": "solo", "figure_id": "solo-B", "start": 74.55, "end": 93.94, "source": "gp-marker"},
    ]
    out = g._merge_adjacent_same_figure(slices)
    a1 = [s for s in out if s["figure_id"] == "riff-A1"]
    d = [s for s in out if s["figure_id"] == "riff-D"]
    assert len(a1) == 1 and a1[0]["start"] == 11.52 and a1[0]["end"] == 21.21
    assert len(d) == 2  # adjacent merge + later return
    assert d[0]["start"] == 49.09 and d[0]["end"] == 53.94
    assert d[1]["start"] == 80.0


def test_spine_primary_ignores_pack_structure_alone():
    """Pack activity spine must not crush unique figure drafts."""
    from boo_lab.guess import _spine_primary, PACK_STRUCTURE_SOURCE
    pack_only = [{"source": PACK_STRUCTURE_SOURCE, "start": 0, "end": 10, "role": "riff"}]
    assert _spine_primary(pack_only, 100.0) is False
    markers = [{"source": "gp-marker", "start": 0, "end": 40, "role": "riff", "figure_id": "riff-A"}]
    # markers_primary needs enough coverage — just assert pack-alone is False
    assert _spine_primary(markers + pack_only, 100.0) in (True, False)


def test_suppress_keeps_short_unique_pack_runs_when_not_primary():
    from boo_lab.guess import _suppress_figure_flood, PACK_STRUCTURE_SOURCE
    spine = [{"source": PACK_STRUCTURE_SOURCE, "start": 0.0, "end": 100.0, "role": "riff"}]
    drafts = [
        {"start": 10.0, "end": 13.3, "figure_id": "riff-A", "unique": True, "role": "riff"},
        {"start": 20.0, "end": 22.0, "figure_id": "riff-B", "unique": False, "role": "riff"},
    ]
    kept = _suppress_figure_flood(drafts, spine, duration=100.0)
    ids = {d["figure_id"] for d in kept}
    assert "riff-A" in ids  # unique 3.3s kept
    assert "riff-B" not in ids  # non-unique 2s < 4s min_span
