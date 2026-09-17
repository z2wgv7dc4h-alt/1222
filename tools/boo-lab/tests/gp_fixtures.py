"""Synthetic, self-built pyguitarpro fixtures only -- mirrors engine/tests/
test_riff_bank.py's own documented strategy. NEVER a real copyrighted GP
file is used as a test fixture; everything here is constructed in memory or
written to a tmp_path from that in-memory object.
"""
from __future__ import annotations

import guitarpro


def make_song(num_measures, markers=None, title="Test Song", tempo=120):
    """`markers` maps a real 0-based measure index to a marker title."""
    song = guitarpro.Song()
    song.title = title
    song.tempo = tempo
    headers = []
    for i in range(num_measures):
        header = guitarpro.MeasureHeader(number=i + 1)
        if markers and i in markers:
            header.marker = guitarpro.Marker(title=markers[i])
        headers.append(header)
    song.measureHeaders = headers
    return song


def make_track(song, number, pitches_by_measure, instrument=30, is_percussion=False, name="Guitar"):
    track = guitarpro.Track(
        song,
        number=number,
        strings=[guitarpro.GuitarString(1, 0)],
        channel=guitarpro.MidiChannel(instrument=instrument),
        isPercussionTrack=is_percussion,
    )
    track.name = name
    measures = []
    for header in song.measureHeaders:
        measure = guitarpro.Measure(track, header)
        pitches = pitches_by_measure.get(header.number - 1, [])
        voice = guitarpro.Voice(measure)
        beats = []
        for p in pitches:
            beat = guitarpro.Beat(voice)
            if p is None:
                beat.status = guitarpro.BeatStatus.rest
                beat.notes = []
            else:
                beat.status = guitarpro.BeatStatus.normal
                note = guitarpro.Note(beat, value=p, string=1)
                beat.notes = [note]
            beat.duration = guitarpro.Duration(value=8)
            beats.append(beat)
        voice.beats = beats
        second_voice = guitarpro.Voice(measure)
        empty_beat = guitarpro.Beat(second_voice)
        empty_beat.status = guitarpro.BeatStatus.empty
        empty_beat.duration = guitarpro.Duration(value=8)
        second_voice.beats = [empty_beat]
        measure.voices = [voice, second_voice]
        measures.append(measure)
    track.measures = measures
    return track
