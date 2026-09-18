"""Build a real GP5 file from a parsed GPIF :class:`~boo_lab.gpif.GpifScore`.

LAW: machines never write ``sections.jsonl``. This is a *tab* writer, not a
label writer: it reconstructs the notated score (tracks, tunings, measures,
beats, notes, palm mutes, markers, repeats) so the existing GP5 readers in
``extract``/``sync``/Guess can use a GP7 file that pyguitarpro cannot open
directly. There is no TuxGuitar subprocess and no invented GP7 binary writer.
Dropped content (a string the track does not have, a drum track) is returned
so the caller records it instead of silently losing it.
"""
from __future__ import annotations

from pathlib import Path

# quarter-note beats -> GP duration value (1=whole .. 64), plus dotted.
_DURATIONS = [
    (4.0, 1, False), (3.0, 2, True), (2.0, 2, False), (1.5, 4, True),
    (1.0, 4, False), (0.75, 8, True), (0.5, 8, False), (0.375, 16, True),
    (0.25, 16, False), (0.125, 32, False), (0.0625, 64, False),
]
_DRUM_WORDS = ("drum", "percussion", "perc", "kit")


def _duration(beats: float):
    import guitarpro

    best = min(_DURATIONS, key=lambda d: abs(d[0] - (beats or 1.0)))
    return guitarpro.Duration(value=best[1], isDotted=best[2])


def _is_drum(name: str) -> bool:
    low = (name or "").lower()
    return any(w in low for w in _DRUM_WORDS)


def _standard_tuning() -> list[int]:
    return [40, 45, 50, 55, 59, 64]  # E standard, low to high


def gpif_to_gp5(score, out_path) -> tuple[Path, list[str]]:
    """Write ``score`` as a GP5 file at ``out_path``.

    Returns ``(Path, drops)`` where ``drops`` is the sorted list of things
    this writer could not represent (drum tracks skipped, notes on a string
    the track does not have). Raises when nothing playable was written."""
    import guitarpro
    from guitarpro.models import (
        Beat, Duration, GuitarString, Measure, MeasureHeader, Marker, Note,
        NoteEffect, NoteType, TimeSignature, Track,
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    drops: set[str] = set()

    song = guitarpro.Song(
        versionTuple=(5, 1, 0),
        title=(score.title or "untitled")[:64],
        artist="",
        tempo=int(round(score.tempo or 120.0)),
    )
    song.measureHeaders = []
    headers = []
    for i, mb in enumerate(score.masterbars):
        header = MeasureHeader(
            number=i + 1,
            timeSignature=TimeSignature(
                numerator=mb.time_n, denominator=Duration(value=mb.time_d)),
            isRepeatOpen=bool(mb.repeat_start),
        )
        if mb.repeat_end and mb.repeat_count >= 2:
            header.repeatClose = mb.repeat_count - 1
        if (mb.section or "").strip():
            header.marker = Marker(title=mb.section.strip()[:64])
        song.addMeasureHeader(header)
        headers.append(header)

    notes_by_track: dict[int, dict] = {}
    for n in score.notes:
        notes_by_track.setdefault(n.track, {}).setdefault(
            (n.bar, round(n.t_beat, 4)), []).append(n)

    tracks = []
    for ti, gt in enumerate(score.tracks):
        if _is_drum(gt.name):
            drops.add("skipped drum track '%s'" % (gt.name or ti + 1))
            continue
        tuning = [int(v) for v in (gt.tuning_midi or _standard_tuning())]
        strings = [GuitarString(number=i + 1, value=v) for i, v in enumerate(tuning)]
        track = Track(song, number=len(tracks) + 1,
                      name=(gt.name or "Track %d" % (ti + 1))[:64], strings=strings)
        track.measures = [Measure(track, h) for h in headers]

        grouped = notes_by_track.get(ti, {})
        max_fret = 0
        for bi, measure in enumerate(track.measures):
            voice = measure.voices[0]
            for (bar, _onset), group in sorted(grouped.items()):
                if bar != bi:
                    continue
                playable = []
                for n in group:
                    if n.string < 1 or n.string > len(strings):
                        drops.add("string %d out of range on track '%s'"
                                  % (n.string, gt.name or ti + 1))
                        continue
                    if n.fret < 0:
                        drops.add("negative fret on track '%s'" % (gt.name or ti + 1))
                        continue
                    max_fret = max(max_fret, int(n.fret))
                    playable.append(n)
                if not playable:
                    continue
                beat = Beat(voice, notes=[], duration=_duration(group[0].duration),
                            status=guitarpro.BeatStatus.normal)
                for n in playable:
                    beat.notes.append(Note(
                        beat, value=int(n.fret), string=int(n.string),
                        type=NoteType.normal,
                        effect=NoteEffect(palmMute=bool(n.palm_mute))))
                voice.beats.append(beat)
        if max_fret > track.fretCount:
            track.fretCount = max_fret
        tracks.append(track)

    if not tracks:
        raise ValueError("no playable tracks to write (all skipped as drums?)")

    song.tracks = tracks
    guitarpro.write(song, str(out_path), version=(5, 1, 0))
    return out_path, sorted(drops)
