"""Tests for src/boo_lab/extract.py -- synthetic in-memory GP5 fixtures only
(mirrors engine/tests/test_riff_bank.py's own documented discipline; never a
real copyrighted GP file)."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

guitarpro = pytest.importorskip("guitarpro")

from gp_fixtures import make_song, make_track  # noqa: E402

from boo_lab import extract as ex  # noqa: E402


def _write(song, tmp_path, name="fixture.gp5"):
    path = tmp_path / name
    guitarpro.write(song, str(path))
    return path


# --- _measure_start_times ----------------------------------------------------


def test_measure_start_times_walks_default_4_4_at_120_bpm():
    song = make_song(3)
    track = make_track(song, 1, {0: [40]})
    assert ex._measure_start_times(track) == [0.0, 2.0, 4.0]


def test_measure_start_times_empty_track_is_empty():
    song = make_song(0)
    track = make_track(song, 1, {})
    assert ex._measure_start_times(track) == []


def test_bars_for_times_missing_file_is_null(tmp_path):
    assert ex.bars_for_times(tmp_path / "nope.gp5", 0.0, 2.0) == (None, None)


def test_bars_for_times_maps_seconds_to_measures(tmp_path):
    song = make_song(3, title="Bar Song")
    track = make_track(song, 1, {0: [40], 1: [40], 2: [40]}, instrument=30)
    song.tracks = [track]
    path = _write(song, tmp_path)
    assert ex.bars_for_times(path, 0.0, 2.0) == (1, 2)
    assert ex.bars_for_times(path, 0.0, 4.0) == (1, 3)
    assert ex.bars_for_times(path, 100.0, 200.0) == (3, 3)


# --- infer_role --------------------------------------------------------------


@pytest.mark.parametrize(
    "marker,expected",
    [
        ("Intro", "intro"),
        ("Verse 2", "riff"),
        ("Riff", "riff"),
        ("Hook", "hook"),
        ("Chorus", "hook"),
        ("Breakdown", "breakdown"),
        # ROLE_WORDS is checked in dict order and "pre" precedes "hook"/
        # "chorus", so a real "Pre-Chorus" marker resolves to "build" here.
        ("Pre-Chorus", "build"),
        ("Build", "build"),
        ("Lead", "solo"),
        ("C1 - Solo", "solo"),
        ("Bridge", "chill"),
        ("Synth", "pulse"),
        (None, None),
        ("", None),
    ],
)
def test_infer_role_maps_markers(marker, expected):
    assert ex.infer_role(marker) == expected


# --- _human_role_at ----------------------------------------------------------


def test_human_role_at_returns_covering_role_or_none():
    sections = [(0.0, 2.0, "intro"), (3.0, 5.0, "breakdown")]
    assert ex._human_role_at(sections, 1.0) == "intro"
    assert ex._human_role_at(sections, 2.0) is None  # end is exclusive
    assert ex._human_role_at(sections, 4.0) == "breakdown"
    assert ex._human_role_at(sections, 2.5) is None


# --- load_human_sections -----------------------------------------------------


def test_load_human_sections_parses_and_translates_roles(tmp_path):
    (tmp_path / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 1.5, "role": "intro", "source": "human", "heard": True}) + "\n"
        + json.dumps({"album": "A", "track": "T", "start": 1.5, "end": 3.0, "role": "riff", "source": "human", "heard": True}) + "\n"
        + json.dumps({"album": "A", "track": "T", "start": 3.0, "end": 4.0, "role": "pulse", "source": "human", "heard": True}) + "\n",
        encoding="utf-8",
    )
    out = ex.load_human_sections(tmp_path)
    assert out == {("A", "T"): [(0.0, 1.5, "intro"), (1.5, 3.0, "verse")]}


def test_load_human_sections_keeper_law_drops_unheard_and_drafts(tmp_path):
    (tmp_path / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 1.0, "role": "intro", "source": "human", "heard": True}) + "\n"
        + json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 1.0, "role": "riff", "source": "human", "heard": False}) + "\n"
        + json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 1.0, "role": "riff", "source": "guess", "heard": True}) + "\n"
        + json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 1.0, "role": "riff", "source": "msa-draft", "heard": True}) + "\n",
        encoding="utf-8",
    )
    out = ex.load_human_sections(tmp_path)
    assert out == {("A", "T"): [(0.0, 1.0, "intro")]}


def test_load_human_sections_missing_file_is_empty(tmp_path):
    assert ex.load_human_sections(tmp_path) == {}


def test_load_human_sections_skips_malformed_and_incomplete_lines(tmp_path):
    (tmp_path / "sections.jsonl").write_text(
        "not json\n"
        "\n"
        + json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 1.0, "role": "intro", "source": "human", "heard": True}) + "\n"
        + json.dumps({"album": "A", "track": "T", "role": "build", "source": "human", "heard": True}) + "\n"
        + "{broken\n",
        encoding="utf-8",
    )
    assert ex.load_human_sections(tmp_path) == {("A", "T"): [(0.0, 1.0, "intro")]}


def test_playback_duration_expands_repeats():
    from types import SimpleNamespace

    def meas(open_=False, close=-1):
        ts = SimpleNamespace(numerator=4, denominator=SimpleNamespace(value=4))
        header = SimpleNamespace(timeSignature=ts, tempo=None,
                                 isRepeatOpen=open_, repeatClose=close)
        return SimpleNamespace(header=header, timeSignature=ts)

    # measure 1 opens, measure 2 closes once -> order [0,1,2,1,2,3]
    track = SimpleNamespace(measures=[meas(), meas(open_=True), meas(close=1), meas()])
    assert ex._playback_duration(track, 120.0) == 12.0  # 6 measures * 4 beats * 0.5s

    plain = SimpleNamespace(measures=[meas(), meas(), meas(), meas()])
    assert ex._playback_duration(plain, 120.0) == 8.0  # once-through, no repeats


def test_section_letter_parses_structural_markers():
    assert ex._section_letter("A (0:00)") == ("A", "A")
    assert ex._section_letter("C1 - Solo") == ("C", "C1")
    assert ex._section_letter("B - Solo") == ("B", "B")
    assert ex._section_letter("Pre-Chorus") == (None, None)  # semantic, not a letter
    assert ex._section_letter("") == (None, None)


# --- gp_track_names / bad input ---------------------------------------------


def test_gp_track_names_bad_input_returns_empty(tmp_path):
    bad = tmp_path / "bad.gp5"
    bad.write_bytes(b"not a guitar pro file")
    assert ex.gp_track_names(bad) == []


def test_gp_track_names_missing_file_returns_empty(tmp_path):
    assert ex.gp_track_names(tmp_path / "nope.gp5") == []


# --- extract_riffs -----------------------------------------------------------


def test_extract_riffs_without_human_sections_returns_real_fragments(tmp_path):
    song = make_song(2, markers={0: "Verse"}, title="Fixture Song")
    track = make_track(song, 1, {0: [40, None, 44], 1: [47, 40]}, instrument=30)
    song.tracks = [track]
    path = _write(song, tmp_path)

    frags = ex.extract_riffs(path, "Fixture Song")

    assert len(frags) == 2
    assert isinstance(frags[0], dict)
    assert frags[0]["source_song"] == "Fixture Song"
    assert frags[0]["measure_index"] == 0
    assert [c["is_rest"] for c in frags[0]["cell"]] == [False, True, False]
    assert frags[0]["deltas"] == [0, 4]
    assert frags[0]["role"] == "verse"
    # same asdict schema riff_bank round-trips
    for key in ("cell", "deltas", "role", "raw_marker", "instrument", "source_type"):
        assert key in frags[0]


def test_extract_riffs_human_sections_override_role(tmp_path):
    song = make_song(2, markers={0: "Verse"}, title="Fixture Song")
    track = make_track(song, 1, {0: [40], 1: [41]}, instrument=30)
    song.tracks = [track]
    path = _write(song, tmp_path)

    # measure 0 starts at 0.0s (4/4 @ 120bpm), measure 1 at 2.0s
    human = [(0.0, 1.5, "breakdown")]
    frags = ex.extract_riffs(path, "Fixture Song", human_sections=human)

    assert frags[0]["role"] == "breakdown"
    # a real existing marker is preserved; only the role is overridden
    assert frags[0]["raw_marker"] == "Verse"
    assert frags[1]["role"] == "verse"  # not covered by a human label


def test_extract_riffs_human_sections_tag_fallback_marker(tmp_path):
    # No GP marker on measure 0 -> the human override supplies the provenance.
    song = make_song(1, title="Fixture Song")
    track = make_track(song, 1, {0: [40]}, instrument=30)
    song.tracks = [track]
    path = _write(song, tmp_path)

    frags = ex.extract_riffs(path, "Fixture Song", human_sections=[(0.0, 1.5, "solo")])

    assert frags[0]["role"] == "solo"
    assert frags[0]["raw_marker"] == "human:sections.jsonl"


def test_extract_riffs_unparseable_file_fails_closed(tmp_path):
    bad = tmp_path / "bad.gp5"
    bad.write_bytes(b"definitely not a guitar pro file")
    with pytest.raises(Exception):
        ex.extract_riffs(bad, "Bad Song")


def test_extract_riffs_missing_file_fails_closed(tmp_path):
    with pytest.raises(Exception):
        ex.extract_riffs(tmp_path / "missing.gp5", "Missing Song")


# --- extract_riffs_from_pack -------------------------------------------------

FIX_PACK = Path(__file__).parent / "fixtures" / "tabnotes_tiny"


def _fixture_pack():
    from boo_lab import tabnotes as tn

    return tn.load_pack(FIX_PACK)


def test_extract_riffs_from_pack_without_human_sections():
    frags = ex.extract_riffs_from_pack(_fixture_pack(), "tabnotes")

    assert len(frags) == 2
    for f in frags:
        assert all(k in f for k in ("cell", "deltas", "chord_notes"))
        assert f["role"] is None
        assert f["raw_marker"] is None
        assert f["instrument"] == "guitar"
        assert f["track"] == "tabnotes"


def test_extract_riffs_from_pack_human_sections_override_role():
    # fixture slots: bar 0 at 1.0s, bar 1 at 3.0s
    frags = ex.extract_riffs_from_pack(
        _fixture_pack(), "tabnotes", human_sections=[(0.0, 2.0, "breakdown")])

    assert frags[0]["role"] == "breakdown"
    assert frags[0]["raw_marker"] == "human:sections.jsonl"
    assert frags[1]["role"] is None  # not covered by a human label
    assert frags[1]["raw_marker"] is None


def test_extract_riffs_from_pack_no_guitar_track_is_empty():
    from boo_lab.tabnotes import TabNotesPack, TabTrack

    pack = TabNotesPack(id="p", title="P",
                        tracks=[TabTrack(index=0, name="Synth", category="other")])

    assert ex.extract_riffs_from_pack(pack, "P") == []


# --- GPIF fallback extraction ------------------------------------------------

BASS_ONLY_XML = """<GPIF><Score><Title>Bass Only</Title></Score>
  <Tracks><Track id="0"><Name>Bass</Name><InstrumentSet><Type>bass</Type></InstrumentSet></Track></Tracks>
  <MasterBars><MasterBar><Time>4/4</Time></MasterBar></MasterBars>
