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
SOURCE_PHRASE = "tabnotes-phrase"
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


def _measure_audio_end(m) -> float:
    """Audio-clock end of a TabMeasure (seconds)."""
    start = float(getattr(m, "start_sec_audio", 0.0) or 0.0)
    dur = getattr(m, "audio_duration_sec", None)
    if dur is None or float(dur) <= 0:
        ms = float(getattr(m, "duration_ms", 0.0) or 0.0)
        dur = ms / 1000.0 if ms > 0 else 0.0
    return start + float(dur)


def _guitar_onset_spans_from_measures(
    pack, times: list[float], *, min_span: float = 2.0, gap_split: float = 1.5,
) -> list[tuple[float, float]]:
    """Full-song riff runs from per-measure guitar activity.

    Peak-relative density (`_dense_spans`) starves quieter openings when a
    later section is denser (Mindful: 621 early onsets, zero spine boxes until
    ~1:24). Measure activity covers every bar that actually has guitar, then
    splits on silence gaps or sharp density changes so Guess gets a continuous
    spine instead of three late crumbs.
    """
    import bisect
    import statistics

    measures = list(getattr(pack, "measures", None) or [])
    if len(measures) < 4 or len(times) < 8:
        return []

    rows: list[tuple[float, float, int, float]] = []
    for m in measures:
        a = float(getattr(m, "start_sec_audio", 0.0) or 0.0)
        b = _measure_audio_end(m)
        if b <= a:
            continue
        lo = bisect.bisect_left(times, a)
        hi = bisect.bisect_left(times, b)
        n = hi - lo
        if n < 2:
            continue
        rows.append((a, b, n, n / (b - a)))
    if not rows:
        return []

    rates = [r for *_, r in rows]
    med = statistics.median(rates) if rates else 0.0

    segs: list[list[tuple[float, float, int, float]]] = [[rows[0]]]
    for prev, cur in zip(rows, rows[1:]):
        gap = cur[0] - prev[1]
        r0, r1 = prev[3], cur[3]
        split = gap > gap_split or (
            abs(r1 - r0) > max(med * 0.9, 4.0) and min(r0, r1) < med * 0.7
        )
        if split:
            segs.append([cur])
        else:
            segs[-1].append(cur)

    out: list[tuple[float, float]] = []
    for seg in segs:
        start, end = seg[0][0], seg[-1][1]
        if end - start >= min_span:
            out.append((round(start, 3), round(end, 3)))
    return out


def _guitar_onset_spans_from_windows(
    times: list[float], *, min_span: float = 2.0, win: float = 2.0,
    min_onsets: int = 3, merge_gap: float = 2.0, valley_ratio: float = 0.45,
) -> list[tuple[float, float]]:
    """Fallback spine when the pack has no usable measure grid: cover active
    guitar time, then split on density valleys so one blob is not the whole song.
    """
    import bisect
    import statistics

    if len(times) < 8:
        return []
    t0, t1 = float(times[0]), float(times[-1])
    if t1 <= t0:
        return []
    step = 0.25
    samples: list[tuple[float, int]] = []
    t = t0
    while t < t1:
        lo = bisect.bisect_left(times, t)
        hi = bisect.bisect_left(times, t + win)
        samples.append((t, hi - lo))
        t += step
    if not samples:
        return []
    counts = [c for _, c in samples]
    med = statistics.median(counts) if counts else 0.0
    floor = max(min_onsets, int(med * valley_ratio) if med else min_onsets)

    raw: list[list[float]] = []
    cur: list[float] | None = None
    for t, c in samples:
        if c >= floor:
            if cur is None:
                cur = [t, t + win]
            else:
                cur[1] = t + win
        else:
            if cur is not None:
                raw.append(cur)
                cur = None
    if cur is not None:
        raw.append(cur)

    if not raw:
        return []
    merged: list[list[float]] = [list(raw[0])]
    for s, e in raw[1:]:
        if s <= merged[-1][1] + merge_gap:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [
        (round(s, 3), round(e, 3))
        for s, e in merged
        if e - s >= min_span
    ]


