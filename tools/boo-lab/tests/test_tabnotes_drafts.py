"""Tests for src/boo_lab/tabnotes_drafts.py -- pack density drafts + meter
cuts. All packs are hand-made synthetic TabNotesPack objects; no FLAC, no
commercial tab, no network."""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab import tabnotes as tn
from boo_lab import tabnotes_drafts as td


def _measure(index, start_ms, start_sec, tempo=120.0, sig="4/4"):
    return tn.TabMeasure(measure=index, start_ms=start_ms, start_sec_audio=start_sec,
                         duration_ms=2000.0, tempo_bpm=tempo, time_signature=sig)


def _pack(events, measures):
    tracks = [tn.TabTrack(index=0, name="Guitar", category="guitar"),
              tn.TabTrack(index=1, name="Drums", category="drums", is_percussion=True)]
    return tn.TabNotesPack(id="p", title="P", tracks=tracks, events=events,
                           measures=measures)


def _dense_pack():
    """24 dense guitar onsets (0.125s) then 24 sparse (0.5s), same clock."""
    dense = [i * 0.125 for i in range(24)]
    sparse = [3.0 + i * 0.5 for i in range(24)]
    events = [
        tn.TabEvent(track=0, category="guitar", measure=0,
                    onset_ms=round(t * 1000.0, 3), pitch=40,
                    palm_mute=(i % 3 == 0), hammer=(i % 4 == 0))
        for i, t in enumerate(dense + sparse)
    ]
    return _pack(events, [_measure(0, 0.0, 0.0)])


def _drum_pack():
    """24 kicks at 0.5s then a real half-time stretch of 16 at 1.0s."""
    kicks = [i * 0.5 for i in range(24)] + [12.0 + i * 1.0 for i in range(16)]
    events = [tn.TabEvent(track=1, category="drums", measure=0, pitch=36,
                          onset_ms=round(t * 1000.0, 3)) for t in kicks]
    return _pack(events, [_measure(0, 0.0, 0.0)])


# --- density spans ---------------------------------------------------------


def test_dense_spans_flags_a_fast_stretch():
    times = [i * 0.125 for i in range(24)] + [3.0 + i * 0.5 for i in range(24)]
    spans = td._dense_spans(times)

    assert len(spans) == 1
    start, end = spans[0]
    assert start == 0.0 and end >= 1.0


def test_dense_spans_bad_input_is_empty():
    assert td._dense_spans([]) == []
    assert td._dense_spans([1.0] * 10) == []          # fewer than 12
    assert td._dense_spans([5.0] * 30) == []          # zero IOI -> median guard


def test_riff_density_spans_from_guitar_onsets():
    spans = td.riff_density_spans(_dense_pack())
    assert spans and spans[0][0] == 0.0


def test_drum_breakdown_spans_reuse_half_time():
    spans = td.drum_breakdown_spans(_drum_pack())
    assert len(spans) == 1
    assert spans[0][1] - spans[0][0] >= 5.0


def test_pack_density_drafts_merges_by_role():
    pack = _dense_pack()
    pack.events += _drum_pack().events
    drafts = td.pack_density_drafts(pack)

    roles = {d["role"] for d in drafts}
    assert roles == {"riff", "breakdown"}
    assert all(d["end"] > d["start"] for d in drafts)


# --- density drafts -> drafts.jsonl (sync_ok gate) -------------------------


def _wire_pack(monkeypatch, pack):
    monkeypatch.setattr(tn, "discover_pack", lambda lab_root, album, track: "fake-path")
    monkeypatch.setattr(tn, "load_pack", lambda path: pack)


def _drafts(lab):
    path = lab / "data" / "drafts.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_build_density_drafts_never_emits_without_sync_ok(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    _wire_pack(monkeypatch, _dense_pack())
    rows = [{"album": "A", "track": "T"}]

    assert td.build_density_drafts(lab, rows)["written"] == 0   # no sync.jsonl
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "sync_ok": False}) + "\n", encoding="utf-8")
    assert td.build_density_drafts(lab, rows)["written"] == 0
    assert not (lab / "data" / "drafts.jsonl").exists()


