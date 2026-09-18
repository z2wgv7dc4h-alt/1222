"""GPIF reader -- a parsed GP7/GP6 score (``.gp``/``.gpx``).

LAW: GP7 may supply markers/notes ONLY via a parsed GPIF score, never via
Guess invention. This module reads the real ``Content/score.gpif`` XML out of
the zip container (no GP7 binary writer, no TuxGuitar) and exposes the richer
score the app project holds: score metadata, tracks (name, tuning, instrument
type, capo), masterbars (time signature, repeat map, section, tempo map),
beats (dynamic, chord, text) and notes (bar/beat/string/fret/duration/midi plus
articulations). It never writes ``sections.jsonl`` or ``drafts.jsonl``.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class GpifTrack:
    name: str
    tuning_midi: list[int] = field(default_factory=list)
    instrument: str | None = None   # e.g. "electricGuitar", "bass", "drumKit"
    capo: int | None = None


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
    voice: int = 0
    midi: int | None = None
    dead: bool = False
    accent: bool = False
    hammer: bool = False
    slide: str | None = None
    articulations: list[str] = field(default_factory=list)


@dataclass
class GpifBeat:
    track: int
    bar: int
    t_beat: float
    duration: float
    dynamic: str | None = None
    chord: str | None = None
    text: str | None = None
    notes: list[GpifNote] = field(default_factory=list)


@dataclass
class GpifScore:
    title: str
    tempo: float
    artist: str = ""
    album: str = ""
    tracks: list[GpifTrack] = field(default_factory=list)
    masterbars: list[GpifMasterBar] = field(default_factory=list)
    notes: list[GpifNote] = field(default_factory=list)
    beats: list[GpifBeat] = field(default_factory=list)


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


def _local(tag) -> str:
    return tag.split("}")[-1]


def _iter(elem, name):
    """Every descendant with this local tag name (id-reference GPIF)."""
    if elem is None:
        return []
    return [e for e in elem.iter() if _local(e.tag) == name]


def _property_value(node, name):
    """A GP8 ``<Property name="...">`` child's text (e.g. String/Fret)."""
    for prop in _iter(_find(node, "Properties"), "Property"):
        if (prop.get("name") or "").lower() == name.lower():
            for c in prop:
                return _text(c)
    return None


def _parse_tuning_flat(tr) -> list[int]:
    for prop in _iter(tr, "Property"):
        if (prop.get("name") or "").lower() == "tuning":
            txt = (_text(_find(prop, "Pitches")) or "").strip()
            return [int(x) for x in txt.split() if x.lstrip("-").isdigit()]
    return []


def _parse_instrument_flat(tr) -> str | None:
    iset = _find(tr, "InstrumentSet")
    if iset is None:
        return None
    return ((_text(_find(iset, "Type")) or "").strip()
            or (_text(_find(iset, "Name")) or "").strip() or None)


def _parse_capo_flat(tr) -> int | None:
    for prop in _iter(tr, "Property"):
        if (prop.get("name") or "").lower() == "capofret":
            return _to_int(_text(_find(prop, "Fret")))
    return None


# GPIF note articulations show up either as direct flag elements or as
# <Property name="..."> entries; normalize both to one snake_case token set.
_ARTICULATIONS = {
    "palmmute": "palm_mute", "dead": "dead", "deadnote": "dead",
    "ghost": "ghost", "ghostnote": "ghost", "hammer": "hammer",
    "hammeron": "hammer", "pulloff": "pull_off", "slide": "slide",
    "bend": "bend", "harmonic": "harmonic", "naturalharmonic": "harmonic",
    "letring": "let_ring", "staccato": "staccato", "vibrato": "vibrato",
    "accentuation": "accent", "accentednote": "accent",
    "heavyaccentuatednote": "heavy_accent", "tie": "tie",
    "trill": "trill", "tremolopicking": "tremolo",
}


def _art_token(name) -> str | None:
    return _ARTICULATIONS.get(re.sub(r"[^a-z]", "", (name or "").lower()))


def _flag_truthy(node) -> bool:
    if node is None:
        return False
    if (node.text or "").strip().lower() in ("false", "0", "no"):
        return False
    for c in node:
        if (c.text or "").strip().lower() in ("false", "0", "no"):
            return False
    return True


def _note_articulations(node) -> list[str]:
    found: set[str] = set()
    for c in list(node):
        token = _art_token(_local(c.tag))
        if token and _flag_truthy(c):
            found.add(token)
    for prop in _iter(_find(node, "Properties"), "Property"):
        token = _art_token(prop.get("name"))
        if token and _flag_truthy(prop):
            found.add(token)
    return sorted(found)


