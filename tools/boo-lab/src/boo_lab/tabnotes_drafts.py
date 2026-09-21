"""Tab-notes pack -> unheard draft boxes + meter/tempo cut hints.

Two pack-utilization features, both gated on the song's own `data/sync.jsonl`
row being `sync_ok` (never emit when the clock is false/missing):

1. **Density drafts** -- high guitar-onset-density spans as unheard `riff`
   drafts and drum-onset half-time/kick shifts as unheard `breakdown` drafts,
   all on the pack's own AUDIO clock. Written to `data/drafts.jsonl` with
   `source="tabnotes-density"`, replacing only prior same-source rows for the
   songs rebuilt; `sections.jsonl` is never written and `heard` is always
   false. `guess.estimate_hybrid` also merges the riff spans read-only.

2. **Meter/tempo cuts** -- measure boundaries where the pack's time signature
   changes or its tempo automation jumps (a GP7 GPIF `tempo_map`/`time_sig_map`
   when there is no pack). Guess surfaces them as a note and snaps its
   audio-derived/density edges to them; no boxes are invented.

Machines draft, humans label.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import tabnotes

SOURCE_DENSITY = "tabnotes-density"
SOURCE_STRUCTURE = "tabnotes-structure"
AUDIO_SOURCES = frozenset({"halftime", "kick", "kick-notation", "blast-hint",
                           SOURCE_DENSITY, SOURCE_STRUCTURE})


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _sync_ok(lab_root, album: str, track: str) -> bool:
    """This song's `sync_ok` witness; `False` when the row is missing/false."""
    path = Path(lab_root) / "data" / "sync.jsonl"
    if not path.exists():
        return False
    for rec in _read_jsonl(path):
        if (rec.get("track") or "") != (track or ""):
            continue
        if album and (rec.get("album") or "") != album:
            continue
        return rec.get("sync_ok") is True
    return False


# --- density spans --------------------------------------------------------
def _dense_spans(times: list[float], *, min_len: float = 1.0,
                 win: float = 1.0, factor: float = 1.5) -> list[tuple[float, float]]:
    """Maximal spans where the local onset rate over a `win`-second window is
    at least `factor` times the song's average rate -- a dense chug run reads
    as one span. `times` must be sorted seconds; `[]` for too few onsets."""
    n = len(times)
    if n < 12:
        return []
    span = times[-1] - times[0]
    if span <= 0:
        return []
    global_rate = n / span
    threshold = max(3.0, factor * global_rate * win)
    flags = []
    j = 0
    for i in range(n):
        if j < i:
            j = i
        while j + 1 < n and times[j + 1] - times[i] < win:
            j += 1
        flags.append((j - i + 1) >= threshold)
    out: list[tuple[float, float]] = []
    i = 0
    while i < n:
        if not flags[i]:
            i += 1
            continue
        k = i
        while k < n and flags[k]:
            k += 1
        start = times[i]
        end = times[min(k, n) - 1]
        if end - start >= min_len:
            out.append((round(start, 3), round(end, 3)))
        i = k
    return out


def riff_density_spans(pack, *, min_span: float = 1.0) -> list[tuple[float, float]]:
    """High-density guitar-onset spans (audio clock), `(start, end)` seconds."""
    times = tabnotes.onsets_audio(pack, category="guitar")
    if not times:
        return []
    return _dense_spans(times, min_len=min_span)


def drum_breakdown_spans(pack) -> list[tuple[float, float]]:
    """Half-time / kick-density shifts from the pack's own drum onsets, reusing
    Guess's `_half_time_spans` (GM kick pitch 36 preferred, else all drums)."""
    from .guess import _half_time_spans

    kick = sorted(pack.audio_sec(e) for e in tabnotes.events_for(pack, category="drums")
                  if getattr(e, "pitch", None) == 36)
    times = kick if len(kick) >= 24 else tabnotes.onsets_audio(pack, category="drums")
    return [(round(s["start"], 3), round(s["end"], 3))
            for s in _half_time_spans(times, min_len=5.0)]


def _merge_spans(spans: list[dict], gap: float = 0.0) -> list[dict]:
    """Merge overlapping/adjacent spans of the same role (caps rows)."""
    by_role: dict[str, list[dict]] = {}
    for s in spans:
        by_role.setdefault(s["role"], []).append(s)
    out: list[dict] = []
    for role, group in by_role.items():
        group.sort(key=lambda x: (x["start"], x["end"]))
        cur: dict | None = None
        for s in group:
            if cur is None:
                cur = dict(s)
                continue
            if s["start"] <= cur["end"] + gap:
                cur["end"] = max(cur["end"], s["end"])
            else:
                out.append(cur)
                cur = dict(s)
        if cur is not None:
            out.append(cur)
    out.sort(key=lambda x: (x["start"], x["end"], x["role"]))
    return out