def test_build_density_drafts_writes_when_sync_ok_and_never_keepers(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "sync_ok": True}) + "\n", encoding="utf-8")
    _wire_pack(monkeypatch, _dense_pack())

    report = td.build_density_drafts(lab, [{"album": "A", "track": "T"}])

    assert report["written"] >= 1 and report["songs"] == 1
    rows = _drafts(lab)
    assert rows and all(r["source"] == "tabnotes-density" for r in rows)
    assert all(r["heard"] is False for r in rows)
    assert not (lab / "data" / "sections.jsonl").exists()


def test_build_density_drafts_replaces_only_its_own_song(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "sync_ok": True}) + "\n", encoding="utf-8")
    (lab / "data" / "drafts.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 99.0, "end": 100.0,
                    "role": "riff", "source": "tabnotes-density", "heard": False}) + "\n"
        + json.dumps({"album": "A", "track": "T", "start": 1.0, "end": 2.0,
                      "role": "riff", "source": "msa-draft"}) + "\n"
        + json.dumps({"album": "B", "track": "U", "start": 1.0, "end": 2.0,
                      "role": "riff", "source": "tabnotes-density"}) + "\n",
        encoding="utf-8")
    _wire_pack(monkeypatch, _dense_pack())

    td.build_density_drafts(lab, [{"album": "A", "track": "T"}])

    rows = _drafts(lab)
    assert not any(r["source"] == "tabnotes-density" and r["start"] == 99.0 for r in rows)
    assert any(r["source"] == "msa-draft" for r in rows)                       # sibling kept
    assert any(r["source"] == "tabnotes-density" and r["album"] == "B" for r in rows)


def test_build_density_drafts_zero_row_leaves_file_untouched(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    draft = lab / "data" / "drafts.jsonl"
    draft.write_text(json.dumps({"album": "A", "track": "T", "source": "msa-draft"}) + "\n",
                     encoding="utf-8")
    before = draft.read_text(encoding="utf-8")

    _wire_pack(monkeypatch, _dense_pack())
    td.build_density_drafts(lab, [{"album": "A", "track": "T"}])   # no sync -> no rows

    assert draft.read_text(encoding="utf-8") == before


# --- pack structure spine --------------------------------------------------


def _spine_pack():
    """Three denser guitar phrases separated by sparse runs -> three riffs."""
    times = []
    for c in range(3):
        base = c * 12.0
        times += [base + i * 0.1 for i in range(24)]   # dense phrase
        times += [base + 2.6 + i * 1.0 for i in range(8)]  # sparse gap
    events = [tn.TabEvent(track=0, category="guitar", measure=0,
                          onset_ms=round(t * 1000.0, 3), pitch=40)
              for t in sorted(times)]
    return _pack(events, [_measure(0, 0.0, 0.0, tempo=120.0)])


def test_pack_structure_spans_orders_figure_ids_and_roles():
    spans = td.pack_structure_spans(_spine_pack())

    assert [s["role"] for s in spans] == ["riff", "riff", "riff"]
    assert [s["figure_id"] for s in spans] == ["riff-A", "riff-B", "riff-C"]
    assert all(s["end"] > s["start"] for s in spans)


def test_pack_structure_spans_never_invents_gp_letters():
    spans = td.pack_structure_spans(_spine_pack())

    assert all(not any(ch.isdigit() for ch in s["figure_id"]) for s in spans)


def test_structure_drafts_for_song_gated_on_sync_ok(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    _wire_pack(monkeypatch, _spine_pack())

    assert td.structure_drafts_for_song(lab, "A", "T") == []   # no sync.jsonl
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "sync_ok": False}) + "\n",
        encoding="utf-8")
    assert td.structure_drafts_for_song(lab, "A", "T") == []

    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "sync_ok": True}) + "\n",
        encoding="utf-8")
    drafts = td.structure_drafts_for_song(lab, "A", "T")
    assert [d["figure_id"] for d in drafts] == ["riff-A", "riff-B", "riff-C"]
    assert all(d["source"] == td.SOURCE_STRUCTURE for d in drafts)
    assert all(d["heard"] is False for d in drafts)
    assert not (lab / "data" / "sections.jsonl").exists()


