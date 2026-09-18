"""Riff identity -- name RUNS of bars that already exist as measures.

Given a matched GP5, fingerprint each bar (`bar_fp`), segment playback order
into maximal runs of equal bars, and emit windows that are RUNS -- an ostinato
run is one window, never a pile of sliding 1-bar 2/4-bar windows. Cluster
windows by exact fingerprint, name them by a consistent GP marker letter or
`riff-A/B` by first start, and flag a letter that maps to two fingerprints
(`conflict`). This is identity, not segmentation: it never cuts new boxes and
never invents boundaries. Machines never write keepers -- output is drafts with
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


def bar_fp(measure):
    """One bar's identity: quantized 1/8 onsets (duration + is_rest), the
    semitone `deltas`, and the tuple of pitch-class sets from `chord_notes`.
    Octave/velocity ignored; a chord never collapses to its top note. Pure."""
    cell = _field(measure, "cell", None) or []
    rhythm = tuple(
        (int(round(float(_field(h, "duration", 0) or 0) * 2)),
         bool(_field(h, "is_rest", False)))
        for h in cell
    )
    deltas = tuple(int(d) for d in (_field(measure, "deltas", None) or []))
    notes = _field(measure, "chord_notes", None) or []
    if notes:
        pcs = tuple(tuple(sorted(int(n) % 12 for n in hit)) for hit in notes)
    else:
        # No chord data: fall back to the cumulative top-note pitches.
        cur = 0
        seen = set()
        for i, d in enumerate(deltas):
            cur = int(d) if i == 0 else cur + int(d)
            seen.add(cur % 12)
        pcs = (tuple(sorted(seen)),) if seen else ()
    return (rhythm, deltas, pcs)


def window_fp(cells) -> str:
    """Stable fingerprint of a window (one or more bars). Same bars in the
    same order => same token, across songs."""
    return hashlib.sha1(repr(tuple(bar_fp(c) for c in cells)).encode("utf-8")).hexdigest()[:12]


def hash_window(cells) -> str:
    """Backward-compatible alias for `window_fp`."""
    return window_fp(cells)


def _first_key(w):
    start = w.get("start")
    return (0, float(start)) if start is not None else (1, w.get("start_bar") or 0)


def _occ(w):
    return {"start": w.get("start"), "end": w.get("end"),
            "start_bar": w.get("start_bar"), "end_bar": w.get("end_bar")}


def cluster_song(windows) -> list[dict]:
    """Cluster windows by EXACT fingerprint (no Jaccard merge).

    `figure_id` = a consistent GP marker letter (`{role}-{letter}`) else
    `riff-A`, `riff-B`, ... by first start. `conflict` is true when one GP
    letter maps to two different fingerprints."""
    groups: dict[str, list[dict]] = {}
    for w in windows or []:
        groups.setdefault(w.get("hash"), []).append(w)

    out: list[dict] = []
    for group in groups.values():
        occ = sorted(group, key=_first_key)
        first = occ[0]
        letters = {w.get("letter") for w in occ if w.get("letter")}
        role = None
        for w in occ:
            if w.get("role"):
                role = w["role"]
                break
        out.append({
            "hash": first.get("hash"),
            "n_bars": first.get("n_bars"),
            "start": first.get("start"),
            "end": first.get("end"),
            "start_bar": first.get("start_bar"),
            "end_bar": first.get("end_bar"),
            "n_hits": len(group),
            "unique": len(group) == 1,
            "occurrences": [_occ(w) for w in occ],
            "role": role,
            "letter": next(iter(letters)) if len(letters) == 1 else None,
        })
    out.sort(key=_first_key)
    unnamed = 0
    for c in out:
        if c["letter"]:
            c["figure_id"] = "%s-%s" % (c["role"] or "riff", c["letter"])
        else:
            c["figure_id"] = "riff-" + _letters(unnamed)
            unnamed += 1
    by_letter: dict[str, set] = {}
    for c in out:
        if c["letter"]:
            by_letter.setdefault(c["letter"], set()).add(c["hash"])
    conflicts = {letter for letter, hashes in by_letter.items() if len(hashes) > 1}
    for c in out:
        c["conflict"] = bool(c["letter"] and c["letter"] in conflicts)
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


def _marker_of(frag):
    from .extract import _section_letter

    _form, letter = _section_letter(_field(frag, "raw_marker") or "")
    return letter, _field(frag, "role")


def _make_window(entries):
    cells = [e[4] for e in entries]
    letter, role = _marker_of(cells[0])
    n_repeats = len(cells) if len({bar_fp(c) for c in cells}) == 1 else 1
    return {
        "start": entries[0][1],
        "end": round(entries[-1][1] + entries[-1][3], 3),
        "start_bar": entries[0][2],
        "end_bar": entries[-1][2],
        "hash": window_fp(cells),
        "n_bars": len(cells),
        "n_repeats": n_repeats,
        "letter": letter,
        "role": role,
    }


def _contiguous_runs(slots, by_mi):
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
    return runs


def _song_windows(fragments, slots) -> list[dict]:
    """RUNS, not slides: each maximal run of equal `bar_fp` becomes one
    ostinato window; bars not inside such a run are paired into non-overlapping
    2-bar blocks. A 2-bar window is never emitted inside a longer same-sequence
    window."""
    by_mi = {f.measure_index: f for f in fragments}
    windows: list[dict] = []
    for run in _contiguous_runs(slots, by_mi):
        segments: list[tuple] = []
        for entry in run:
            fp = bar_fp(entry[4])
            if segments and segments[-1][0] == fp:
                segments[-1][1].append(entry)
            else:
                segments.append((fp, [entry]))

        covered: set[int] = set()
        for _fp, entries in segments:
            if len(entries) >= 2:
                windows.append(_make_window(entries))
                covered.update(id(e) for e in entries)

        i = 0
        while i < len(run):
            if id(run[i]) in covered:
                i += 1
                continue
            block = [run[i]]
            j = i + 1
            while j < len(run) and id(run[j]) not in covered and len(block) < 2:
                block.append(run[j])
                j += 1
            windows.append(_make_window(block))
            i = j
    return windows


def build_figures(lab_root, rows, *, album=None, track=None) -> dict:
    """Suggest repeating `figure_id`s for each matched GP5 song.

    Writes one row per repeating window cluster. Replaces only the songs it
    rebuilt (keyed by album+track); a run that yields zero rows leaves an
    existing `data/figures.jsonl` untouched."""
    lab_root = Path(lab_root)
    out = lab_root / "data" / "figures.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    if album and track:
        from .catalogue import resolve_row

        target = resolve_row(rows, album, track)
        if target is not None:
            album = target.get("album") or album
            track = target.get("track") or track
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

        clusters = [c for c in cluster_song(windows) if c["n_hits"] >= 2]
        # Seconds are only trustworthy when the tab clock actually matched the
        # audio (sync_ok). Otherwise keep bars/hashes and publish no times.
        trusted = bool((sync_by.get((ra, rt)) or {}).get("sync_ok") is True)
        for c in clusters:
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
                "figure_id": c["figure_id"], "hash": c["hash"],
                "n_bars": c["n_bars"], "n_hits": c["n_hits"], "unique": c["unique"],
                "start": start, "end": end,
                "start_bar": c["start_bar"], "end_bar": c["end_bar"],
                "occurrences": occ, "times_trusted": trusted,
                "conflict": c["conflict"], "source": "figure-hash",
            })
        print("FIGURES", rt, len(windows), "window(s),", len(clusters), "repeating",
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