def _computed_midi(tuning, string, fret) -> int | None:
    """``tuning_midi[string] + fret`` for the 1-based `string` when that index
    exists; otherwise ``None`` (never invented)."""
    if not tuning:
        return None
    idx = int(string) - 1
    if 0 <= idx < len(tuning):
        return int(tuning[idx]) + int(fret)
    return None


def _slide_kind(node) -> str | None:
    """A slide's kind text when the note carries one, else ``None``."""
    el = _find(node, "Slide")
    if el is None:
        for prop in _iter(_find(node, "Properties"), "Property"):
            if (prop.get("name") or "").lower() == "slide":
                el = prop
                break
    if el is None:
        return None
    return ((_text(_find(el, "Type")) or _text(el) or "slide").strip() or "slide")


def _note_flags(arts: list[str], node):
    """``(dead, accent, hammer, slide)`` from the normalized articulations."""
    dead = "dead" in arts
    accent = "accent" in arts or "heavy_accent" in arts
    hammer = "hammer" in arts
    slide = _slide_kind(node) if "slide" in arts else None
    return dead, accent, hammer, slide


def _beat_meta(beat) -> tuple[str | None, str | None, str | None]:
    dynamic = (_text(_find(beat, "Dynamic")) or "").strip() or None
    text = (_text(_find(beat, "Text")) or "").strip() or None
    chord_el = _find(beat, "Chord")
    chord = None
    if chord_el is not None:
        chord = ((_text(_find(chord_el, "Name")))
                 or (_text(_find(chord_el, "String"))) or "").strip() or None
    return dynamic, chord, text


def _parse_flat(root, title) -> GpifScore:
    """GP8/alphaTab GPIF: flat ``MasterBars``/``Bars``/``Voices``/``Beats``/
    ``Notes``/``Rhythms`` containers linked by ``id`` refs, tempo in
    ``MasterTrack`` automations. The schema this corpus actually uses."""
    tempos: dict = {}
    for a in _findall(_find(_find(root, "MasterTrack"), "Automations"), "Automation"):
        if (_text(_find(a, "Type")) or "").strip().lower() != "tempo":
            continue
        bar = _to_int(_text(_find(a, "Bar")))
        bpm = _to_float((_text(_find(a, "Value")) or "").split(" ")[0])
        if bar is not None and bpm:
            tempos[bar] = bpm

    masterbars: list[GpifMasterBar] = []
    bar_ids_by_mb: list[list[int]] = []
    for mb in _findall(_find(root, "MasterBars"), "MasterBar"):
        time_n, time_d = _parse_time(_find(mb, "Time"))
        section = _section_text(_find(mb, "Section"))
        start, end, count = _parse_repeat(_findall(mb, "Repeat"))
        ids = [int(x) for x in (_text(_find(mb, "Bars")) or "").split()
               if x.lstrip("-").isdigit()]
        masterbars.append(GpifMasterBar(time_n, time_d, start, end, count, section, None))
        bar_ids_by_mb.append(ids)
    for i, mb in enumerate(masterbars):
        if i in tempos:
            mb.tempo = tempos[i]
    tempo = next((m.tempo for m in masterbars if m.tempo), 120.0)

    tracks = [GpifTrack((_text(_find(tr, "Name")) or "").strip(),
                        _parse_tuning_flat(tr),
                        _parse_instrument_flat(tr),
                        _parse_capo_flat(tr))
              for tr in _findall(_find(root, "Tracks"), "Track")]

    rhythms: dict = {}
    for rh in _findall(_find(root, "Rhythms"), "Rhythm"):
        if rh.get("id") is not None:
            rhythms[rh.get("id")] = _rhythm_beats(rh)

    bars_by_id = {b.get("id"): _text(_find(b, "Voices")) or ""
                  for b in _findall(_find(root, "Bars"), "Bar")}
    voices_by_id = {v.get("id"): _text(_find(v, "Beats")) or ""
                    for v in _findall(_find(root, "Voices"), "Voice")}
    beats_by_id: dict = {}
    for b in _findall(_find(root, "Beats"), "Beat"):
        rh = _find(b, "Rhythm")
        beats_by_id[b.get("id")] = (rh.get("ref") if rh is not None else None,
                                    _text(_find(b, "Notes")) or "", b)
    notes_by_id = {n.get("id"): n for n in _findall(_find(root, "Notes"), "Note")}

    score = _find(root, "Score")
    artist = (_text(_find(score, "Artist")) or "").strip()
    album = (_text(_find(score, "Album")) or "").strip()

    notes: list[GpifNote] = []
    beats: list[GpifBeat] = []
    for bi, ids in enumerate(bar_ids_by_mb):
        for ti in range(len(tracks)):
            if ti >= len(ids):
                continue
            voice_ids = (bars_by_id.get(str(ids[ti])) or "").split()
            tuning = tracks[ti].tuning_midi if ti < len(tracks) else []
            for vi, vid in enumerate(voice_ids):
                t_beat = 0.0
                for beid in (voices_by_id.get(vid) or "").split():
                    ref, note_ids, beat_node = beats_by_id.get(beid, (None, "", None))
                    dur = rhythms.get(ref, 1.0)
                    dynamic, chord, text = _beat_meta(beat_node)
                    beat = GpifBeat(ti, bi, t_beat, dur, dynamic, chord, text, [])
                    for nid in note_ids.split():
                        node = notes_by_id.get(nid)
                        if node is None:
                            continue
                        string = _to_int(_property_value(node, "String"))
                        fret = _to_int(_property_value(node, "Fret"))
                        if string is None or fret is None:
                            continue
                        arts = _note_articulations(node)
                        palm = "palm_mute" in arts or _find(node, "PalmMute") is not None
                        if palm and "palm_mute" not in arts:
                            arts = sorted(set(arts) | {"palm_mute"})
                        # GP8 String is 0-based; normalize to the 1-based Note.string
                        string += 1
                        dead, accent, hammer, slide = _note_flags(arts, node)
                        note = GpifNote(ti, bi, t_beat, string, fret, dur, palm,
                                        vi, _computed_midi(tuning, string, fret),
                                        dead, accent, hammer, slide, arts)
                        notes.append(note)
                        beat.notes.append(note)
                    beats.append(beat)
                    t_beat += dur
    return GpifScore(title, float(tempo), artist, album, tracks, masterbars, notes, beats)