</GPIF>"""


def _write_gpif(tmp_path, xml=None, name="fixture.gp"):
    from test_gpif import FLAT_XML

    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif", FLAT_XML if xml is None else xml)
    return path


def test_extract_fragments_from_gpif_reads_written_bars(tmp_path):
    path = _write_gpif(tmp_path)

    frags = ex.extract_fragments_from_gpif(path, song_title="Gpif Tune")

    assert len(frags) == 2
    assert [f.measure_index for f in frags] == [0, 1]
    assert all(f.track == "Gtr" and f.instrument == "guitar" for f in frags)
    assert frags[0].cell and frags[0].deltas and frags[0].chord_notes
    assert frags[0].chord_frets == [[(1, 3), (2, 5)], [(1, 0)]]
    assert frags[1].chord_notes == [[45]]
    assert frags[0].role is None and frags[0].raw_marker is None


def test_extract_fragments_from_gpif_no_guitar_track_fails_closed(tmp_path):
    path = _write_gpif(tmp_path, xml=BASS_ONLY_XML)

    with pytest.raises(ValueError):
        ex.extract_fragments_from_gpif(path, song_title="Bass Only")


def test_extract_riffs_falls_back_to_gpif_when_pyguitarpro_raises(tmp_path, monkeypatch):
    path = _write_gpif(tmp_path)
    rb = ex._engine_riff_bank()
    monkeypatch.setattr(rb, "extract_fragments_from_file",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no pyguitarpro")))

    # human label covers bar 0 (0.0s) only -- proves the override used the
    # GPIF-written clock, not a pyguitarpro re-parse that would crash.
    frags = ex.extract_riffs(path, "Gpif Tune", human_sections=[(0.0, 1.5, "breakdown")])

    assert len(frags) == 2
    assert frags[0]["measure_index"] == 0
    assert frags[0]["role"] == "breakdown"
    assert frags[0]["raw_marker"] == "human:sections.jsonl"
    assert frags[1]["role"] is None


# --- estimate_from_gp --------------------------------------------------------


def test_estimate_from_gp_uses_markers_and_reports_duration(tmp_path):
    song = make_song(3, markers={0: "Intro", 2: "Breakdown"}, title="Fixture Song")
    track = make_track(song, 1, {0: [40], 1: [40], 2: [40]}, instrument=30)
    song.tracks = [track]
    path = _write(song, tmp_path)

    result = ex.estimate_from_gp(path)

    assert result["duration"] == pytest.approx(6.0)
    roles = [s["role"] for s in result["sections"]]
    assert roles == ["intro", "breakdown"]
    assert result["sections"][0]["start"] == 0.0
    assert result["sections"][1]["start"] == 4.0


@pytest.mark.parametrize(
    "marker,role,figure_id",
    [("Verse", "riff", "riff-A"), ("Chorus", "hook", "hook-A")],
)
def test_estimate_from_gp_marker_uses_lab_role(tmp_path, marker, role, figure_id):
    song = make_song(1, markers={0: marker}, title="Fixture Song")
    track = make_track(song, 1, {0: [40]}, instrument=30)
    song.tracks = [track]
    path = _write(song, tmp_path)

    result = ex.estimate_from_gp(path)

    assert result["sections"][0]["role"] == role
    assert result["sections"][0]["figure_id"] == figure_id


def test_estimate_from_gp_without_markers_is_honest(tmp_path):
    song = make_song(2, title="No Markers")
    track = make_track(song, 1, {0: [40], 1: [40]}, instrument=30)
    song.tracks = [track]
    path = _write(song, tmp_path)

    result = ex.estimate_from_gp(path)
    assert result["sections"] == []
    assert result["reason"] == "no markers in tab"


def test_estimate_from_gp_unparseable_file_fails_closed(tmp_path):
    bad = tmp_path / "bad.gp5"
    bad.write_bytes(b"nope")
    with pytest.raises(Exception):
        ex.estimate_from_gp(bad)


# --- estimate_from_gpif ------------------------------------------------------

FIX_GP7 = Path(__file__).parent / "fixtures" / "tiny.gp"


def test_estimate_from_gpif_uses_masterbar_sections_and_playback_order():
    result = ex.estimate_from_gpif(FIX_GP7)

    assert result["duration"] == pytest.approx(8.0)
    assert [s["source"] for s in result["sections"]] == ["gp-marker", "gp-marker"]
    # bar 1's section "A" plays at 2.0s and again at 6.0s (2x repeat)
    assert [s["start"] for s in result["sections"]] == [2.0, 6.0]
    assert result["sections"][0]["end"] == 6.0
    assert result["sections"][1]["end"] == 8.0
    assert result["sections"][0]["role"] == "riff"
    assert result["sections"][0]["figure_id"] == "riff-A"
    assert result["sections"][0]["unique"] is False


@pytest.mark.parametrize(
    "marker,role,figure_id",
    [("Verse", "riff", "riff-A"), ("Chorus", "hook", "hook-A")],
)
def test_estimate_from_gpif_marker_uses_lab_role(tmp_path, marker, role, figure_id):
    from test_gpif import FLAT_XML

    xml = FLAT_XML.replace("Verse", marker)
    path = _write_gpif(tmp_path, xml=xml)

    result = ex.estimate_from_gpif(path)

    assert result["sections"][0]["role"] == role
    assert result["sections"][0]["figure_id"] == figure_id


def test_estimate_from_gpif_unparseable_file_fails_closed(tmp_path):
    bad = tmp_path / "bad.gp"
    bad.write_bytes(b"nope")
    with pytest.raises(Exception):
        ex.estimate_from_gpif(bad)
