"""Riff identity -- name windows that already exist as measures.

Given a matched GP5, hash 2-bar and 4-bar rhythm-guitar windows in playback
order, cluster near-duplicates INSIDE one song, and suggest `figure_id`
values. This is identity, not segmentation: it never cuts new boxes and never
invents boundaries. Machines never write keepers -- output is drafts with
`source="figure-hash"`, written to `data/figures.jsonl` under the same
never-blank-on-a-zero-row law as `beats`/`structure`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _letters(i: int) -> str:
    """0 -> 'A', 25 -> 'Z', 26 -> 'AA' (spreadsheet-style, so a song with more
    than 26 clusters still gets real names)."""
    out = ""
    i += 1
    while i > 0:
        i, rem = divmod(i - 1, 26)
        out = _ALPHABET[rem] + out
    return out


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _pitch_classes(measure) -> frozenset[int]:
    """Pitch-class set of one measure (octave/velocity ignored, chords kept as
    sets). Prefers riff_bank's complete `chord_notes`; falls back to the
    cumulative top-note `deltas` only when no chord data exists."""
    notes = _field(measure, "chord_notes", None)
    pcs: set[int] = set()
    if notes:
        for hit in notes:
            for n in hit:
                pcs.add(int(n) % 12)
        return frozenset(pcs)
    deltas = _field(measure, "deltas", None) or []
    cur = 0
    for i, d in enumerate(deltas):
        cur = int(d) if i == 0 else cur + int(d)
        pcs.add(cur % 12)
    return frozenset(pcs)


def _rhythm_mask(measure) -> str:
    """Coarse 4-beat onset grid for one measure: "1010" = onsets on beats 1
    and 3. Durations are quarter-note beats; a rest contributes no onset."""
    cell = _field(measure, "cell", None) or []
    mask = [0, 0, 0, 0]
    pos = 0.0
    for hit in cell:
        dur = float(_field(hit, "duration", 0) or 0)
        if not _field(hit, "is_rest", False):
            beat = int(pos + 1e-6)
            if 0 <= beat < 4:
                mask[beat] = 1
        pos += dur
    return "".join(str(b) for b in mask)


def hash_window(cells) -> str:
    """Stable fingerprint of a 2- or 4-measure window: per-measure pitch-class
    set (chord-aware, octave/velocity ignored) plus the coarse 4-beat onset
    grid. Same notes + rhythm => same hash, across songs. Pure function."""
    parts = []
    for measure in cells or []:
        pcs = ",".join(str(p) for p in sorted(_pitch_classes(measure)))
        parts.append(pcs + "|" + _rhythm_mask(measure))
    return hashlib.sha1(";".join(parts).encode("utf-8")).hexdigest()[:12]


def _grid(w):
    return w.get("rhythm") or w.get("grid")


def _pcs_list(w):
    pcs = w.get("pcs")
    return [set(m) for m in pcs] if pcs else None


def _compatible(a, b, jaccard_min: float) -> bool:
    """Two hashes may merge when their rhythm grids match AND the mean
    measure-level pitch-class Jaccard across the window is >= `jaccard_min`.
    Only possible when the windows carry `pcs`/`rhythm` (build_figures does)."""
    ga, gb = _grid(a), _grid(b)
    if not ga or not gb or list(ga) != list(gb):
        return False
    pa, pb = _pcs_list(a), _pcs_list(b)
    if not pa or not pb or len(pa) != len(pb):
        return False
    scores = []
    for sa, sb in zip(pa, pb):
        union = sa | sb
        scores.append(1.0 if not union else len(sa & sb) / len(union))
    return bool(scores) and (sum(scores) / len(scores)) >= jaccard_min


def _first_key(w):
    start = w.get("start")
    return (0, float(start)) if start is not None else (1, w.get("start_bar") or 0)


def _occ(w):
    return {"start": w.get("start"), "end": w.get("end"),
            "start_bar": w.get("start_bar"), "end_bar": w.get("end_bar")}


def cluster_song(windows, *, jaccard_min: float = 0.85) -> list[dict]:
    """Group a song's windows into repeating figures.

    Exact-hash groups first; a group may merge into another when the optional
    per-window pitch-class Jaccard clears `jaccard_min` and the rhythm grids
    match. `figure_id` is `riff-A`, `riff-B`, ... by first-start order;
    `n_hits` counts windows in the cluster and `unique` is `n_hits == 1`."""
    groups: dict[str, list[dict]] = {}
    for w in windows or []:
        groups.setdefault(w.get("hash"), []).append(w)

    merged: list[dict] = []
    for group in groups.values():
        placed = False
        for m in merged:
            if _compatible(m["rep"], group[0], jaccard_min):
                m["windows"].extend(group)
                placed = True
                break
        if not placed:
            merged.append({"rep": group[0], "windows": list(group)})

    out: list[dict] = []
    for m in merged:
        occ = sorted(m["windows"], key=_first_key)
        first = occ[0]
        out.append({
            "hash": m["rep"].get("hash"),
            "n_bars": m["rep"].get("n_bars"),
            "start": first.get("start"),
            "end": first.get("end"),
            "start_bar": first.get("start_bar"),
            "end_bar": first.get("end_bar"),
            "n_hits": len(m["windows"]),
            "unique": len(m["windows"]) == 1,
            "occurrences": [_occ(w) for w in occ],
        })
    out.sort(key=_first_key)
    for i, c in enumerate(out):
        c["figure_id"] = "riff-" + _letters(i)
    return out


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


def _playback_slots(gp_path: Path):
    """`[(measure_index, start_sec, bar_no, dur_sec), ...]` in playback order
    (repeats expanded), on the tab's own tempo/measure clock. Bar numbers are
    the 1-based tab measures; a repeat plays the same bar again."""
    import guitarpro

    from .extract import _rhythm_track
    from .sync import _playback_order

    song = guitarpro.parse(str(gp_path))
    track = _rhythm_track(song) or (song.tracks[0] if song.tracks else None)
    if track is None:
        return None
    order = _playback_order(track.measures)
    t = 0.0
    bpm = float(getattr(getattr(song, "tempo", None), "value", None)
                or getattr(song, "tempo", 120) or 120)
    slots = []
    for idx in order:
        measure = track.measures[idx]
        header = getattr(measure, "header", None)
        val = getattr(getattr(header, "tempo", None), "value", None)
        if val:
            bpm = float(val)
        ts = getattr(measure, "timeSignature", None) or getattr(header, "timeSignature", None)
        num = getattr(ts, "numerator", 4) if ts else 4
        den_obj = getattr(ts, "denominator", 4) if ts else 4
        den = getattr(den_obj, "value", den_obj) or 4
        dur = (float(num) * 4.0 / float(den)) * 60.0 / max(bpm, 1.0)
        slots.append((idx, t, idx + 1, dur))
        t += dur
    return slots


def _song_windows(fragments, slots) -> list[dict]:
    """Contiguous 2- and 4-measure windows over runs of consecutive measures
    that actually carry a fragment -- no invented boundaries."""
    by_mi = {f.measure_index: f for f in fragments}
    runs: list[list[tuple]] = []
    cur: list[tuple] = []
    prev = None
    for (mi, sec, bar, dur) in slots:
        frag = by_mi.get(mi)
        if frag is None:
            if cur:
                runs.append(cur)
            cur = []
            prev = mi
            continue
        if prev is not None and mi == prev + 1:
            cur.append((mi, sec, bar, dur, frag))
        else:
            if cur:
                runs.append(cur)
            cur = [(mi, sec, bar, dur, frag)]
        prev = mi
    if cur:
        runs.append(cur)

    windows: list[dict] = []
    for run in runs:
        n = len(run)
        for i in range(n):
            for size in (2, 4):
                if i + size > n:
                    continue
                chunk = run[i:i + size]
                cells = [c[4] for c in chunk]
                windows.append({
                    "start": chunk[0][1],
                    "end": round(chunk[-1][1] + chunk[-1][3], 3),
                    "start_bar": chunk[0][2],
                    "end_bar": chunk[-1][2],
                    "hash": hash_window(cells),
                    "n_bars": size,
                    "pcs": [sorted(_pitch_classes(c)) for c in cells],
                    "rhythm": [_rhythm_mask(c) for c in cells],
                })
    return windows


def _span_contains(outer: dict, inner: dict) -> bool:
    if outer.get("start") is not None and inner.get("start") is not None:
        return (outer["start"] - 1e-6 <= inner["start"]
                and inner["end"] <= outer["end"] + 1e-6)
    ob0, ob1 = outer.get("start_bar"), outer.get("end_bar")
    ib0, ib1 = inner.get("start_bar"), inner.get("end_bar")
    if None in (ob0, ob1, ib0, ib1):
        return False
    return ob0 <= ib0 and ib1 <= ob1


def build_figures(lab_root, rows, *, album=None, track=None) -> dict:
    """Suggest repeating `figure_id`s for each matched GP5 song.

    Clusters 4-bar windows first, then 2-bar windows that are not already
    inside a 4-bar cluster with `n_hits >= 2`. Replaces only the songs it
    rebuilt (keyed by album+track); a run that yields zero rows leaves an
    existing `data/figures.jsonl` untouched."""
    lab_root = Path(lab_root)
    out = lab_root / "data" / "figures.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    akey = album.casefold() if album else None
    tkey = track.casefold() if track else None

    produced: list[dict] = []
    rebuilt: set[tuple[str, str]] = set()
    songs = 0
    skipped = 0

    from .extract import _engine_riff_bank
    from .schema import write_jsonl_atomic

    sync_by = {(s.get("album"), s.get("track")): s
               for s in _read_jsonl(lab_root / "data" / "sync.jsonl")}

    for r in rows:
        ra = r.get("album") or ""
        rt = r.get("track") or ""
        if akey is not None and ra.casefold() != akey:
            continue
        if tkey is not None and rt.casefold() != tkey:
            continue
        matched = (r.get("match") or "").lower() in {"yes", "y", "1", "true"}
        gp_raw = r.get("gp_path") or r.get("gp") or ""
        gp = Path(gp_raw) if gp_raw else None
        if not matched or gp is None or not gp.exists():
            skipped += 1
            print("SKIP figures", rt, "no matched gp")
            continue
        try:
            fragments = _engine_riff_bank().extract_fragments_from_file(gp, song_title=rt)
            slots = _playback_slots(gp)
        except Exception as exc:  # real unparseable GP files exist in this corpus
            skipped += 1
            print("SKIP figures", rt, exc)
            continue
        rebuilt.add((ra, rt))
        if not fragments or not slots:
            skipped += 1
            print("SKIP figures", rt, "no fragments")
            continue

        windows = _song_windows(fragments, slots)
        songs += 1
        if not windows:
            print("FIGURES", rt, "0 windows")
            continue

        four = [w for w in windows if w["n_bars"] == 4]
        two = [w for w in windows if w["n_bars"] == 2]
        covered = [c for c in cluster_song(four) if c["n_hits"] >= 2]

        def covered_by(w):
            return any(_span_contains(occ, w)
                       for c in covered for occ in c["occurrences"])

        two_keep = [w for w in two if not covered_by(w)]
        clusters = cluster_song(four + two_keep)
        song_rows = [c for c in clusters if c["n_hits"] >= 2]
        # Seconds are only trustworthy when the tab clock actually matched the
        # audio (sync_ok). Otherwise keep bars/hashes and publish no times.
        trusted = bool((sync_by.get((ra, rt)) or {}).get("sync_ok") is True)
        # Re-letter only the repeating clusters we actually suggest, by
        # first-start order, so the studio sees riff-A, riff-B, ...
        for i, c in enumerate(song_rows):
            if trusted:
                start, end = c["start"], c["end"]
                occ = c["occurrences"]
            else:
                start = end = None
                occ = [{"start": None, "end": None,
                        "start_bar": o["start_bar"], "end_bar": o["end_bar"]}
                       for o in c["occurrences"]]
            produced.append({
                "album": ra, "track": rt,
                "figure_id": "riff-" + _letters(i), "hash": c["hash"],
                "n_bars": c["n_bars"], "n_hits": c["n_hits"], "unique": c["unique"],
                "start": start, "end": end,
                "start_bar": c["start_bar"], "end_bar": c["end_bar"],
                "occurrences": occ, "times_trusted": trusted,
                "source": "figure-hash",
            })
        print("FIGURES", rt, len(windows), "windows,", len(song_rows), "repeating",
              "(times trusted)" if trusted else "(bars only; sync not ok)")

    if not produced:
        print("figures: 0 rows written; leaving", out.name, "untouched")
        return {"songs": songs, "clusters": 0, "written": 0,
                "skipped": skipped, "out": str(out)}

    existing = _read_jsonl(out)
    keep = [x for x in existing
            if (x.get("album"), x.get("track")) not in rebuilt]
    write_jsonl_atomic(out, keep + produced)
    return {"songs": songs, "clusters": len(produced), "written": len(produced),
            "skipped": skipped, "out": str(out)}


def load_figures(lab_root, album, track) -> list[dict]:
    """`data/figures.jsonl` rows for one song (empty when not computed)."""
    path = Path(lab_root) / "data" / "figures.jsonl"
    return [r for r in _read_jsonl(path)
            if (r.get("album") or "") == (album or "")
            and (r.get("track") or "") == (track or "")]
