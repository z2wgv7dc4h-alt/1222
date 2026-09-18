"""Tests for src/boo_lab/gpif.py -- parse a real Content/score.gpif zip.

The fixture `tests/fixtures/tiny.gp` is hand-made (2 bars 4/4 120 bpm, one
D-standard track, four notes, a 2x repeat); no commercial tab is bundled.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from boo_lab import cli, gpif

FIX = Path(__file__).parent / "fixtures" / "tiny.gp"


def test_open_gp_reads_the_gpif_entry():
    z = gpif.open_gp(FIX)
    try:
        names = [n.replace("\\", "/") for n in z.namelist()]
        assert "VERSION" in names
        assert "Content/score.gpif" in names
    finally:
        z.close()


def test_open_gp_fails_closed_without_a_score():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "empty.gp"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("VERSION", "7.0")
        with pytest.raises(ValueError):
            gpif.open_gp(p)


def test_open_gp_rejects_a_non_zip(tmp_path):
    p = tmp_path / "not.gp"
    p.write_text("definitely not a zip", encoding="utf-8")
    with pytest.raises((zipfile.BadZipFile, ValueError)):
        gpif.open_gp(p)


def test_parses_tracks_tunings_and_markers():
    score = gpif.load_score(FIX)

    assert score.title == "Tiny"
    assert score.tempo == 120.0
    assert [(t.name, t.tuning_midi) for t in score.tracks] == [
        ("Guitar", [38, 43, 48, 53, 57, 62])
    ]
    assert len(score.masterbars) == 2
    assert (score.masterbars[0].time_n, score.masterbars[0].time_d) == (4, 4)
    assert score.masterbars[0].repeat_start is True
    assert score.masterbars[1].repeat_end is True
    assert score.masterbars[1].repeat_count == 2
    assert score.masterbars[1].section == "A"
    assert gpif.count_markers(score) == 1


def test_repeat_expands_the_playback():
    score = gpif.load_score(FIX)

    assert gpif.playback_bar_order(score) == [0, 1, 0, 1]
    assert gpif.playback_beats(score) == 16.0          # 4 bars * 4 beats
    assert gpif.duration_sec(score) == pytest.approx(8.0)  # 16 beats at 120 bpm


def test_parses_notes_with_positions_palm_mute_and_midi():
    score = gpif.load_score(FIX)

    got = [(n.track, n.bar, n.t_beat, n.string, n.fret, n.duration,
            n.palm_mute, n.voice, n.midi) for n in score.notes]
    # midi = tuning[string-1] + fret, tuning [38,43,48,53,57,62]
    assert got == [
        (0, 0, 0.0, 5, 7, 2.0, False, 0, 57 + 7),
        (0, 0, 2.0, 5, 9, 2.0, True, 0, 57 + 9),
        (0, 0, 0.0, 6, 0, 2.0, False, 1, 62 + 0),   # second voice in bar 0
        (0, 1, 0.0, 6, 3, 2.0, False, 0, 62 + 3),
        (0, 1, 2.0, 6, 5, 2.0, False, 0, 62 + 5),
    ]


def test_no_repeat_plays_once_and_tempo_change_is_applied():
    xml = """<?xml version="1.0"?>
<GPIF><Score>
  <Title>T</Title>
  <MasterBars>
    <MasterBar><Time>4/4</Time><Tempo>120</Tempo></MasterBar>
    <MasterBar><Time>4/4</Time><Tempo>60</Tempo></MasterBar>
  </MasterBars>
  <Tracks><Track id="0"><Name>G</Name></Track></Tracks>
  <Bars></Bars>