def spine_coverage_ratio(spans: list[tuple[float, float]] | list[dict],
                         times: list[float]) -> float:
    """Fraction of guitar onset span covered by spine boxes. Used as a
    regression guard so Quiet-open / Busy-close packs cannot silently starve."""
    if not times or len(times) < 2:
        return 0.0
    total = float(times[-1]) - float(times[0])
    if total <= 0:
        return 0.0
    covered = 0.0
    for s in spans:
        if isinstance(s, dict):
            a, b = float(s["start"]), float(s["end"])
        else:
            a, b = float(s[0]), float(s[1])
        a = max(a, float(times[0]))
        b = min(b, float(times[-1]))
        if b > a:
            covered += b - a
    return min(1.0, covered / total)




def _fp_token_set(fp: str) -> set[str]:
    return {p for p in (fp or "").split("|") if p}


def _fp_jaccard(a: str, b: str) -> float:
    sa, sb = _fp_token_set(a), _fp_token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))


def _phrase_fingerprint(pack, start: float, end: float, track_idx) -> str:
    """Stable fingerprint of bars overlapping [start, end) on one track."""
    parts: list[str] = []
    for m in getattr(pack, "measures", None) or []:
        a = float(getattr(m, "start_sec_audio", 0.0) or 0.0)
        b = _measure_audio_end(m)
        if b <= start or a >= end:
            continue
        try:
            parts.append(tabnotes.bar_fp_tab(pack, m, track_idx))
        except Exception:
            continue
    return "||".join(parts)


def pack_phrase_spans(
    pack,
    *,
    min_span: float = 8.0,
    max_span: float = 36.0,
    gap_split: float = 0.75,
    rate_frac: float = 0.45,
    rate_floor: float = 2.0,
    fp_split: float = 0.42,
    identity_jaccard: float = 0.72,
) -> list[dict]:
    """Phrase-level riff boxes from pack guitar activity + pitch contour.

    Finer than the coverage spine (~4 blobs) and coarser than unique bar-run
    hashes (~60 one-shots). Splits on silence gaps, meter/tempo cuts,
    guitar-density jumps, and bar-fingerprint (pitch/articulation) changes.
    Returning phrases reuse the first `figure_id` when fuzzy bar-fp Jaccard
    >= `identity_jaccard`. `[]` when no guitar.
    """
    import bisect
    import statistics

    times = tabnotes.onsets_audio(pack, category="guitar")
    measures = list(getattr(pack, "measures", None) or [])
    if len(measures) < 4 or len(times) < 8:
        return []

    # Primary guitar track for contour fingerprints
    track_idx = 0
    try:
        from .figures import _tab_track_by_category
        tr = _tab_track_by_category(pack, "guitar")
        if tr is not None:
            track_idx = int(getattr(tr, "index", 0) or 0)
    except Exception:
        track_idx = 0

    rows: list[tuple[float, float, int, float, str]] = []
    for m in measures:
        a = float(getattr(m, "start_sec_audio", 0.0) or 0.0)
        b = _measure_audio_end(m)
        if b <= a:
            continue
        lo = bisect.bisect_left(times, a)
        hi = bisect.bisect_left(times, b)
        n = hi - lo
        if n < 2:
            continue
        try:
            fp = tabnotes.bar_fp_tab(pack, m, track_idx)
        except Exception:
            fp = ""
        rows.append((a, b, n, n / (b - a), fp))
    if not rows:
        return []

    rates = [r[3] for r in rows]
    med = statistics.median(rates) if rates else 0.0
    cuts = set(meter_cuts(pack))

    segs: list[list[tuple[float, float, int, float, str]]] = [[rows[0]]]
    for prev, cur in zip(rows, rows[1:]):
        gap = cur[0] - prev[1]
        r0, r1 = prev[3], cur[3]
        at_cut = any(abs(cur[0] - c) < 0.35 for c in cuts)
        fp_jump = _fp_jaccard(prev[4], cur[4]) < fp_split if (prev[4] or cur[4]) else False
        split = (
            gap > gap_split
            or at_cut
            or abs(r1 - r0) > max(med * rate_frac, rate_floor)
            or fp_jump
        )
        if split:
            segs.append([cur])
        else:
            segs[-1].append(cur)

    raw = [(seg[0][0], seg[-1][1]) for seg in segs]
    merged: list[list[float]] = []
    for s, e in raw:
        if merged and (e - s) < min_span and (merged[-1][1] - merged[-1][0]) < max_span:
            merged[-1][1] = e
        else:
            merged.append([s, e])

    final: list[tuple[float, float]] = []
    for s, e in merged:
        if e - s <= max_span:
            final.append((round(s, 3), round(e, 3)))
            continue
        cands = [r for r in rows if s + min_span <= r[0] <= e - min_span]
        if not cands:
            final.append((round(s, 3), round(e, 3)))
            continue
        mid = (s + e) / 2.0
        # Prefer a strong fingerprint jump near the middle when splitting longs
        def score(r):
            # lower is better: distance to mid, prefer low jaccard vs prev bar
            return abs(r[0] - mid)
        best = min(cands, key=score)
        final.append((round(s, 3), round(best[0], 3)))
        final.append((round(best[0], 3), round(e, 3)))

    # Assign figure_ids with returning identity
    phrases: list[dict] = []
    seen: list[tuple[str, str]] = []  # (fp, figure_id)
    letter_i = 0
    for s, e in final:
        if e - s < min_span * 0.5:
            continue
        fp = _phrase_fingerprint(pack, s, e, track_idx)
        fid = None
        # Empty fingerprints (no notes resolved) must not collapse everything
        # to riff-A via Jaccard(empty, empty) == 1.
        if fp and any(tok.strip("|") for tok in fp.split("||")):
            for prev_fp, prev_id in seen:
                if not prev_fp:
                    continue
                if _fp_jaccard(fp, prev_fp) >= identity_jaccard:
                    fid = prev_id
                    break
        if fid is None:
            fid = "riff-%s" % _letter(letter_i)
            letter_i += 1
            if fp:
                seen.append((fp, fid))
        phrases.append({
            "role": "riff", "start": s, "end": e, "figure_id": fid,
        })
    from collections import Counter
    counts = Counter(p["figure_id"] for p in phrases)
    for p in phrases:
        p["unique"] = counts[p["figure_id"]] == 1
    return phrases