def parse_gpif(xml) -> GpifScore:
    """Parse ``score.gpif`` XML (bytes or str) into a :class:`GpifScore`.

    Handles both the flat GP8/alphaTab schema (flat id-reference containers)
    and the nested legacy schema used by the test fixture."""
    if isinstance(xml, (bytes, bytearray)):
        xml = bytes(xml).decode("utf-8", "replace")
    root = ET.fromstring(xml)
    score = _find(root, "Score")
    if score is None:
        score = root

    title = (_text(_find(score, "Title")) or "").strip()

    if _find(root, "MasterBars") is not None and _find(score, "MasterBars") is None:
        return _parse_flat(root, title)

    masterbars: list[GpifMasterBar] = []
    for mb in _findall(_find(score, "MasterBars"), "MasterBar"):
        time_n, time_d = _parse_time(_find(mb, "Time"))
        tempo = _to_float(_text(_find(mb, "Tempo")))
        section = _section_text(_find(mb, "Section"))
        start, end, count = _parse_repeat(_findall(mb, "Repeat"))
        masterbars.append(GpifMasterBar(time_n, time_d, start, end, count, section, tempo))

    tracks: list[GpifTrack] = []
    for tr in _findall(_find(score, "Tracks"), "Track"):
        tracks.append(GpifTrack((_text(_find(tr, "Name")) or "").strip(),
                                _parse_tuning(tr),
                                _parse_instrument_flat(tr),
                                _parse_capo_flat(tr)))

    rhythms: dict = {}
    for rh in _findall(_find(score, "Rhythms"), "Rhythm"):
        rid = rh.get("id")
        if rid is not None:
            rhythms[rid] = _rhythm_beats(rh)

    artist = (_text(_find(score, "Artist")) or "").strip()
    album = (_text(_find(score, "Album")) or "").strip()

    notes: list[GpifNote] = []
    beats: list[GpifBeat] = []
    for bi, bar in enumerate(_findall(_find(score, "Bars"), "Bar")):
        track = _to_int(bar.get("track")) or 0
        tuning = tracks[track].tuning_midi if track < len(tracks) else []
        voices = _findall(bar, "Voices")
        for vhost in voices:
            for vi, voice in enumerate(_findall(vhost, "Voice")):
                t_beat = 0.0
                for beat_node in _findall(_find(voice, "Beats"), "Beat"):
                    dur = _beat_beats(beat_node, rhythms)
                    dynamic, chord, text = _beat_meta(beat_node)
                    beat = GpifBeat(track, bi, t_beat, dur, dynamic, chord, text, [])
                    for note in _findall(_find(beat_node, "Notes"), "Note"):
                        props = _find(note, "Properties")
                        if props is None:
                            props = note
                        string = _to_int(_text(_find(props, "String")))
                        fret = _to_int(_text(_find(props, "Fret")))
                        if string is None or fret is None:
                            continue
                        arts = _note_articulations(note)
                        palm = ("palm_mute" in arts
                                or _find(note, "PalmMute") is not None
                                or _find(props, "PalmMute") is not None)
                        if palm and "palm_mute" not in arts:
                            arts = sorted(set(arts) | {"palm_mute"})
                        dead, accent, hammer, slide = _note_flags(arts, note)
                        rich = GpifNote(track, bi, t_beat, string, fret, dur, palm,
                                        vi, _computed_midi(tuning, string, fret),
                                        dead, accent, hammer, slide, arts)
                        notes.append(rich)
                        beat.notes.append(rich)
                    beats.append(beat)
                    t_beat += dur
    tempo = next((m.tempo for m in masterbars if m.tempo), 120.0)
    return GpifScore(title, float(tempo), artist, album, tracks, masterbars, notes, beats)


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