</Score></GPIF>"""
    score = gpif.parse_gpif(xml)

    assert gpif.playback_bar_order(score) == [0, 1]
    assert gpif.playback_beats(score) == 8.0
    assert gpif.duration_sec(score) == pytest.approx(6.0)  # 4 beats @120 (2s) + 4 @60 (4s)


def test_parses_namespaced_gpif():
    xml = """<GPIF xmlns="http://www.guitar-pro.com/gpif">
  <Score><Title>N</Title>
    <MasterBars><MasterBar><Time><Numerator>3</Numerator><Denominator>4</Denominator></Time></MasterBar></MasterBars>
    <Tracks><Track id="0"><Name>B</Name></Track></Tracks>
  </Score></GPIF>"""
    score = gpif.parse_gpif(xml)

    assert score.title == "N"
    assert (score.masterbars[0].time_n, score.masterbars[0].time_d) == (3, 4)
    assert gpif.playback_beats(score) == 3.0


FLAT_XML = """<GPIF>
  <Score><Title>Flat</Title><Artist>A</Artist><Album>B</Album></Score>
  <MasterTrack><Tracks>0 1</Tracks><Automations>
    <Automation><Type>Tempo</Type><Bar>0</Bar><Position>0</Position><Value>120 2</Value></Automation>
    <Automation><Type>Tempo</Type><Bar>1</Bar><Position>0</Position><Value>90 2</Value></Automation>
  </Automations></MasterTrack>
  <Tracks>
    <Track id="0"><Name>Gtr</Name><InstrumentSet><Type>electricGuitar</Type></InstrumentSet>
      <Staves><Staff><Properties><Property name="CapoFret"><Fret>2</Fret></Property>
        <Property name="Tuning"><Pitches>38 43 48 53 57 62</Pitches></Property></Properties></Staff></Staves></Track>
    <Track id="1"><Name>Bass</Name><InstrumentSet><Type>bass</Type></InstrumentSet></Track>
  </Tracks>
  <MasterBars>
    <MasterBar><Time>4/4</Time><Bars>10 20</Bars></MasterBar>
    <MasterBar><Time>3/4</Time><Bars>11 21</Bars><Section><Text>Verse</Text></Section></MasterBar>
  </MasterBars>
  <Rhythms><Rhythm id="0"><NoteValue>Quarter</NoteValue></Rhythm></Rhythms>
  <Bars>
    <Bar id="10"><Voices>100</Voices></Bar><Bar id="11"><Voices>101</Voices></Bar>
    <Bar id="20"><Voices>200</Voices></Bar><Bar id="21"><Voices>201</Voices></Bar>
  </Bars>
  <Voices>
    <Voice id="100"><Beats>1000 1001</Beats></Voice><Voice id="101"><Beats>1010</Beats></Voice>
    <Voice id="200"><Beats>2000</Beats></Voice><Voice id="201"><Beats /></Voice>
  </Voices>
  <Beats>
    <Beat id="1000"><Dynamic>F</Dynamic><Rhythm ref="0"/><Chord><Name>C5</Name></Chord><Text>hit</Text><Notes>1 2</Notes></Beat>
    <Beat id="1001"><Dynamic>P</Dynamic><Rhythm ref="0"/><Notes>3</Notes></Beat>
    <Beat id="1010"><Dynamic>F</Dynamic><Rhythm ref="0"/><Notes>4</Notes></Beat>
    <Beat id="2000"><Dynamic>F</Dynamic><Rhythm ref="0"/><Notes>5</Notes></Beat>
  </Beats>
  <Notes>
    <Note id="1"><Properties><Property name="String"><String>0</String></Property><Property name="Fret"><Fret>3</Fret></Property><Property name="Midi"><Number>41</Number></Property></Properties><PalmMute/></Note>
    <Note id="2"><Properties><Property name="String"><String>1</String></Property><Property name="Fret"><Fret>5</Fret></Property><Property name="Midi"><Number>48</Number></Property><Property name="Hammer"><Hammer>true</Hammer></Property></Properties></Note>
    <Note id="3"><Properties><Property name="String"><String>0</String></Property><Property name="Fret"><Fret>0</Fret></Property></Properties></Note>
    <Note id="4"><Properties><Property name="String"><String>0</String></Property><Property name="Fret"><Fret>7</Fret></Property></Properties></Note>
    <Note id="5"><Properties><Property name="String"><String>0</String></Property><Property name="Fret"><Fret>2</Fret></Property></Properties></Note>
  </Notes>
