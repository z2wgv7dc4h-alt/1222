"""Tab-notes pack reader -- a local multi-track score (notes + timeline + raw).

No HTTP, no Songsterr; the operator pastes a local zip or folder. A pack is::

    <id>/manifest.json
    <id>/notes.json            # format tab-notes/1 (flat events)
    <id>/timeline.json         # measures + the AUDIO clock
    <id>/raw/song.json         # tracks (tuning/capo/volume/automations)
    <id>/raw/video_points.json
    <id>/raw/parts/N.json      # raw beats/notes (tuplets, bends)

`load_pack` accepts the `.zip`, the unpacked folder, or a `notes.json` and never
requires the user to unzip. When both `notes.json`/`timeline.json` and `raw/`
exist, both are parsed. Machines never write `sections.jsonl`; this module only
reads a pack and (via the CLI) appends a local index.
"""
from __future__ import annotations

import json
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

PACK_FORMAT = "tab-notes/1"


# --- tiny coercion helpers ------------------------------------------------
def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, tuple):
        return list(v)
    return [v]


def _str(v):
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _float(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int_list(v):
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        out = [_int(x) for x in v]
        return [x for x in out if x is not None] or None
    if isinstance(v, str):
        out = [_int(x) for x in v.split() if x.lstrip("-").isdigit()]
        return out or None
    return None


def _norm(s):
    """A title/stem without a track-number prefix or punctuation, so
    `07 - Bow Down` and `Bow Down` compare equal (same rule as sync)."""
    s = re.sub(r"^\d+[\s._-]+", "", s or "")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _json(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# --- model ----------------------------------------------------------------
@dataclass
class TabTrack:
    index: int
    part_id: int | None = None
    name: str = ""
    instrument_name: str = ""
    category: str = ""
    tuning: list[int] | None = None
    capo: int | None = None
    strings: int | None = None
    is_percussion: bool = False
    volume: float | None = None
    balance: float | None = None
    automations_tempo: list[dict] = field(default_factory=list)


@dataclass
class TabEvent:
    track: int
    part_id: int | None = None
    track_name: str = ""
    instrument_id: int | None = None
    instrument_name: str = ""
    category: str = ""
    is_percussion: bool = False
    measure: int = 0
    voice: int = 0
    beat: int = 0
    onset_beat: float = 0.0
    onset_ms: float = 0.0
    duration_beats: float = 0.0
    duration_ms: float = 0.0
    tempo_bpm: float | None = None
    time_signature: str | None = None
    key_signature: str | None = None
    pitch: int | None = None
    string: int | None = None
    fret: int | None = None
    capo: int | None = None
    velocity: float | None = None
    dynamic: str | None = None
    palm_mute: bool = False
    dead: bool = False
    ghost: bool = False
    hammer: bool = False
    slide: str | None = None
    harmonic: bool = False
    bend: bool = False
    tie: bool = False


@dataclass
class TabRawNote:
    string: int | None = None
    fret: int | None = None
    rest: bool = False
    hp: str | None = None
    slide: str | None = None
    harmonic: bool = False
    bend_points: list[dict] | None = None


@dataclass
class TabRawBeat:
    type: str = ""
    duration: list[int] | None = None
    dotted: bool = False
    rest: bool = False
    tuplet: dict | None = None
    tuplet_start: bool = False
    tuplet_stop: bool = False
    velocity: float | None = None
    tempo: float | None = None
    notes: list[TabRawNote] = field(default_factory=list)
    measure: int = 0
    part_id: int | None = None
    audio_sec: float | None = None


@dataclass
class TabMeasure:
    measure: int
    start_ms: float = 0.0
    start_sec_audio: float | None = None
    duration_ms: float = 0.0
    audio_duration_sec: float | None = None
    tempo_bpm: float | None = None
    time_signature: str | None = None
    length_beats: float | None = None
    video_sec: float | None = None


@dataclass
class TabNotesPack:
    id: str = ""
    title: str = ""
    artist: str = ""
    source_path: str = ""
    tracks: list[TabTrack] = field(default_factory=list)
    events: list[TabEvent] = field(default_factory=list)
    measures: list[TabMeasure] = field(default_factory=list)
    raw_beats: list[TabRawBeat] = field(default_factory=list)
    audio_total_sec: float = 0.0
    notated_total_ms: float = 0.0
    clock_ratio: float = 1.0
    video_points: list[float] = field(default_factory=list)

    def measure(self, index) -> TabMeasure | None:
        for m in self.measures:
            if m.measure == index:
                return m
        return None

    def audio_sec(self, event) -> float:
        """The event's time on the AUDIO clock. Timeline first; then
        `video_points[measure]` + in-bar; else the raw `onset_ms`."""
        m = _int(getattr(event, "measure", 0), 0)
        ms = _float(getattr(event, "onset_ms", 0.0), 0.0) or 0.0
        meas = self.measure(m)
        if meas is not None and meas.start_sec_audio is not None:
            return meas.start_sec_audio + (ms - (meas.start_ms or 0.0)) / 1000.0
        if self.video_points and 0 <= m < len(self.video_points):
            in_bar = (ms - (meas.start_ms or 0.0)) / 1000.0 if meas is not None else 0.0
            return float(self.video_points[m]) + in_bar
        return ms / 1000.0


# --- sources --------------------------------------------------------------
class _ZipSrc:
    def __init__(self, zf: zipfile.ZipFile, prefix: str):
        self.z = zf
        self.prefix = prefix

    def read(self, rel):
        try:
            return self.z.read(self.prefix + rel).decode("utf-8", "replace")
        except KeyError:
            return None

    def part_files(self):
        out = []
        for name in self.z.namelist():
            if not name.startswith(self.prefix + "raw/parts/") or not name.endswith(".json"):
                continue
            base = name[len(self.prefix):]
            pid = _int(Path(base).stem)
            if pid is not None:
                out.append((pid, base))
        return sorted(out)


class _DirSrc:
    def __init__(self, root: Path):
        self.root = Path(root)

    def read(self, rel):
        p = self.root / rel
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None

    def part_files(self):
        d = self.root / "raw" / "parts"
        if not d.is_dir():
            return []
        out = []
        for p in d.glob("*.json"):
            pid = _int(p.stem)
            if pid is not None:
                out.append((pid, str(p.relative_to(self.root))))
        return sorted(out)


def _zip_prefix(zf: zipfile.ZipFile) -> str | None:
    cands = [n for n in zf.namelist() if n.replace("\\", "/").endswith("notes.json")]
    if not cands:
        return None
    best = min(cands, key=lambda n: n.count("/"))
    return best[: len(best) - len("notes.json")]


def _find_pack_root_dir(path: Path) -> Path:
    if (path / "notes.json").exists() or (path / "manifest.json").exists():
        return path
    for d in sorted(path.iterdir()):
        if d.is_dir() and ((d / "notes.json").exists() or (d / "manifest.json").exists()):
            return d
    return path


def load_pack(path) -> TabNotesPack:
    """Load a `.zip`, an unpacked folder, or a `notes.json`."""
    path = Path(path)
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            prefix = _zip_prefix(zf)
            if prefix is None:
                raise ValueError("not a tab-notes pack: no notes.json in %s" % path)
            pid = prefix.strip("/").split("/")[-1] if prefix.strip("/") else path.stem
            return _load(_ZipSrc(zf, prefix), str(path), pid)
    if path.is_file() and path.name.lower() == "notes.json":
        return _load(_DirSrc(path.parent), str(path), path.parent.name)
    if path.is_dir():
        root = _find_pack_root_dir(path)
        return _load(_DirSrc(root), str(path), root.name)
    raise FileNotFoundError(str(path))


def read_manifest(path) -> dict:
    """Cheap title/artist/id read for discovery (no full pack parse).

    Songsterr packs often ship a thin `manifest.json` (files + event_count only).
    Fall back to `notes.json` for title/artist/id so discover_pack can match
    map rows after ingest.
    """
    path = Path(path)

    def _enrich(man: dict, src) -> dict:
        man = dict(man or {})
        if man.get("title") and man.get("artist") and man.get("id"):
            return man
        try:
            notes = _json(src.read("notes.json")) or {}
        except Exception:
            notes = {}
        for k in ("title", "artist", "id", "format", "event_count"):
            if not man.get(k) and notes.get(k) is not None:
                man[k] = notes[k]
        return man

    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            prefix = _zip_prefix(zf)
            if prefix is None:
                return {}
            src = _ZipSrc(zf, prefix)
            return _enrich(_json(src.read("manifest.json")) or {}, src)
    if path.is_dir():
        root = _find_pack_root_dir(path)
        src = _DirSrc(root)
        return _enrich(_json(src.read("manifest.json")) or {}, src)
    return {}


# --- builder --------------------------------------------------------------
def _parse_events(raw):
    events = []
    for e in _as_list(raw):
        if not isinstance(e, dict):
            continue
        events.append(TabEvent(
            track=_int(e.get("track"), 0) or 0,
            part_id=_int(e.get("part_id")),
            track_name=_str(e.get("track_name")),
            instrument_id=_int(e.get("instrument_id")),
            instrument_name=_str(e.get("instrument_name")),
            category=_str(e.get("category")),
            is_percussion=bool(e.get("is_percussion")),
            measure=_int(e.get("measure"), 0) or 0,
            voice=_int(e.get("voice"), 0) or 0,
            beat=_int(e.get("beat"), 0) or 0,
            onset_beat=_float(e.get("onset_beat"), 0.0) or 0.0,
            onset_ms=_float(e.get("onset_ms"), 0.0) or 0.0,
            duration_beats=_float(e.get("duration_beats"), 0.0) or 0.0,
            duration_ms=_float(e.get("duration_ms"), 0.0) or 0.0,
            tempo_bpm=_float(e.get("tempo_bpm")),
            time_signature=_str(e.get("time_signature")) or None,
            key_signature=_str(e.get("key_signature")) or None,
            pitch=_int(e.get("pitch")),
            string=_int(e.get("string")),
            fret=_int(e.get("fret")),
            capo=_int(e.get("capo")),
            velocity=_float(e.get("velocity")),
            dynamic=_str(e.get("dynamic")) or None,
            palm_mute=bool(e.get("palm_mute")),
            dead=bool(e.get("dead")),
            ghost=bool(e.get("ghost")),
            hammer=bool(e.get("hammer")),
            slide=(_str(e.get("slide")) or None) if e.get("slide") else None,
            harmonic=bool(e.get("harmonic")),
            bend=bool(e.get("bend")),
            tie=bool(e.get("tie")),
        ))
    return events


def _tempo_automations(track: dict) -> list[dict]:
    out = []
    for a in _as_list(track.get("automations") or track.get("tempoAutomations")
                      or track.get("tempo_automations")):
        if not isinstance(a, dict):
            continue
        typ = (_str(a.get("type")) + _str(a.get("name"))).lower()
        bpm = _float(a.get("bpm"), _float(a.get("value")))
        if "tempo" not in typ and bpm is None:
            continue
        out.append({
            "measure": _int(a.get("measure"), 0) or 0,
            "bpm": bpm,
            "position": _float(a.get("position"), 0.0) or 0.0,
            "linear": bool(a.get("linear")),
        })
    return out


def _parse_tracks(song, events) -> list[TabTrack]:
    raw = _as_list(song.get("tracks") if isinstance(song, dict) else None)
    tracks = []
    for i, t in enumerate(raw):
        if not isinstance(t, dict):
            continue
        cat = _str(t.get("category") or t.get("type"))
        tracks.append(TabTrack(
            index=_int(t.get("index"), i) if _int(t.get("index"), i) is not None else i,
            part_id=_int(t.get("partId"), _int(t.get("part_id"), i)),
            name=_str(t.get("name") or t.get("trackName")),
            instrument_name=_str(t.get("instrumentName") or t.get("instrument_name")),
            category=cat,
            tuning=_int_list(t.get("tuning") or t.get("tuningMidi") or t.get("pitches")),
            capo=_int(t.get("capo")),
            strings=_int(t.get("strings") or t.get("stringCount")),
            is_percussion=bool(t.get("isPercussion") or t.get("is_percussion")
                               or cat.lower() in ("drums", "percussion")),
            volume=_float(t.get("volume")),
            balance=_float(t.get("balance")),
            automations_tempo=_tempo_automations(t),
        ))
    if tracks:
        return tracks
    # Synthesize from events when raw/song.json has no tracks.
    seen: dict[int, TabTrack] = {}
    for e in events:
        if e.track in seen:
            continue
        seen[e.track] = TabTrack(
            index=e.track, part_id=e.part_id, name=e.track_name,
            instrument_name=e.instrument_name, category=e.category,
            is_percussion=e.is_percussion)
    return [seen[k] for k in sorted(seen)]


def _parse_measures(timeline) -> list[TabMeasure]:
    raw = timeline.get("measures") if isinstance(timeline, dict) else timeline
    measures = []
    for i, m in enumerate(_as_list(raw)):
        if not isinstance(m, dict):
            continue
        measures.append(TabMeasure(
            measure=_int(m.get("measure"), i) if _int(m.get("measure"), i) is not None else i,
            start_ms=_float(m.get("start_ms"), 0.0) or 0.0,
            start_sec_audio=_float(m.get("start_sec_audio")),
            duration_ms=_float(m.get("duration_ms"), 0.0) or 0.0,
            audio_duration_sec=_float(m.get("audio_duration_sec")),
            tempo_bpm=_float(m.get("tempo_bpm")),
            time_signature=_str(m.get("time_signature")) or None,
            length_beats=_float(m.get("length_beats")),
        ))
    return measures


def _parse_video_points(vp) -> list[float]:
    if isinstance(vp, dict):
        vp = vp.get("points") or vp.get("video_points")
    out = []
    for x in _as_list(vp):
        v = _float(x)
        if v is not None:
            out.append(v)
    return out


def _parse_raw_beats(parts, measures) -> list[TabRawBeat]:
    by_meas = {m.measure: m for m in measures}
    beats: list[TabRawBeat] = []
    for pid, obj in parts:
        if obj is None:
            continue
        raw = obj.get("measures") if isinstance(obj, dict) else obj
        for mi, m in enumerate(_as_list(raw)):
            if not isinstance(m, dict):
                continue
            measure_index = _int(m.get("measure"), mi)
            measure_index = mi if measure_index is None else measure_index
            base_sec = None
            meas = by_meas.get(measure_index)
            if meas is not None and meas.start_sec_audio is not None:
                base_sec = meas.start_sec_audio
            in_bar_quarters = 0.0
            for b in _as_list(m.get("beats")):
                if not isinstance(b, dict):
                    continue
                tempo = _float(b.get("tempo"), meas.tempo_bpm if meas else None) or 120.0
                beat = TabRawBeat(
                    type=_str(b.get("type")),
                    duration=_int_list(b.get("duration")),
                    dotted=bool(b.get("dotted")),
                    rest=bool(b.get("rest")),
                    tuplet=b.get("tuplet") if isinstance(b.get("tuplet"), dict) else None,
                    tuplet_start=bool(b.get("tuplet_start")),
                    tuplet_stop=bool(b.get("tuplet_stop")),
                    velocity=_float(b.get("velocity")),
                    tempo=_float(b.get("tempo")),
                    measure=measure_index,
                    part_id=pid,
                )
                for n in _as_list(b.get("notes")):
                    if not isinstance(n, dict):
                        continue
                    bp = n.get("bend_points")
                    beat.notes.append(TabRawNote(
                        string=_int(n.get("string")),
                        fret=_int(n.get("fret")),
                        rest=bool(n.get("rest")),
                        hp=(_str(n.get("hp")) or None) if n.get("hp") else None,
                        slide=(_str(n.get("slide")) or None) if n.get("slide") else None,
                        harmonic=bool(n.get("harmonic")),
                        bend_points=bp if isinstance(bp, list) else None,
                    ))
                if base_sec is not None:
                    beat.audio_sec = base_sec + in_bar_quarters * 60.0 / max(tempo, 1.0)
                d = beat.duration
                if d and len(d) >= 2 and d[1]:
                    in_bar_quarters += (d[0] / d[1]) * 4.0
                beats.append(beat)
    return beats


def _load(src, source_path: str, pack_id: str) -> TabNotesPack:
    manifest = _json(src.read("manifest.json")) or {}
    notes = _json(src.read("notes.json")) or {}
    timeline = _json(src.read("timeline.json")) or {}
    song = _json(src.read("raw/song.json")) or {}
    video_points = _parse_video_points(_json(src.read("raw/video_points.json")))
    parts = [(pid, _json(src.read(rel))) for pid, rel in src.part_files()]

    raw_events = notes.get("events") if isinstance(notes, dict) else notes
    events = _parse_events(raw_events)
    tracks = _parse_tracks(song, events)
    measures = _parse_measures(timeline)
    if video_points:
        for i, m in enumerate(measures):
            if i < len(video_points):
                m.video_sec = float(video_points[i])
    raw_beats = _parse_raw_beats(parts, measures)

    pack = TabNotesPack(
        id=_str(manifest.get("id") or pack_id),
        title=_str(manifest.get("title") or notes.get("title") if isinstance(notes, dict) else ""),
        artist=_str(manifest.get("artist") or (notes.get("artist") if isinstance(notes, dict) else "")),
        source_path=source_path,
        tracks=tracks, events=events, measures=measures, raw_beats=raw_beats,
        video_points=video_points,
    )

    if measures:
        pack.notated_total_ms = max((m.start_ms + m.duration_ms) for m in measures)
        starts = [m.start_sec_audio for m in measures if m.start_sec_audio is not None]
        ends = [(m.start_sec_audio + (m.audio_duration_sec if m.audio_duration_sec is not None
                                      else m.duration_ms / 1000.0))
                for m in measures if m.start_sec_audio is not None]
        if starts and ends:
            pack.audio_total_sec = max(ends)
            notated_span = (pack.notated_total_ms - min(m.start_ms for m in measures)) / 1000.0
            if notated_span > 0:
                pack.clock_ratio = round((max(ends) - min(starts)) / notated_span, 6)
    else:
        pack.notated_total_ms = max((e.onset_ms + e.duration_ms) for e in events) if events else 0.0
        pack.audio_total_sec = max((pack.audio_sec(e) for e in events), default=0.0)
    return pack


# --- helpers --------------------------------------------------------------
def events_for(pack: TabNotesPack, category=None, track=None) -> list[TabEvent]:
    out = []
    for e in pack.events:
        if category is not None and (e.category or "") != category:
            continue
        if track is not None and e.track != track:
            continue
        out.append(e)
    return out


def onsets_audio(pack: TabNotesPack, category=None, track=None) -> list[float]:
    return sorted(pack.audio_sec(e) for e in events_for(pack, category, track))


def onsets_audio_by_track(pack: TabNotesPack) -> dict[int, list[float]]:
    out: dict[int, list[float]] = {}
    for e in pack.events:
        out.setdefault(e.track, []).append(pack.audio_sec(e))
    return {k: sorted(v) for k, v in out.items()}


def tempo_map(pack: TabNotesPack) -> list[tuple[float, float]]:
    """`(audio_sec, bpm)`; raw track automations win, else timeline measures."""
    out: list[tuple[float, float]] = []
    autos = [(t.index, a) for t in pack.tracks for a in t.automations_tempo if a.get("bpm")]
    if autos:
        for _ti, a in autos:
            meas = pack.measure(a.get("measure", 0))
            start_ms = meas.start_ms if meas is not None else 0.0
            sec = pack.audio_sec(type("E", (), {"measure": a.get("measure", 0), "onset_ms": start_ms})())
            out.append((sec, float(a["bpm"])))
    else:
        for m in pack.measures:
            if m.tempo_bpm is None:
                continue
            sec = m.start_sec_audio if m.start_sec_audio is not None else m.start_ms / 1000.0
            out.append((sec, float(m.tempo_bpm)))
    out.sort(key=lambda x: x[0])
    deduped: list[tuple[float, float]] = []
    for sec, bpm in out:
        if deduped and abs(deduped[-1][1] - bpm) < 1e-9:
            continue
        deduped.append((sec, bpm))
    return deduped


def tuning_of(pack: TabNotesPack, track) -> list[int] | None:
    for t in pack.tracks:
        if t.index == track:
            return t.tuning
    return None


def bar_events(pack: TabNotesPack, measure, track=None) -> list[TabEvent]:
    """Events in one bar. `measure` may be a measure number or a `TabMeasure`."""
    mnum = measure if isinstance(measure, int) else getattr(measure, "measure", measure)
    return [e for e in events_for(pack, track=track) if e.measure == mnum]


def _beats_per_bar(time_signature) -> float:
    """Quarter-note length of a bar from `4/4`, `(4, 4)`, or similar. Default 4."""
    if time_signature is None or time_signature == "":
        return 4.0
    if isinstance(time_signature, (tuple, list)) and len(time_signature) >= 2:
        try:
            num, den = int(time_signature[0]), int(time_signature[1])
            if den:
                return float(num) * (4.0 / float(den))
        except (TypeError, ValueError):
            return 4.0
        return 4.0
    s = str(time_signature).strip()
    if "/" in s:
        a, b = s.split("/", 1)
        try:
            num, den = int(a.strip()), int(b.strip())
            if den:
                return float(num) * (4.0 / float(den))
        except ValueError:
            return 4.0
    return 4.0


def _bar_start_beats(pack: TabNotesPack, measure_num: int) -> float:
    """Absolute beat index at the start of `measure_num`.

    Prefer cumulative `length_beats` on pack measures (handles meter changes).
    Else `measure_num * beats_per_bar` from that measure's time_signature.
    """
    measures = list(getattr(pack, "measures", None) or [])
    if measures and all(getattr(m, "length_beats", None) for m in measures):
        total = 0.0
        for m in sorted(measures, key=lambda x: int(getattr(x, "measure", 0))):
            mn = int(getattr(m, "measure", 0))
            if mn >= int(measure_num):
                return total
            total += float(getattr(m, "length_beats") or 0.0)
        return total
    by_num = {int(getattr(m, "measure", i)): m for i, m in enumerate(measures)}
    m = by_num.get(int(measure_num))
    bpb = _beats_per_bar(getattr(m, "time_signature", None) if m else None)
    return float(measure_num) * bpb


def _event_art(e) -> str:
    if getattr(e, "palm_mute", False):
        return "p"
    if getattr(e, "dead", False):
        return "d"
    if getattr(e, "hammer", False):
        return "h"
    return "-"


def bar_fp_tab(pack: TabNotesPack, measure, track_idx) -> str:
    """Bar fingerprint from in-bar onset + duration (16ths), full MIDI pitch,
    and articulation. Stable string, no role names.

    Format per chord slot: `pos:dur:pitches:arts` joined by `|`.
    Replaces the old pitch-class / eighths hash that collapsed 16ths to 0
    and made through-composed metal look identical bar-to-bar.
    """
    mnum = measure if isinstance(measure, int) else getattr(measure, "measure", measure)
    evs = sorted(
        bar_events(pack, measure, track=track_idx),
        key=lambda e: (e.onset_beat, e.string or 0, e.pitch if e.pitch is not None else -1),
    )
    if not evs:
        return ""
    bar_start = _bar_start_beats(pack, int(mnum))
    rels = [float(e.onset_beat or 0.0) - bar_start for e in evs]
    # If clock looks wrong (notes before bar), fall back to min-onset relative.
    if rels and min(rels) < -0.125:
        base = min(float(e.onset_beat or 0.0) for e in evs)
        rels = [float(e.onset_beat or 0.0) - base for e in evs]

    groups: dict[int, list] = {}
    for e, rel in zip(evs, rels):
        pos = int(round(rel * 4.0))
        if pos < 0:
            pos = 0
        groups.setdefault(pos, []).append(e)

    parts = []
    for pos in sorted(groups):
        pitch_art: dict[int, str] = {}
        max_dur = 1
        for e in groups[pos]:
            dur = max(1, int(round((e.duration_beats or 0.0) * 4.0)))
            if dur > max_dur:
                max_dur = dur
            if e.pitch is None:
                continue
            pit = int(e.pitch)
            if pit not in pitch_art:
                pitch_art[pit] = _event_art(e)
        if not pitch_art:
            parts.append("%d:%d:x:%s" % (pos, max_dur, _event_art(groups[pos][0])))
            continue
        pits = sorted(pitch_art)
        arts = ",".join(pitch_art[p] for p in pits)
        pitch_s = ",".join(str(p) for p in pits)
        parts.append("%d:%d:%s:%s" % (pos, max_dur, pitch_s, arts))
    return "|".join(parts)


# --- detection / unpack ---------------------------------------------------
def _notes_is_pack(text) -> bool:
    obj = _json(text)
    return isinstance(obj, dict) and str(obj.get("format", "")).strip() == PACK_FORMAT


def is_pack(path) -> bool:
    """`True` only for a real tab-notes pack: a directory whose `notes.json`
    is `format: tab-notes/1`, or a `.zip` containing such a `notes.json`
    (any folder prefix). A `.gp`/`.gp5`/FLAC zip is never a pack."""
    p = Path(path)
    if p.is_dir():
        n = p / "notes.json"
        return n.exists() and _notes_is_pack(n.read_text(encoding="utf-8", errors="replace"))
    if p.is_file() and p.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(p) as zf:
                prefix = _zip_prefix(zf)
                if prefix is None:
                    return False
                return _notes_is_pack(_ZipSrc(zf, prefix).read("notes.json"))
        except Exception:
            return False
    return False


def safe_id(name) -> str:
    """`<id>` for the data/tabnotes folder: lowercase alnum + underscore."""
    s = re.sub(r"[^a-z0-9]+", "_", _str(name).lower()).strip("_")
    return s or "pack"


def unpack_pack(src, dest) -> Path:
    """Unpack a pack `.zip` (stripping the `<id>/` prefix) or copy a pack
    folder's contents into `dest`, overwriting same-id files only. Other ids
    in `data/tabnotes/` are never touched, and nothing goes to the FLAC/GP
    roots."""
    src, dest = Path(src), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if src.is_file() and src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src) as zf:
            prefix = _zip_prefix(zf) or ""
            for name in zf.namelist():
                if name.endswith("/") or not name.startswith(prefix):
                    continue
                rel = name[len(prefix):]
                if not rel:
                    continue
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as f, target.open("wb") as out:
                    shutil.copyfileobj(f, out)
    elif src.is_dir():
        # Pack folders only — never pull sibling .zips / scratch unpack trees
        # that lived next to notes.json in a reused drop directory.
        skip_parts = {"_unpacked", "__MACOSX"}
        for p in src.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(src)
            if any(part in skip_parts for part in rel.parts):
                continue
            if p.suffix.lower() == ".zip":
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    return dest


# --- discovery + index ----------------------------------------------------
def _pack_candidates(lab_root):
    base = Path(lab_root) / "data" / "tabnotes"
    if not base.exists():
        return []
    out = list(base.rglob("*.zip"))
    for d in base.rglob("*"):
        if d.is_dir() and (d / "notes.json").exists():
            out.append(d)
    return sorted(out)


def discover_pack(lab_root, album=None, track=None):
    """Match a map row to a local pack under `data/tabnotes/**`.

    Requires a real *title* hit (exact or track contains pack title / vice
    versa). Artist-in-album is only a tie-break bonus — never enough alone,
    or every Born of Osiris album folder falsely badges Mindful.
    """
    want = _norm(track)
    album_n = _norm(album)
    best = None
    for cand in _pack_candidates(lab_root):
        try:
            man = read_manifest(cand)
        except Exception:
            continue
        title = _norm(man.get("title"))
        artist = _norm(man.get("artist"))
        title_score = 0
        if title and want and title == want:
            title_score = 2
        elif title and want and len(title) >= 4 and (title in want or want in title):
            title_score = 1
        if not title_score:
            continue
        score = title_score
        if artist and album_n and (artist in album_n or album_n in artist):
            score += 1
        if best is None or score > best[0]:
            best = (score, cand)
    return best[1] if best else None


def pack_to_dict(pack: TabNotesPack) -> dict:
    from dataclasses import asdict

    return asdict(pack)


def append_index(lab_root, pack: TabNotesPack) -> Path:
    """Upsert one row (by pack id) into `data/tabnotes_index.jsonl`. Never
    touches `sections.jsonl` or `map.csv`."""
    from .schema import write_jsonl_atomic

    path = Path(lab_root) / "data" / "tabnotes_index.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "id": pack.id, "title": pack.title, "artist": pack.artist,
        "source_path": pack.source_path, "tracks": len(pack.tracks),
        "events": len(pack.events), "measures": len(pack.measures),
        "raw_beats": len(pack.raw_beats), "clock_ratio": pack.clock_ratio,
    }
    kept = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec["id"] and obj.get("id") == rec["id"]:
                continue
            kept.append(obj)
    kept.append(rec)
    write_jsonl_atomic(path, kept, ensure_ascii=False)
    return path