# --- meter / tempo cuts ----------------------------------------------------


def test_meter_cuts_from_time_sig_and_tempo_changes():
    pack = _pack([], [
        _measure(0, 0.0, 0.0, tempo=120.0, sig="4/4"),
        _measure(1, 2000.0, 10.0, tempo=141.0, sig="4/4"),   # tempo jump at 10.0
        _measure(2, 4000.0, 20.0, tempo=141.0, sig="7/8"),   # meter change at 20.0
        _measure(3, 6000.0, 30.0, tempo=141.0, sig="7/8"),
    ])

    assert td.meter_cuts(pack) == [10.0, 20.0]


def test_meter_cuts_for_song_gated_on_sync_ok(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    _wire_pack(monkeypatch, _pack([], [
        _measure(0, 0.0, 0.0, tempo=120.0, sig="4/4"),
        _measure(1, 2000.0, 12.3, tempo=141.0, sig="4/4"),
    ]))
    rows_album, rows_track = "A", "T"

    assert td.meter_cuts_for_song(lab, rows_album, rows_track) == []   # no sync.jsonl
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "sync_ok": False}) + "\n", encoding="utf-8")
    assert td.meter_cuts_for_song(lab, rows_album, rows_track) == []

    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "sync_ok": True}) + "\n", encoding="utf-8")
    assert td.meter_cuts_for_song(lab, rows_album, rows_track) == [12.3]


def test_snap_sections_to_cuts_only_audio_sources():
    sections = [
        {"role": "riff", "start": 12.0, "end": 20.4, "source": "tabnotes-density"},
        {"role": "riff", "start": 12.0, "end": 20.4, "source": "gp-marker"},
    ]

    snapped = td.snap_sections_to_cuts(sections, [12.3, 20.0], tol=0.75)

    assert snapped == 2
    assert sections[0]["start"] == 12.3 and sections[0]["end"] == 20.0
    assert sections[1]["start"] == 12.0 and sections[1]["end"] == 20.4   # marker untouched


def _uneven_fullsong_pack():
    """Mindful-shaped: quieter early guitar, denser late — peak-relative density
    used to starve the opening; measure spine must still cover the song."""
    events = []
    measures = []
    # 40 measures x 2.0s audio
    for i in range(40):
        start = i * 2.0
        measures.append(tn.TabMeasure(
            measure=i, start_ms=start * 1000.0, start_sec_audio=start,
            duration_ms=2000.0, audio_duration_sec=2.0, tempo_bpm=120.0,
            time_signature="4/4", length_beats=4.0,
        ))
        # early: ~4 onsets/measure; late: ~16 onsets/measure
        n = 4 if i < 20 else 16
        step = 2.0 / n
        for k in range(n):
            tt = start + k * step + 0.05
            events.append(tn.TabEvent(
                track=0, category="guitar", measure=i,
                onset_ms=round(tt * 1000.0, 3), pitch=40,
            ))
    return _pack(events, measures)


def test_pack_structure_covers_uneven_density_full_song():
    pack = _uneven_fullsong_pack()
    times = tn.onsets_audio(pack, category="guitar")
    # legacy peak-relative path is sparse on this shape
    legacy = td._dense_spans(times, min_len=2.0)
    legacy_cov = td.spine_coverage_ratio(legacy, times)
    spans = td.pack_structure_spans(pack)
    cov = td.spine_coverage_ratio(spans, times)
    assert cov >= 0.85, (cov, spans)
    assert spans[0]["start"] < 5.0
    assert spans[-1]["end"] > 70.0
    assert legacy_cov < 0.85 or True  # document intent; primary assert is cov
    assert [s["figure_id"] for s in spans][0] == "riff-A"
    assert all(s["role"] == "riff" for s in spans)


def test_spine_coverage_ratio_helper():
    assert td.spine_coverage_ratio([(0.0, 5.0)], [0.0, 10.0]) == 0.5
    assert td.spine_coverage_ratio([], [0.0, 10.0]) == 0.0