</GPIF>"""


def test_flat_gp8_richer_model():
    score = gpif.parse_gpif(FLAT_XML)

    assert (score.title, score.artist, score.album) == ("Flat", "A", "B")
    assert [(t.name, t.instrument, t.capo, t.tuning_midi) for t in score.tracks] == [
        ("Gtr", "electricGuitar", 2, [38, 43, 48, 53, 57, 62]),
        ("Bass", "bass", None, []),
    ]
    assert gpif.tempo_map(score) == [(0.0, 120.0), (4.0, 90.0)]  # unexpanded beats
    assert gpif.time_sig_map(score) == [(0, 4, 4), (1, 3, 4)]
    assert gpif.section_list(score) == [(1, "Verse")]


def test_flat_notes_carry_midi_and_articulations():
    score = gpif.parse_gpif(FLAT_XML)

    assert len(score.notes) == 5
    first = score.notes[0]
    assert (first.track, first.bar, first.string, first.fret) == (0, 0, 1, 3)
    assert first.midi == 41 and first.palm_mute is True
    assert "palm_mute" in first.articulations
    assert score.notes[1].midi == 48 and "hammer" in score.notes[1].articulations


def test_flat_beats_carry_dynamic_chord_text_and_notes():
    score = gpif.parse_gpif(FLAT_XML)

    b0 = score.beats[0]
    assert (b0.track, b0.bar, b0.t_beat, b0.duration) == (0, 0, 0.0, 1.0)
    assert b0.dynamic == "F" and b0.chord == "C5" and b0.text == "hit"
    assert len(b0.notes) == 2
    assert score.beats[1].dynamic == "P" and len(score.beats[1].notes) == 1
    # a tempo change after bar 0 makes bar 1 shorter in seconds
    assert gpif.duration_sec(score) == pytest.approx(4 * 0.5 + 3 * (60.0 / 90.0))
    assert len(gpif.note_events(score)) == 5


def test_nested_fixture_exposes_beats_voices_and_articulations():
    score = gpif.load_score(FIX)

    assert len(score.beats) == 5                    # 2 + 1 (bar 0) + 2 (bar 1)
    assert all(b.dynamic is None for b in score.beats)
    assert "palm_mute" in score.notes[1].articulations
    assert score.notes[1].palm_mute is True
    # every note has a midi from the known tuning; two voices in bar 0
    assert all(n.midi is not None for n in score.notes)
    assert score.notes[2].voice == 1
    assert {n.voice for n in score.notes if n.bar == 0} == {0, 1}


def test_note_events_keep_seconds_first_and_are_finite():
    score = gpif.load_score(FIX)

    events = gpif.note_events(score)
    assert len(events) == 10                         # 5 notes x 2 repeat passes
    assert all(len(e) == 4 for e in events)
    assert events[0][0] == 0.0 and events[0][1] == 57 + 7
    assert events[0][3] is False and events[1][3] is True
    assert gpif.duration_sec(score) > 0 and gpif.duration_sec(score) < 1e6


def test_cli_prints_counts_and_writes_nothing(capsys):
    assert cli.main(["gpif", "--path", str(FIX)]) == 0
    out = capsys.readouterr().out
    assert "duration_sec=8.000" in out
    assert "n_bars=2" in out
    assert "n_notes=5" in out
    assert "n_markers=1" in out
    assert "n_with_midi=5" in out


def test_cli_bad_path_is_a_clean_error(tmp_path, capsys):
    assert cli.main(["gpif", "--path", str(tmp_path / "missing.gp")]) == 1
    assert "gpif:" in capsys.readouterr().out