def phrase_drafts_for_song(lab_root, album: str, track: str, *,
                           min_span: float = 8.0) -> list[dict]:
    """Stamped unheard phrase drafts for one pack song when sync_ok.

    Primary Guess structure for pack-only tracks (no GP markers). Never a keeper.
    """
    if not _sync_ok(lab_root, album, track):
        return []
    try:
        pack_path = tabnotes.discover_pack(lab_root, album, track)
        if pack_path is None:
            return []
        pack = tabnotes.load_pack(pack_path)
        spans = pack_phrase_spans(pack, min_span=min_span)
    except Exception:
        return []
    from .schema import stamp_box

    return [
        stamp_box(s["start"], s["end"], s["role"], source=SOURCE_PHRASE,
                  figure_id=s["figure_id"], heard=False,
                  extra={"album": album, "track": track, "kind": "phrase",
                         "unique": bool(s.get("unique", True))})
        for s in spans
    ]


def pack_structure_spans(pack, *, min_span: float = 2.0) -> list[dict]:
    """The pack's own structure spine: guitar-active runs as `role=riff`
    boxes with order-assigned `riff-A` / `riff-B` / ... ids.

    Prefer the measure grid (full-song coverage). Fall back to windowed
    activity, then legacy peak-density spans. A pack has no GP section
    letters, so none are invented. No stamping / sync check here --
    `structure_drafts_for_song` gates and stamps. `[]` when no phrase.
    """
    times = tabnotes.onsets_audio(pack, category="guitar")
    pairs = _guitar_onset_spans_from_measures(pack, times, min_span=min_span)
    if not pairs:
        pairs = _guitar_onset_spans_from_windows(times, min_span=min_span)
    if not pairs:
        # last resort: old peak-relative density (may be sparse on uneven songs)
        pairs = riff_density_spans(pack, min_span=min_span)
    return [
        {"role": "riff", "start": s, "end": e, "figure_id": "riff-%s" % _letter(i)}
        for i, (s, e) in enumerate(pairs)
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
        times = tabnotes.onsets_audio(pack, category="guitar")
        cov = spine_coverage_ratio(spans, times)
        if times and cov < 0.45:
            print(
                "WARN pack spine coverage %.0f%% for %s / %s (want >=45%%) -- check tabnotes"
                % (100.0 * cov, album, track)
            )
    except Exception:
        return []
    from .schema import stamp_box

    return [
        stamp_box(s["start"], s["end"], s["role"], source=SOURCE_STRUCTURE,
                  figure_id=s["figure_id"], heard=False,
                  extra={"album": album, "track": track, "kind": "structure",
                         "spine_coverage": round(cov, 3)})
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