def pack_density_drafts(pack, *, roles=("riff", "breakdown"),
                        min_span: float = 1.0) -> list[dict]:
    """Role/start/end spans from one pack (no sync check, no stamping)."""
    rows: list[dict] = []
    if "riff" in roles:
        rows.extend({"role": "riff", "start": s, "end": e}
                    for s, e in riff_density_spans(pack, min_span=min_span))
    if "breakdown" in roles:
        rows.extend({"role": "breakdown", "start": s, "end": e}
                    for s, e in drum_breakdown_spans(pack))
    return _merge_spans(rows)


def density_drafts_for_song(lab_root, album: str, track: str, *,
                            roles=("riff", "breakdown"),
                            min_span: float = 1.0) -> list[dict]:
    """Stamped unheard density drafts for one song, or `[]` unless the pack is
    found AND the song's `sync_ok` is true. Never raises."""
    if not _sync_ok(lab_root, album, track):
        return []
    try:
        pack_path = tabnotes.discover_pack(lab_root, album, track)
        if pack_path is None:
            return []
        pack = tabnotes.load_pack(pack_path)
        spans = pack_density_drafts(pack, roles=roles, min_span=min_span)
    except Exception:
        return []
    from .schema import stamp_box

    return [
        stamp_box(s["start"], s["end"], s["role"], source=SOURCE_DENSITY,
                  heard=False,
                  extra={"album": album, "track": track, "kind": "density"})
        for s in spans
    ]