def _bar_starts(score: GpifScore) -> list[float]:
    """Unexpanded quarter-note beat position where each masterbar starts."""
    starts: list[float] = []
    beat = 0.0
    for mb in score.masterbars:
        starts.append(beat)
        beat += mb.time_n * 4.0 / mb.time_d
    return starts


def duration_sec(score: GpifScore) -> float:
    """Notated length in seconds over the expanded playback. Uses
    `tempo_map` when present, else each masterbar's own tempo (score tempo,
    then 120)."""
    starts = _bar_starts(score)
    tmap = tempo_map(score)
    total = 0.0
    for i in playback_bar_order(score):
        mb = score.masterbars[i]
        if tmap:
            bpm = score.tempo or 120.0
            for beat, value in tmap:
                if beat <= starts[i] + 1e-9:
                    bpm = value
                else:
                    break
        else:
            bpm = mb.tempo or score.tempo or 120.0
        total += (mb.time_n * 4.0 / mb.time_d) * 60.0 / max(bpm, 1.0)
    return total


def note_events(score: GpifScore) -> list[tuple[float, int | None, float, bool]]:
    """``(seconds, midi_or_None, duration_sec, palm_mute)`` per note in playback
    order (repeats expanded). ``seconds`` is always element ``[0]`` so the
    ``sync._gpif_events`` / ``gp_onset_times`` onset clock keeps working; the
    extra fields (midi, palm mute) are additions, not a replacement."""
    by_bar: dict = {}
    for n in score.notes:
        by_bar.setdefault(n.bar, []).append(n)
    events: list[tuple[float, int | None, float, bool]] = []
    t = 0.0
    for bi in playback_bar_order(score):
        mb = score.masterbars[bi]
        bpm = mb.tempo or score.tempo or 120.0
        beat_sec = 60.0 / max(bpm, 1.0)
        for n in by_bar.get(bi, []):
            events.append((t + n.t_beat * beat_sec, n.midi,
                           n.duration * beat_sec, bool(n.palm_mute)))
        t += (mb.time_n * 4.0 / mb.time_d) * beat_sec
    return events


def count_markers(score: GpifScore) -> int:
    return sum(1 for mb in score.masterbars if (mb.section or "").strip())


# --- maps -----------------------------------------------------------------
def tempo_map(score: GpifScore) -> list[tuple[float, float]]:
    """``(unexpanded beat, bpm)`` at each tempo change; score tempo when the
    masterbars carry none."""
    starts = _bar_starts(score)
    out: list[tuple[float, float]] = []
    last = None
    for i, mb in enumerate(score.masterbars):
        bpm = mb.tempo
        if bpm is not None and bpm != last:
            out.append((round(starts[i], 4), float(bpm)))
            last = bpm
    if not out and score.tempo:
        out.append((0.0, float(score.tempo)))
    return out


def time_sig_map(score: GpifScore) -> list[tuple[int, int, int]]:
    """``(bar_index, numerator, denominator)`` at each time-signature change."""
    out: list[tuple[int, int, int]] = []
    last = None
    for i, mb in enumerate(score.masterbars):
        sig = (mb.time_n, mb.time_d)
        if sig != last:
            out.append((i, mb.time_n, mb.time_d))
            last = sig
    return out


def section_list(score: GpifScore) -> list[tuple[int, str]]:
    """``(bar_index, text)`` for every masterbar that carries a section."""
    return [(i, mb.section.strip()) for i, mb in enumerate(score.masterbars)
            if (mb.section or "").strip()]
