"""GPIF reader -- a parsed GP7/GP6 ``.gpx``/``.gp`` score.

LAW: GP7 may supply markers/notes ONLY via a parsed GPIF score, never via
Guess invention. This module reads the real ``Content/score.gpif`` XML out of
the zip container (no GP7 binary writer, no TuxGuitar, no GP5 conversion) and
exposes the few fields the lab needs: title, tempo, tracks/tunings, masterbars
(time signature, repeat map, section marker) and notes (bar/beat/string/fret).
It never writes ``sections.jsonl`` or ``drafts.jsonl``.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class GpifTrack:
    name: str
    tuning_midi: list[int] = field(default_factory=list)


@dataclass
class GpifMasterBar:
    time_n: int
    time_d: int
    repeat_start: bool
    repeat_end: bool
    repeat_count: int
    section: str | None
    tempo: float | None = None


@dataclass
class GpifNote:
    track: int
    bar: int
    t_beat: float          # quarter-note beats from the start of its bar
    string: int
    fret: int
    duration: float        # quarter-note beats
    palm_mute: bool


@dataclass
class GpifScore:
    title: str
    tempo: float
    tracks: list[GpifTrack] = field(default_factory=list)
    masterbars: list[GpifMasterBar] = field(default_factory=list)
    notes: list[GpifNote] = field(default_factory=list)


# --- XML plumbing ---------------------------------------------------------
# `{*}` matches a tag in any (or no) namespace, so real GPIF files with a
# namespace and our hand-made fixture both read the same way.
def _find(elem, name):
    if elem is None:
        return None
    return elem.find("{*}" + name)


def _findall(elem, name):
    if elem is None:
        return []
    return elem.findall("{*}" + name)


def _text(elem):
    if elem is None:
        return None
    return elem.text


def _to_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _to_float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


# --- container ------------------------------------------------------------
def open_gp(path):
    """Open a GP7/GP6 zip and require a ``Content/score.gpif`` entry.

    Returns the open ``zipfile.ZipFile`` (caller closes). Raises ``ValueError``
    when the score entry is missing -- fail closed, never guess a format."""
    import zipfile

    z = zipfile.ZipFile(path)
    entry = _score_entry(z)
    if entry is None:
        z.close()
        raise ValueError("not a GPIF file: Content/score.gpif missing")
    return z


def _score_entry(z):
    for name in z.namelist():
        if name.replace("\\", "/").endswith("Content/score.gpif"):
            return name
    return None


def load_score(path) -> GpifScore:
    """``open_gp`` + read + ``parse_gpif`` for one file."""
    with open_gp(path) as z:
        entry = _score_entry(z)
        data = z.read(entry)
    return parse_gpif(data)


# --- parser ---------------------------------------------------------------
_TIME_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


def _parse_time(el) -> tuple[int, int]:
    if el is None:
        return 4, 4
    m = _TIME_RE.search(el.text or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    num = _to_int(_text(_find(el, "Numerator")))
    den = _to_int(_text(_find(el, "Denominator")))
    return num or 4, den or 4


def _section_text(el):
    if el is None:
        return None
    txt = _text(_find(el, "Text"))
    if txt is None:
        txt = el.text or ""
    txt = (txt or "").strip()
    return txt or None


def _parse_repeat(reps) -> tuple[bool, bool, int]:
    start = end = False
    count = 0
    for r in reps:
        st = (r.get("start") or "").lower() in {"true", "1"}
        en = (r.get("end") or "").lower() in {"true", "1"}
        c = _to_int(r.get("count"))
        if c is None:
            c = _to_int(_text(_find(r, "Count"))) or 0
        if st:
            start = True
        if en or (c and not st):
            end = True
        if c > count:
            count = c
    return start, end, count


def _parse_tuning(tr) -> list[int]:
    el = _find(tr, "Tuning")
    if el is None:
        return []
    vals = []
    for s in _findall(el, "String"):
        v = _to_int(_text(s))
        if v is not None:
            vals.append(v)
    if not vals:
        txt = (el.text or "").strip()
        if txt:
            vals = [int(x) for x in txt.split() if x.lstrip("-").isdigit()]
    return vals


_NOTE_VALUE = {
    "whole": 4.0, "half": 2.0, "quarter": 1.0, "eighth": 0.5, "8th": 0.5,
    "sixteenth": 0.25, "16th": 0.25, "thirtysecond": 0.125, "32nd": 0.125,
    "sixtyfourth": 0.0625, "64th": 0.0625,
}


def _rhythm_beats(rh) -> float:
    nv = (_text(_find(rh, "NoteValue")) or "quarter").strip().lower()
    base = _NOTE_VALUE.get(nv, 1.0)
    dots = len(_findall(rh, "AugmentationDot"))
    if dots:
        base *= 2.0 - 0.5 ** dots
    tup = _find(rh, "PrimaryTuplet")
    if tup is not None:
        num = _to_int(tup.get("num"))
        den = _to_int(tup.get("den"))
        if num and den:
            base *= den / num
    return base


def _beat_beats(beat, rhythms: dict) -> float:
    rh = _find(beat, "Rhythm")
    if rh is None:
        return 1.0
    ref = rh.get("ref")
    if ref is not None and ref in rhythms:
        return rhythms[ref]
    return _rhythm_beats(rh)


def parse_gpif(xml) -> GpifScore:
    """Parse ``score.gpif`` XML (bytes or str) into a :class:`GpifScore`."""
    if isinstance(xml, (bytes, bytearray)):
        xml = bytes(xml).decode("utf-8", "replace")
    root = ET.fromstring(xml)
    score = _find(root, "Score")
    if score is None:
        score = root

    title = (_text(_find(score, "Title")) or "").strip()

    masterbars: list[GpifMasterBar] = []
    for mb in _findall(_find(score, "MasterBars"), "MasterBar"):
        time_n, time_d = _parse_time(_find(mb, "Time"))
        tempo = _to_float(_text(_find(mb, "Tempo")))
        section = _section_text(_find(mb, "Section"))
        start, end, count = _parse_repeat(_findall(mb, "Repeat"))
        masterbars.append(GpifMasterBar(time_n, time_d, start, end, count, section, tempo))

    tracks: list[GpifTrack] = []
    for tr in _findall(_find(score, "Tracks"), "Track"):
        tracks.append(GpifTrack((_text(_find(tr, "Name")) or "").strip(), _parse_tuning(tr)))

    rhythms: dict = {}
    for rh in _findall(_find(score, "Rhythms"), "Rhythm"):
        rid = rh.get("id")
        if rid is not None:
            rhythms[rid] = _rhythm_beats(rh)

    notes: list[GpifNote] = []
    for bi, bar in enumerate(_findall(_find(score, "Bars"), "Bar")):
        track = _to_int(bar.get("track")) or 0
        voices = _findall(bar, "Voices")
        for vhost in voices:
            for voice in _findall(vhost, "Voice"):
                t_beat = 0.0
                for beat in _findall(_find(voice, "Beats"), "Beat"):
                    dur = _beat_beats(beat, rhythms)
                    for note in _findall(_find(beat, "Notes"), "Note"):
                        props = _find(note, "Properties")
                        if props is None:
                            props = note
                        string = _to_int(_text(_find(props, "String")))
                        fret = _to_int(_text(_find(props, "Fret")))
                        if string is None or fret is None:
                            continue
                        palm = (_find(note, "PalmMute") is not None
                                or _find(props, "PalmMute") is not None)
                        notes.append(GpifNote(track, bi, t_beat, string, fret, dur, palm))
                    t_beat += dur
                break  # first voice only, like the existing tab walk
    tempo = next((m.tempo for m in masterbars if m.tempo), 120.0)
    return GpifScore(title, float(tempo), tracks, masterbars, notes)


# --- playback -------------------------------------------------------------
def playback_bar_order(score: GpifScore) -> list[int]:
    """Masterbar indices in real playback order, expanding repeat groups
    (the same open/close/count idea as Guess's ``sync._playback_order``)."""
    bars = score.masterbars
    n = len(bars)
    order: list[int] = []
    counts: dict = {}
    open_idx = None
    i = 0
    guard = 0
    while 0 <= i < n and guard < 200000:
        guard += 1
        mb = bars[i]
        order.append(i)
        if mb.repeat_start:
            open_idx = i
            counts.setdefault(i, 0)
        if mb.repeat_end and open_idx is not None:
            total = max(mb.repeat_count, bars[open_idx].repeat_count)
            if total >= 2:
                counts[open_idx] = counts.get(open_idx, 0) + 1
                if counts[open_idx] < total:
                    i = open_idx
                    continue
            open_idx = None
        i += 1
    return order


def playback_beats(score: GpifScore) -> float:
    """Total quarter-note beats over the expanded playback, using each
    masterbar's own time signature."""
    return sum(score.masterbars[i].time_n * 4.0 / score.masterbars[i].time_d
               for i in playback_bar_order(score))


def duration_sec(score: GpifScore) -> float:
    """Notated length in seconds over the expanded playback, applying each
    masterbar's tempo (falling back to the score tempo, then 120)."""
    total = 0.0
    for i in playback_bar_order(score):
        mb = score.masterbars[i]
        bpm = mb.tempo or score.tempo or 120.0
        total += (mb.time_n * 4.0 / mb.time_d) * 60.0 / max(bpm, 1.0)
    return total


def note_events(score: GpifScore) -> list[tuple[float, list, float]]:
    """``(seconds, [], duration_sec)`` per note in playback order (repeats
    expanded). Pitches are intentionally empty: GPIF string numbering is not
    trusted enough to feed the chroma witness, so only the onset clock is used
    (the caller's ``_tab_notes`` shape, for `sync`)."""
    by_bar: dict = {}
    for n in score.notes:
        by_bar.setdefault(n.bar, []).append(n)
    events: list[tuple[float, list, float]] = []
    t = 0.0
    for bi in playback_bar_order(score):
        mb = score.masterbars[bi]
        bpm = mb.tempo or score.tempo or 120.0
        beat_sec = 60.0 / max(bpm, 1.0)
        for n in by_bar.get(bi, []):
            events.append((t + n.t_beat * beat_sec, [], n.duration * beat_sec))
        t += (mb.time_n * 4.0 / mb.time_d) * beat_sec
    return events


def count_markers(score: GpifScore) -> int:
    return sum(1 for mb in score.masterbars if (mb.section or "").strip())