# --- pack structure spine -------------------------------------------------
def _letter(i: int) -> str:
    """`A`, `B`, ... `Z`, `AA`, `AB` for a 0-based index (figure suffix)."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def pack_structure_spans(pack, *, min_span: float = 1.0) -> list[dict]:
    """The pack's own structure spine: high guitar-onset-density phrases as
    `role=riff` boxes, each with a simple order-assigned `riff-A` / `riff-B` /
    `riff-C` id. A pack has no GP section letters, so none are invented; only
    the role the real note density supports is used. No stamping, no sync
    check -- `structure_drafts_for_song` gates and stamps. `[]` when the pack
    yields no phrase."""
    return [
        {"role": "riff", "start": s, "end": e, "figure_id": "riff-%s" % _letter(i)}
        for i, (s, e) in enumerate(riff_density_spans(pack, min_span=min_span))
    ]


def structure_drafts_for_song(lab_root, album: str, track: str, *,
                              min_span: float = 1.0) -> list[dict]:
    """Stamped unheard pack-spine drafts for one song, or `[]` unless the pack
    is found AND the song's `sync_ok` is true. It is the spine the same way
    `gp-marker` is, just without a GP. Never raises, never a keeper."""
    if not _sync_ok(lab_root, album, track):
        return []
    try:
        pack_path = tabnotes.discover_pack(lab_root, album, track)
        if pack_path is None:
            return []
        pack = tabnotes.load_pack(pack_path)
        spans = pack_structure_spans(pack, min_span=min_span)
    except Exception:
        return []
    from .schema import stamp_box

    return [
        stamp_box(s["start"], s["end"], s["role"], source=SOURCE_STRUCTURE,
                  figure_id=s["figure_id"], heard=False,
                  extra={"album": album, "track": track, "kind": "structure"})
        for s in spans
    ]


def build_density_drafts(lab_root, rows, *, album: str | None = None,
                         track: str | None = None) -> dict:
    """Merge `source=tabnotes-density` drafts into `data/drafts.jsonl`,
    replacing only prior same-source rows for the songs rebuilt. A run that
    yields zero rows leaves the file untouched. Never writes keepers."""
    from .schema import write_jsonl_atomic

    lab_root = Path(lab_root)
    out = lab_root / "data" / "drafts.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    if album and track:
        try:
            from .catalogue import resolve_row

            row = resolve_row(list(rows), album, track)
            if row is not None:
                album = row.get("album") or album
                track = row.get("track") or track
        except Exception:
            pass
    akey = album.casefold() if album else None
    tkey = track.casefold() if track else None

    produced: list[dict] = []
    rebuilt: set[tuple[str, str]] = set()
    songs = 0
    skipped = 0
    for r in rows:
        ra = r.get("album") or ""
        rt = r.get("track") or ""
        if akey is not None and ra.casefold() != akey:
            continue
        if tkey is not None and rt.casefold() != tkey:
            continue
        drafts = density_drafts_for_song(lab_root, ra, rt)
        if drafts:
            produced.extend(drafts)
            rebuilt.add((ra, rt))
            songs += 1
            print("TABNOTES-DRAFTS", rt, len(drafts), "box(es)")
        else:
            skipped += 1

    if not produced:
        print("tabnotes-drafts: 0 rows written; leaving", out.name, "untouched")
        return {"songs": songs, "written": 0, "skipped": skipped, "out": str(out)}

    keep = [x for x in _read_jsonl(out)
            if not ((x.get("album") or "", x.get("track") or "") in rebuilt
                    and x.get("source") == SOURCE_DENSITY)]
    write_jsonl_atomic(out, keep + produced)
    return {"songs": songs, "written": len(produced), "skipped": skipped,
            "out": str(out)}


# --- meter / tempo cuts ---------------------------------------------------
def meter_cuts(pack) -> list[float]:
    """Audio-clock seconds at every measure boundary where the pack's time
    signature changes or its tempo automation jumps. `[]` when neither."""
    cuts: set[float] = set()
    prev_sig = None
    for m in sorted(pack.measures, key=lambda x: x.measure):
        sig = m.time_signature
        if prev_sig is not None and sig and prev_sig and sig != prev_sig:
            sec = (m.start_sec_audio if m.start_sec_audio is not None
                   else (m.start_ms or 0.0) / 1000.0)
            cuts.add(round(float(sec), 3))
        if sig:
            prev_sig = sig
    for sec, _bpm in tabnotes.tempo_map(pack)[1:]:
        cuts.add(round(float(sec), 3))
    return sorted(cuts)


def _gpif_meter_cuts(gp_path) -> list[float]:
    """`meter_cuts` twin for a GP7/GP6 score: time-sig changes + tempo jumps
    mapped to unexpanded bar-start seconds."""
    from .gpif import _bar_starts, load_score, tempo_map as _tm, time_sig_map

    score = load_score(gp_path)
    starts = _bar_starts(score)
    tmap = _tm(score)
    secs: list[float] = []
    t = 0.0
    for i, mb in enumerate(score.masterbars):
        bpm = score.tempo or 120.0
        for beat, value in tmap:
            if beat <= starts[i] + 1e-9:
                bpm = value
            else:
                break
        secs.append(t)
        t += (mb.time_n * 4.0 / mb.time_d) * 60.0 / max(bpm, 1.0)
    cuts: set[float] = set()
    for bar, _n, _d in time_sig_map(score)[1:]:
        if 0 <= bar < len(secs):
            cuts.add(round(secs[bar], 3))
    for beat, _bpm in tmap[1:]:
        for i, s in enumerate(starts):
            if abs(s - beat) < 1e-6 and i < len(secs):
                cuts.add(round(secs[i], 3))
                break
    return sorted(cuts)


def meter_cuts_for_song(lab_root, album: str, track: str, *,
                        gp_path=None) -> list[float]:
    """Meter/tempo cut seconds for one song: a pack when found, else a GP7
    GPIF score. `[]` unless the song's `sync_ok` is true. Never raises."""
    if not _sync_ok(lab_root, album, track):
        return []
    try:
        pack_path = tabnotes.discover_pack(lab_root, album, track)
    except Exception:
        pack_path = None
    if pack_path is not None:
        try:
            return meter_cuts(tabnotes.load_pack(pack_path))
        except Exception:
            pass
    if gp_path is not None:
        p = Path(gp_path)
        if p.suffix.lower() in (".gp", ".gpx"):
            try:
                return _gpif_meter_cuts(p)
            except Exception:
                return []
    return []


def snap_sections_to_cuts(sections: list[dict], cuts: list[float], *,
                          tol: float = 0.75, sources=None) -> int:
    """Snap audio-derived/density section edges to the nearest cut within
    `tol` seconds. Markers and model drafts are never touched. Returns count."""
    if not cuts:
        return 0
    want = AUDIO_SOURCES if sources is None else set(sources)
    snapped = 0
    for s in sections:
        if s.get("source") not in want:
            continue
        for key in ("start", "end"):
            try:
                v = float(s[key])
            except (KeyError, TypeError, ValueError):
                continue
            best = min(cuts, key=lambda c: abs(c - v))
            if 1e-6 < abs(best - v) <= tol:
                s[key] = round(best, 3)
                snapped += 1
    return snapped
