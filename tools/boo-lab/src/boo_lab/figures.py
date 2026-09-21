"""Riff identity -- name RUNS of bars that already exist as measures.

Given a matched GP5 or a local tab-notes pack (`tabnotes.py`; the pack wins
when both are available, same precedence `sync.py` already uses), fingerprint
each bar (`bar_fp`), segment playback order into maximal runs of equal bars,
and emit windows that are RUNS -- an ostinato run is one window, never a pile
of sliding 1-bar 2/4-bar windows. Cluster windows by exact fingerprint, name
them by a consistent GP marker letter or `riff-A/B` by first start, and flag a
letter that maps to two fingerprints (`conflict`). This is identity, not
segmentation: it never cuts new boxes and never invents boundaries.

Repeating clusters (`n_hits >= 2`) stay the trusted identity stream. Unique
(one-shot) runs are also written as drafts (`unique=true`) so pack-only songs
still populate Guess — through-composed phrases never qualified under a
repeats-only gate. Machines
never write keepers -- output is drafts with `source="figure-hash"`, written
to `data/figures.jsonl` under the same never-blank-on-a-zero-row law as
`beats`/`structure`.
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


def _tab_track_by_category(pack, category):
    """The pack's `category` track with the lowest mean pitch -- a rhythm-
    register proxy (same intent as the engine's own GM-program register
    filter, `riff_bank._select_rhythm_track`, adapted to a source with no GM
    program range). For `"guitar"` this picks the rhythm guitar among
    several; for `"bass"` there is usually only one candidate anyway.
    `None` when the pack has no track of that category (fails closed, same
    as the GP path returning `None`)."""
    cands = [t for t in pack.tracks if (t.category or "").lower() == category]
    if not cands:
        return None
    best, best_mean = None, None
    for t in cands:
        pitches = [e.pitch for e in pack.events if e.track == t.index and e.pitch is not None]
        if not pitches:
            continue
        mean = sum(pitches) / len(pitches)
        if best_mean is None or mean < best_mean:
            best, best_mean = t, mean
    return best or cands[0]


def _measure_cell_and_deltas_tab(events, length_beats):
    """The tab-notes mirror of the engine's own `_measure_cell_and_deltas`:
    same `(cell, deltas, chord_notes)` shape, built from onset-grouped
    `TabEvent`s instead of a parsed GP measure. Events sharing an
    `onset_beat` are one chord hit (top pitch drives `deltas`, same
    top-note convention as the GP path); a gap in the beat grid becomes an
    explicit rest hit, including a trailing rest up to `length_beats`."""
    by_onset: dict[float, list] = {}
    for e in events:
        by_onset.setdefault(round(e.onset_beat, 6), []).append(e)

    cell: list[dict] = []
    deltas: list[int] = []
    chord_notes: list[list[int]] = []
    prev_pitch = None
    cursor = 0.0
    for onset in sorted(by_onset):
        if onset > cursor + 1e-6:
            cell.append({"duration": round(onset - cursor, 6), "is_rest": True})
            cursor = onset
        hit_events = by_onset[onset]
        dur = max((e.duration_beats or 0.0) for e in hit_events) or 0.5
        hit = {"duration": round(dur, 6), "is_rest": False}
        if any(e.palm_mute for e in hit_events):
            hit["palm_mute"] = True
        if any(e.harmonic for e in hit_events):
            hit["harmonic"] = True
        if any(e.slide for e in hit_events):
            hit["slide"] = True
        cell.append(hit)
        pitches = [e.pitch for e in hit_events if e.pitch is not None]
        chord_notes.append(pitches)
        if pitches:
            pitch = max(pitches)
            deltas.append(0 if prev_pitch is None else pitch - prev_pitch)
            prev_pitch = pitch
        cursor = onset + dur
    if length_beats and length_beats > cursor + 1e-6:
        cell.append({"duration": round(length_beats - cursor, 6), "is_rest": True})
    return cell, deltas, chord_notes


def _tab_fragments_and_slots(pack, category="guitar", track=None):
    """`(fragments, slots)` from one tab-notes pack track -- the pack-native
    mirror of the GP `_playback_slots` + `_engine_riff_bank().
    extract_fragments_from_file`/`extract_bass_fragments_from_file` pair.
    `RiffFragment` is the real engine dataclass (`_engine_riff_bank`), never
    a second definition; `instrument` on it is set to `category` so a bass
    cluster is never mistaken for a guitar one downstream. No repeat-bar
    expansion: the format carries none, so each measure appears once, in
    written order -- a known gap versus the GP path's `playback_bar_order`.

    `track` selects a specific `TabTrack` directly (used to cluster a
    second/third guitar track on its own, since a pack can carry several --
    see `build_figures`); when omitted, `_tab_track_by_category(pack,
    category)` picks one. `(None, None)` when there's no matching track or
    no measures."""
    from .extract import _engine_riff_bank
    from .tabnotes import bar_events

    if track is None:
        track = _tab_track_by_category(pack, category)
    if track is None or not pack.measures:
        return None, None

    riff_bank = _engine_riff_bank()
    fragments = []
    slots = []
    for m in sorted(pack.measures, key=lambda m: m.measure):
        evs = sorted(bar_events(pack, m.measure, track=track.index),
                     key=lambda e: e.onset_beat)
        cell, deltas, chord_notes = _measure_cell_and_deltas_tab(evs, m.length_beats or 0.0)
        start_sec = m.start_sec_audio if m.start_sec_audio is not None else m.start_ms / 1000.0
        dur_sec = (m.audio_duration_sec if m.audio_duration_sec is not None
                   else m.duration_ms / 1000.0)
        slots.append((m.measure, start_sec, m.measure + 1, dur_sec))
        if not cell or not deltas:
            continue
        fragments.append(riff_bank.RiffFragment(
            source_song=pack.title or pack.id,
            source_file=Path(pack.source_path).name,
            measure_index=m.measure,
            track="tabnotes",
            cell=cell,
            deltas=deltas,
            role=None,
            raw_marker=None,
            instrument=category,
            source_type="tab_verbatim",
            chord_notes=chord_notes,
        ))
    return fragments, slots


def _tab_pulse_windows(pack) -> list[dict]:
    """Candidate Pulse spans from a tab-notes pack: contiguous-measure runs
    of a `category="other"` track's events -- LAW.md's Pulse is "a named
    synth/keyboard figure, not 'keys are audible'", and a Songsterr-style
    `other`-category track (e.g. "SynthStrings 1") is exactly that, already
    timestamped. One row per run, sorted by start. Strict measure-to-measure
    contiguity (no gap tolerance) -- a pad that drops out for a full bar and
    returns starts a new window; a known, simple first pass. `[]` when the
    pack has no `other` track or that track has no events."""
    from .tabnotes import events_for

    other_tracks = [t for t in pack.tracks if (t.category or "").lower() == "other"]
    if not other_tracks:
        return []

    windows: list[dict] = []
    for t in other_tracks:
        evs = sorted(events_for(pack, track=t.index), key=lambda e: (e.measure, e.onset_beat))
        if not evs:
            continue
        measures = sorted({e.measure for e in evs})
        runs: list[list[int]] = [[measures[0]]]
        for mi in measures[1:]:
            if mi == runs[-1][-1] + 1:
                runs[-1].append(mi)
            else:
                runs.append([mi])
        for run in runs:
            run_events = [e for e in evs if e.measure in run]
            first = run_events[0]
            last = max(run_events, key=lambda e: (e.measure, e.onset_beat))
            windows.append({
                "start": round(pack.audio_sec(first), 3),
                "end": round(pack.audio_sec(last) + (last.duration_ms or 0.0) / 1000.0, 3),
                "start_bar": run[0] + 1,
                "end_bar": run[-1] + 1,
            })
    windows.sort(key=lambda w: w["start"])
    return windows


def _emit_clusters(rows, windows, *, album, track, trusted, note_source, instrument,
                   id_prefix="", extra=None):
    """Cluster `windows` and append one produced row per cluster to `rows`.

    Repeating (`n_hits >= 2`) and unique one-shot runs (`unique=true`) both
    land so pack-only through-composed songs still populate Guess. Shared by
    the guitar/GP, extra-guitar-track and bass emission paths in
    `build_figures`. `extra` merges additional fields (e.g. `track_index`)
    into every row. Returns the clusters for the caller's log line."""
    clusters = [c for c in cluster_song(windows) if c["n_hits"] >= 1]
    for c in clusters:
        if trusted:
            start, end = c["start"], c["end"]
            occ = c["occurrences"]
        else:
            start = end = None
            occ = [{"start": None, "end": None,
                    "start_bar": o["start_bar"], "end_bar": o["end_bar"]}
                   for o in c["occurrences"]]
        row = {
            "album": album, "track": track,
            "figure_id": id_prefix + c["figure_id"], "hash": c["hash"],
            "n_bars": c["n_bars"], "n_hits": c["n_hits"], "unique": c["unique"],
            "start": start, "end": end,
            "start_bar": c["start_bar"], "end_bar": c["end_bar"],
            "occurrences": occ, "times_trusted": trusted,
            "conflict": c["conflict"], "source": "figure-hash",
            "note_source": note_source, "instrument": instrument,
        }
        if extra:
            row.update(extra)
        rows.append(row)
    return clusters


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
    """Suggest `figure_id`s for each song with a tab-notes pack or a matched
    GP5 (the pack wins when both exist -- see module docstring).

    Writes one row per window cluster, including unique (non-repeating) runs.
    Replaces only the songs it rebuilt (keyed by album+track); a run that
    yields zero rows leaves an existing `data/figures.jsonl` untouched."""
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
    from .tabnotes import discover_pack, load_pack

    sync_by = {(s.get("album"), s.get("track")): s
               for s in _read_jsonl(lab_root / "data" / "sync.jsonl")}

    for r in rows:
        ra = r.get("album") or ""
        rt = r.get("track") or ""
        if akey is not None and ra.casefold() != akey:
            continue
        if tkey is not None and rt.casefold() != tkey:
            continue

        # A local tab-notes pack wins over any GP file for riff identity --
        # same precedence `sync.py` already uses. Pack discovery is kept
        # separate from fragment-extraction success so a song whose guitar
        # track yields no usable riff windows still gets Pulse detection
        # below (which reads a different track on the same pack).
        pack = None
        try:
            pack_path = discover_pack(lab_root, ra, rt)
            if pack_path is not None:
                pack = load_pack(pack_path)
        except Exception as exc:
            print("SKIP figures (tabnotes)", rt, exc)
            pack = None

        fragments = slots = None
        note_source = None
        primary_guitar = _tab_track_by_category(pack, "guitar") if pack is not None else None
        if pack is not None:
            try:
                fragments, slots = _tab_fragments_and_slots(pack, track=primary_guitar)
            except Exception as exc:
                print("SKIP figures (tabnotes fragments)", rt, exc)
                fragments = slots = None
            if fragments and slots:
                note_source = "tabnotes"
            else:
                fragments = slots = None

        if fragments is None:
            matched = (r.get("match") or "").lower() in {"yes", "y", "1", "true"}
            gp_raw = r.get("gp_path") or r.get("gp") or ""
            gp = Path(gp_raw) if gp_raw else None
            if matched and gp is not None and gp.exists():
                try:
                    fragments = _engine_riff_bank().extract_fragments_from_file(gp, song_title=rt)
                    slots = _playback_slots(gp)
                    note_source = "gp"
                except Exception as exc:  # real unparseable GP files exist in this corpus
                    print("SKIP figures", rt, exc)
                    fragments = slots = None

        # A tab-notes pack alone (no riff figures, e.g. no usable guitar
        # content on either source) still gets Pulse detection below --
        # only bail out here when there's neither a pack nor riff fragments.
        if pack is None and not fragments:
            skipped += 1
            print("SKIP figures", rt, "no matched gp" if pack is None else "no fragments")
            continue

        rebuilt.add((ra, rt))
        songs += 1
        # Seconds are only trustworthy when the tab clock actually matched the
        # audio (sync_ok). Otherwise keep bars/hashes and publish no times.
        trusted = bool((sync_by.get((ra, rt)) or {}).get("sync_ok") is True)

        windows = _song_windows(fragments, slots) if fragments and slots else []
        if not windows:
            print("FIGURES", rt, "0 windows")
        else:
            clusters = _emit_clusters(produced, windows, album=ra, track=rt, trusted=trusted,
                                      note_source=note_source, instrument="guitar")
            print("FIGURES", rt, len(windows), "window(s),", len(clusters), "cluster(s)",
                  "(times trusted)" if trusted else "(bars only; sync not ok)",
                  "[%s]" % note_source)

        # Extra guitar tracks: a pack can carry more than one `guitar`-
        # category track (e.g. two rhythm guitars doubled/panned, a third
        # layered part) and only the lowest-mean-pitch one becomes the
        # unprefixed `riff-*` stream above. Register alone doesn't reliably
        # separate "lead" from a doubled rhythm part on real corpus data
        # (checked: three same-song guitar tracks all landed in the same
        # 46-52 mean-pitch band) -- so every other guitar track gets its own
        # independent cluster pass instead of being discarded or guessed at,
        # namespaced `guitar<index>-` and tagged with `track_index` so it's
        # traceable back to the source track.
        if pack is not None and primary_guitar is not None:
            extra_guitars = [t for t in pack.tracks
                             if (t.category or "").lower() == "guitar"
                             and t.index != primary_guitar.index]
            for t in extra_guitars:
                try:
                    g_frags, g_slots = _tab_fragments_and_slots(pack, track=t)
                except Exception as exc:
                    print("SKIP figures (tabnotes guitar track)", rt, t.index, exc)
                    continue
                if not g_frags or not g_slots:
                    continue
                g_windows = _song_windows(g_frags, g_slots)
                if not g_windows:
                    continue
                g_clusters = _emit_clusters(
                    produced, g_windows, album=ra, track=rt, trusted=trusted,
                    note_source="tabnotes", instrument="guitar",
                    id_prefix="guitar%d-" % t.index, extra={"track_index": t.index})
                print("FIGURES", rt, len(g_windows), "guitar[%d] window(s)," % t.index,
                      len(g_clusters), "cluster(s)")

        # Bass: a tab-notes pack's `bass`-category track, same cluster/RUNS
        # machinery as guitar (`_tab_fragments_and_slots(pack, "bass")`),
        # namespaced with a `bass-` figure_id prefix so a bass riff can never
        # collide with a guitar one sharing the same letter. Tabnotes-only:
        # `build_figures`'s GP path never extracts bass (`_engine_riff_bank`
        # has a bass extractor, but nothing here calls it -- out of scope).
        if pack is not None:
            try:
                bass_frags, bass_slots = _tab_fragments_and_slots(pack, category="bass")
            except Exception as exc:
                print("SKIP figures (tabnotes bass)", rt, exc)
                bass_frags = bass_slots = None
            if bass_frags and bass_slots:
                bass_windows = _song_windows(bass_frags, bass_slots)
                if bass_windows:
                    bass_clusters = _emit_clusters(
                        produced, bass_windows, album=ra, track=rt, trusted=trusted,
                        note_source="tabnotes", instrument="bass", id_prefix="bass-")
                    print("FIGURES", rt, len(bass_windows), "bass window(s),",
                          len(bass_clusters), "cluster(s)")

        # Pulse: a tab-notes pack's `other`-category track (named synth/
        # keyboard, LAW.md's Pulse definition) has no GP-side equivalent --
        # `_engine_riff_bank` only extracts guitar/bass/lead -- so this is a
        # tabnotes-only signal.
        if pack is not None:
            for i, w in enumerate(_tab_pulse_windows(pack)):
                produced.append({
                    "album": ra, "track": rt,
                    "figure_id": "pulse-%s" % _letters(i), "hash": None,
                    "n_bars": w["end_bar"] - w["start_bar"] + 1,
                    "n_hits": 1, "unique": True,
                    "start": w["start"] if trusted else None,
                    "end": w["end"] if trusted else None,
                    "start_bar": w["start_bar"], "end_bar": w["end_bar"],
                    "occurrences": [{
                        "start": w["start"] if trusted else None,
                        "end": w["end"] if trusted else None,
                        "start_bar": w["start_bar"], "end_bar": w["end_bar"],
                    }],
                    "times_trusted": trusted, "conflict": False,
                    "role": "pulse", "source": "figure-hash", "instrument": "other",
                    "note_source": "tabnotes",  # pulse is tabnotes-only, see above
                })

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
