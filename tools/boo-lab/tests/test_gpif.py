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


def test_parses_notes_with_positions_and_palm_mute():
    score = gpif.load_score(FIX)

    got = [(n.track, n.bar, n.t_beat, n.string, n.fret, n.duration, n.palm_mute)
           for n in score.notes]
    assert got == [
        (0, 0, 0.0, 5, 7, 2.0, False),
        (0, 0, 2.0, 5, 9, 2.0, True),
        (0, 1, 0.0, 6, 3, 2.0, False),
        (0, 1, 2.0, 6, 5, 2.0, False),
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


def test_cli_prints_counts_and_writes_nothing(capsys):
    assert cli.main(["gpif", "--path", str(FIX)]) == 0
    out = capsys.readouterr().out
    assert "duration_sec=8.000" in out
    assert "n_bars=2" in out
    assert "n_notes=4" in out
    assert "n_markers=1" in out


def test_cli_bad_path_is_a_clean_error(tmp_path, capsys):
    assert cli.main(["gpif", "--path", str(tmp_path / "missing.gp")]) == 1
    assert "gpif:" in capsys.readouterr().out
