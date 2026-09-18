"""Tab-vs-audio clock witness. Map-level only: never touches pins.

Builds a coarse onset series from the GP5 (note starts in seconds on the
tab's own tempo/measure clock) and one from the audio (librosa onset
strength, guitar stem if cached else the mix), then scores their normalized
cross-correlation. Both sides are blurred (~120 ms) first, so an onset only
has to land *near* a tab note -- a raw impulse comb against a broad envelope
is too spiky and latches wrong peaks on repeated riffs. A second witness
aligns tab pitches against audio chroma (harmonic content, drums matter far
less); `sync_ok` passes if either witness is within 350 ms. No new
dependencies (numpy + librosa only).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

LAG_TOLERANCE = 0.35  # seconds -- sync_ok requires |lag| below this
SCORE_THRESHOLD = 0.15  # normalized cross-correlation peak
SMOOTH_SECONDS = 0.12  # blur before correlating: onsets need only land near each other
RATE_TOLERANCE = 0.015  # sync_ok requires the tab clock rate within 1.5% of the audio
LEADIN_MAX = 5.0  # an "aligned with offset" pass must be within this many seconds
PROMINENCE_MIN = 0.05  # ... and the correlation peak must stand out this much
CLOCK_SPAN = 0.08  # best_clock_fit search half-width (a searched rate only passes inside this)
CO_WITNESS_SECONDS = 0.25  # two witnesses "agree" within this; never a pass threshold on its own


GP7_EXTS = (".gp", ".gpx")


def _norm_stem(name: str) -> str:
    """A GP stem without its track-number prefix or punctuation, so
    "07 - Exist" and "07 Exist" compare equal."""
    s = re.sub(r"^\d+[\s._-]+", "", name or "")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _prefer_gpif_path(gp_path: Path) -> Path:
    """Sync-time preference: a `.gp5` clock is replaced by a matching
    `.gp`/`.gpx` when one exists beside it or under `BOO_GP_ROOT` (same
    normalized stem). Never deletes or rewrites map.csv; returns the input
    unchanged when there is no GP7 sibling."""
    p = Path(gp_path)
    if p.suffix.lower() != ".gp5":
        return p
    key = _norm_stem(p.stem)
    if not key:
        return p
    cands = [c for c in p.parent.glob("*") if c.suffix.lower() in GP7_EXTS]
    root = os.environ.get("BOO_GP_ROOT")
    if root:
        rootp = Path(root)
        gp7 = rootp / "gp7"
        search = gp7 if gp7.is_dir() else rootp
        if search.is_dir():
            cands += [c for c in search.rglob("*") if c.suffix.lower() in GP7_EXTS]
    for cand in sorted(cands):
        if _norm_stem(cand.stem) == key:
            return cand
    return p


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


def _enclosing_open(headers: list, i: int) -> int:
    """Nearest prior `isRepeatOpen` measure at or before `i` (innermost)."""
    for j in range(i, -1, -1):
        if getattr(headers[j], "isRepeatOpen", False):
            return j
    return 0


def _playback_order(measures: list) -> list[int]:
    """Measure indices in real playback order, expanding repeat-open/close and
    alternative endings. `repeatClose` is the number of EXTRA repeats (the
    parser already subtracts 1), so a group plays `repeatClose + 1` times."""
    headers = [m.header for m in measures]
    n = len(measures)
    order: list[int] = []
    counts: dict[int, int] = {}
    i = 0
    guard = 0
    while 0 <= i < n and guard < 200000:
        guard += 1
        h = headers[i]
        alt = getattr(h, "repeatAlternative", 0)
        if alt:
            open_idx = _enclosing_open(headers, i)
            if not (alt & (1 << counts.get(open_idx, 0))):
                i += 1
                continue
        order.append(i)
        if getattr(h, "isRepeatOpen", False):
            # setdefault: a repeat group re-enters this index on every pass;
            # resetting here would loop forever.
            counts.setdefault(i, 0)
        rc = getattr(h, "repeatClose", -1)
        if rc != -1:
            open_idx = _enclosing_open(headers, i)
            if counts.get(open_idx, 0) < rc:
                counts[open_idx] = counts.get(open_idx, 0) + 1
                i = open_idx
                continue
        i += 1
    return order





def _tab_notes(gp_path: Path):
    """Generator of `(seconds, [midi pitches])` for each notated beat, on the
    tab's own tempo/measure clock, in playback order (repeats expanded).
    `None` when the GP cannot be parsed.

    Faithful where it matters: `song.tempo` (per-measure `header.tempo` only
    when set), repeat/unroll, dotted beats; onset time and the measure advance
    share the same beat-duration arithmetic so the clock stays self-consistent.

    A `.gp`/`.gpx` is read via the parsed GPIF score FIRST (never a conversion);
    `.gp5` (and any other suffix) still goes through `guitarpro.parse`.
    """
    p = Path(gp_path)
    if p.suffix.lower() in GP7_EXTS:
        events = _gpif_events(p)
        if events is not None:
            return events
    try:
        import guitarpro

        song = guitarpro.parse(str(gp_path))
    except Exception:
        # A last-resort GPIF read for a non-GP7 suffix; `None` otherwise.
        return None if p.suffix.lower() in GP7_EXTS else _gpif_events(p)
    from .extract import _rhythm_track

    track = _rhythm_track(song) or (song.tracks[0] if song.tracks else None)
    if track is None:
        return None

    def walk():
        t = 0.0
        bpm = float(getattr(song, "tempo", None) or 120.0)
        for idx in _playback_order(track.measures):
            measure = track.measures[idx]
            val = getattr(getattr(measure.header, "tempo", None), "value", None)
            if val:
                bpm = float(val)
            beat_seconds = 60.0 / max(bpm, 1.0)
            for voice in measure.voices:
                for beat in voice.beats:
                    quarters = 4.0 / beat.duration.value
                    if beat.duration.isDotted:
                        quarters *= 1.5
                    dur = quarters * beat_seconds
                    if beat.notes:
                        pitches = []
                        for note in beat.notes:
                            try:
                                pitches.append(int(note.realValue))
                            except Exception:
                                pass
                        yield t, pitches, dur
                    t += dur
                break

    return walk()


def _gpif_events(gp_path: Path):
    """`_tab_notes`-shaped events from a GP7 `.gp`/`.gpx` via its parsed GPIF
    score. `None` when the file is not GP7 or the score will not parse, so the
    caller keeps its `unreadable-gp` outcome. Onsets only (no pitches)."""
    p = Path(gp_path)
    if p.suffix.lower() not in (".gp", ".gpx"):
        return None
    try:
        from .gpif import load_score, note_events

        score = load_score(p)
    except Exception:
        return None
    return note_events(score)


def gp_onset_times(gp_path: Path) -> list[float] | None:
    """Real note-start times (seconds) in playback order; `None` if unparseable."""
    events = _tab_notes(gp_path)
    if events is None:
        return None
    # seconds is always element [0]; GPIF events carry extra fields after it.
    return [round(e[0], 4) for e in events]


def envelope_from_times(times: list[float], n_frames: int, hop_s: float):
    import numpy as np

    env = np.zeros(max(0, n_frames), dtype=float)
    if hop_s <= 0:
        return env
    for t in times:
        i = int(round(t / hop_s))
        if 0 <= i < env.size:
            env[i] += 1.0
    return env


def audio_envelope(path: Path):
    """`(onset_strength envelope, hop seconds)` from an audio file."""
    import librosa

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    hop = 512
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    return env, hop / float(sr)


def gp_chroma(gp_path: Path, hop_s: float, n_frames: int):
    """`(12, n_frames)` pitch-class activity from the tab's note starts, in
    playback order. `None` when the GP cannot be parsed."""
    import numpy as np

    events = _tab_notes(gp_path)
    if events is None:
        return None
    chroma = np.zeros((12, max(0, n_frames)), dtype=float)
    if hop_s <= 0:
        return chroma
    for t, pitches, dur in events:
        # Hold each note over its beat: audio chroma is sustained, so an
        # onset-only comb correlates poorly even when the pitches are right.
        start = int(round(t / hop_s))
        stop = max(start + 1, int(round((t + dur) / hop_s)))
        for frame in range(start, min(stop, chroma.shape[1])):
            for pitch in pitches:
                chroma[pitch % 12, frame] += 1.0
    return chroma


def audio_chroma(path: Path):
    """`(12, T) chroma_cqt, hop seconds` -- harmonic content, which is driven by
    the guitars rather than the drums that dominate onset strength."""
    import librosa

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    hop = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    return chroma, hop / float(sr)


def _smooth(env, window_frames: int):
    import numpy as np

    if window_frames <= 1:
        return env
    kernel = np.ones(window_frames, dtype=float) / window_frames
    return np.convolve(env, kernel, mode="same")


def best_alignment(
    env_gp, env_audio, hop_s: float, smooth_s: float = SMOOTH_SECONDS
) -> tuple[float, float, float]:
    """Normalized cross-correlation peak of two 1-D envelopes, after blurring
    both so an onset only has to land *near* a tab note (a raw impulse comb vs
    a broad envelope is too spiky and picks wrong peaks on repeated riffs).
    Returns `(lag_seconds, score, prominence)`. Prominence is the peak minus
    the best score outside a +/-0.5 s neighborhood -- a genuine offset is one
    sharp peak, a wrong peak on a repeated riff is one of several near-ties."""
    import numpy as np

    a = np.asarray(env_gp, dtype=float)
    b = np.asarray(env_audio, dtype=float)
    n = max(a.size, b.size)
    if n == 0:
        return 0.0, 0.0, 0.0
    a = np.pad(a, (0, n - a.size))
    b = np.pad(b, (0, n - b.size))
    if hop_s > 0 and smooth_s > 0:
        w = max(1, int(round(smooth_s / hop_s)))
        a = _smooth(a, w)
        b = _smooth(b, w)
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 0:
        return 0.0, 0.0, 0.0
    corr = np.correlate(a, b, mode="full") / denom
    k = int(np.argmax(corr))
    peak = float(corr[k])
    w = max(1, int(round(0.5 / hop_s))) if hop_s > 0 else 1
    lo, hi = max(0, k - w), min(corr.size, k + w + 1)
    rest = np.concatenate([corr[:lo], corr[hi:]])
    nxt = float(rest.max()) if rest.size else 0.0
    return (k - (n - 1)) * hop_s, peak, peak - nxt


def best_lag_and_score(
    env_gp, env_audio, hop_s: float, smooth_s: float = SMOOTH_SECONDS
) -> tuple[float, float]:
    lag, score, _prom = best_alignment(env_gp, env_audio, hop_s, smooth_s)
    return lag, score


def _smooth_rows(matrix, window_frames: int):
    import numpy as np

    if window_frames <= 1:
        return matrix
    kernel = np.ones(window_frames, dtype=float) / window_frames
    out = np.empty_like(matrix)
    for row in range(matrix.shape[0]):
        out[row] = np.convolve(matrix[row], kernel, mode="same")
    return out


def chroma_lag_and_score(
    gp_chroma, audio_chroma, hop_s: float, smooth_s: float = SMOOTH_SECONDS
) -> tuple[float, float]:
    """Normalized cross-correlation of two chroma matrices along time.
    Returns `(lag_seconds, score)`. Harmonic content, so drums matter less
    than they do for the onset-strength envelope."""
    import numpy as np

    a = np.asarray(gp_chroma, dtype=float)
    b = np.asarray(audio_chroma, dtype=float)
    if a.size == 0 or b.size == 0:
        return 0.0, 0.0
    n = max(a.shape[1], b.shape[1])
    A = np.zeros((12, n))
    B = np.zeros((12, n))
    A[:, : a.shape[1]] = a[:12]
    B[:, : b.shape[1]] = b[:12]
    if hop_s > 0 and smooth_s > 0:
        w = max(1, int(round(smooth_s / hop_s)))
        A = _smooth_rows(A, w)
        B = _smooth_rows(B, w)
    A = A - A.mean(axis=1, keepdims=True)
    B = B - B.mean(axis=1, keepdims=True)
    num = np.zeros(2 * n - 1)
    for pc in range(12):
        num += np.correlate(A[pc], B[pc], mode="full")
    denom = float(np.linalg.norm(A) * np.linalg.norm(B))
    if denom <= 0:
        return 0.0, 0.0
    corr = num / denom
    k = int(np.argmax(corr))
    return (k - (n - 1)) * hop_s, float(corr[k])


def best_clock_fit(
    env_gp, env_audio, hop_s: float, span: float = 0.12, step: float = 0.01
) -> tuple[float, float, float]:
    """Fit a clock RATE as well as an offset: search `a` in [1-span, 1+span],
    resample the GP envelope by `a`, keep the best. Returns `(ratio, lag, score)`.
    This separates "the tab is notated at a different tempo" (a fixable rate)
    from "the tab is wrong"."""
    import numpy as np

    g = np.asarray(env_gp, dtype=float)
    if g.size == 0:
        return 1.0, 0.0, 0.0
    src = np.arange(g.size, dtype=float)
    best = (1.0, 0.0, -1.0)
    k = int(round(span / step))
    for i in range(-k, k + 1):
        ratio = 1.0 + i * step
        m = max(2, int(round(g.size * ratio)))
        resampled = np.interp(np.linspace(0, g.size - 1, m), src, g)
        lag, score = best_lag_and_score(resampled, env_audio, hop_s)
        if score > best[2]:
            best = (ratio, lag, score)
    return best


def _resample_rows(matrix, ratio: float):
    """Time-scale a `(12, T)` chroma matrix by `ratio`, the chroma twin of
    `best_clock_fit`'s envelope resample. Scores the chroma witness at the SAME
    winning ratio -- chroma is never searched independently."""
    import numpy as np

    A = np.asarray(matrix, dtype=float)
    if A.size == 0 or abs(ratio - 1.0) <= 1e-9:
        return A
    n = A.shape[1]
    m = max(2, int(round(n * ratio)))
    src = np.arange(n, dtype=float)
    dst = np.linspace(0, n - 1, m)
    out = np.empty((A.shape[0], m))
    for pc in range(A.shape[0]):
        out[pc] = np.interp(dst, src, A[pc])
    return out


def _rate_corroborated(rlag, clag_r, cscore_r, clag, cscore):
    """Whether a chroma witness backs an onset rate-fit at `rlag`.

    Returns `True`/`False` when any chroma witness exists, and `None` when
    there is none at all -- a lone onset rate-fit may then stand on its own,
    exactly as the ratio=1 `onset_ok` rule already can. A bare ratio is never a
    pass; `decide(rlag, rscore)` still has to hold."""
    if clag_r is None and clag is None:
        return None
    if clag_r is not None and abs(clag_r - rlag) < CO_WITNESS_SECONDS:
        return True
    if (clag is not None and cscore is not None
            and cscore >= SCORE_THRESHOLD and abs(clag - rlag) < CO_WITNESS_SECONDS):
        return True
    return False


def decide(lag_sec: float, score: float) -> bool:
    return bool(abs(lag_sec) < LAG_TOLERANCE and score >= SCORE_THRESHOLD)


def _write_sync(lab_root: Path, rec: dict) -> None:
    path = Path(lab_root) / "data" / "sync.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = [
        r for r in _read_jsonl(path)
        if not ((r.get("album") or "") == rec["album"] and (r.get("track") or "") == rec["track"])
    ]
    from .schema import write_jsonl_atomic

    write_jsonl_atomic(path, kept + [rec], ensure_ascii=False)


def _tab_play_seconds(gp_path: Path) -> float | None:
    """Real playback length of the tab (repeats expanded). A `.gp`/`.gpx` uses
    `gpif.duration_sec`; otherwise extract's `_playback_duration`. `None` when
    the GP cannot be parsed -- never a second tempo walker."""
    p = Path(gp_path)
    if p.suffix.lower() in GP7_EXTS:
        try:
            from .gpif import duration_sec, load_score

            return float(duration_sec(load_score(p)))
        except Exception:
            return None
    try:
        import guitarpro

        from .extract import _playback_duration, _rhythm_track

        song = guitarpro.parse(str(gp_path))
        track = _rhythm_track(song) or (song.tracks[0] if song.tracks else None)
        if track is None:
            return None
        bpm = float(getattr(getattr(song, "tempo", None), "value", None) or 120.0)
        return float(_playback_duration(track, bpm))
    except Exception:
        return None


def _audio_seconds(flac_path: Path) -> float | None:
    try:
        import librosa

        return float(librosa.get_duration(path=str(flac_path)))
    except Exception:
        return None


def _duration_note(gp_path: Path, flac_path: Path, dly: float | None) -> str:
    """One-line `tab_play=Xs flac=Ys dly=Zs` for a genuine failed sync (tab and
    audio both exist). Empty when either length is unavailable."""
    tab_s = _tab_play_seconds(gp_path)
    flac_s = _audio_seconds(flac_path)
    if tab_s is None or flac_s is None:
        return ""
    return "tab_play=%.1fs flac=%.1fs dly=%.2fs" % (tab_s, flac_s, dly or 0.0)


def _evaluate_source(src: Path, gp: Path, onsets: list[float]) -> dict:
    """Run both witnesses (onset + chroma) on one audio source, at ratio=1 and
    at the best-fit clock rate. The rate is never a pass on its own: the
    resampled onset envelope still has to peak near zero (`decide`) and the
    chroma witness has to agree at that same ratio."""
    env_audio, hop_s = audio_envelope(Path(src))
    env_gp = envelope_from_times(onsets, len(env_audio), hop_s)
    lag, score, prom = best_alignment(env_gp, env_audio, hop_s)
    ratio, rlag, rscore = best_clock_fit(env_gp, env_audio, hop_s, span=CLOCK_SPAN)
    clag = cscore = None
    clag_r = cscore_r = None
    try:
        audio_c, chop = audio_chroma(Path(src))
        gp_c = gp_chroma(gp, chop, audio_c.shape[1])
        if gp_c is not None:
            clag, cscore = chroma_lag_and_score(gp_c, audio_c, chop)
            if abs(ratio - 1.0) > 1e-9:
                clag_r, cscore_r = chroma_lag_and_score(
                    _resample_rows(gp_c, ratio), audio_c, chop)
            else:
                clag_r, cscore_r = clag, cscore
    except Exception:
        pass
    onset_ok = decide(lag, score)
    chroma_ok = clag is not None and decide(clag, cscore)
    within = abs(ratio - 1.0) <= CLOCK_SPAN + 1e-9
    corrob = _rate_corroborated(rlag, clag_r, cscore_r, clag, cscore)
    rate_ok = bool(within and decide(rlag, rscore) and corrob is not False)
    return {
        "lag": lag, "score": score, "prom": prom,
        "ratio": ratio, "rlag": rlag, "rscore": rscore,
        "clag": clag, "cscore": cscore, "clag_r": clag_r, "cscore_r": cscore_r,
        "onset_ok": onset_ok,
        "chroma_ok": chroma_ok,
        "rate_ok": rate_ok,
        # "aligned with offset": a bounded, prominent peak the other witness sees too
        "onset_leadin": (
            not onset_ok
            and score >= SCORE_THRESHOLD
            and LAG_TOLERANCE <= abs(lag) <= LEADIN_MAX
            and prom >= PROMINENCE_MIN
        ),
    }


_OUTCOME_RANK = {"fail": 0, "lead-in": 1, "rate": 2, "aligned": 3}


def _outcome(ev: dict) -> tuple[str, float | None]:
    """Classify one source's witnesses as `aligned`, `rate`, `lead-in`, or
    `fail`. `rate` uses `ev.get` so a hand-built witness dict (tests) without
    the clock-fit keys still classifies."""
    if ev["onset_ok"]:
        return "aligned", ev["lag"]
    if ev["chroma_ok"]:
        return "aligned", ev["clag"]
    if ev.get("rate_ok"):
        return "rate", ev.get("rlag")
    if ev["onset_leadin"]:
        clag = ev["clag"]
        if clag is not None and abs(clag) <= LEADIN_MAX and abs(clag - ev["lag"]) < CO_WITNESS_SECONDS:
            return "lead-in", ev["lag"]
    return "fail", ev["lag"]


def sync_track(lab_root: Path, album: str | None, track: str | None) -> dict:
    """Score one song's tab clock against its audio. `ValueError` when either
    `album` or `track` is missing (never the whole catalog)."""
    if not album or not track:
        raise ValueError("need both --album and --track (never the whole catalog)")
    from .catalogue import load_map, resolve_row

    lab_root = Path(lab_root)
    map_path = lab_root / "data" / "map.csv"
    rows = load_map(map_path) if map_path.exists() else []
    row = resolve_row(rows, album, track)

    rec = {
        "album": album, "track": track, "sync_ok": False, "lag_sec": None,
        "score": None, "clock_ratio": None, "chroma_lag": None,
        "chroma_score": None, "offset_sec": None, "used_stem": "", "gp": "",
        "flac": "", "flac_sha256": "", "note": "",
    }

    if row is None:
        # Distinct from no-gp: the map itself has no such album/track.
        rec["note"] = "no-row"
        _write_sync(lab_root, rec)
        return rec

    # Report the resolved names so the CLI shows "2009 - A Higher Place" even
    # when the human typed "A Higher Place"; fill the real paths on the row.
    rec["album"] = row.get("album") or album
    rec["track"] = row.get("track") or track
    rec["gp"] = row.get("gp") or ""
    rec["flac"] = row.get("flac") or ""
    rec["flac_sha256"] = row.get("flac_sha256") or ""

    if rec["gp"]:
        gp = _prefer_gpif_path(Path(rec["gp"]))  # .gp5 -> matching .gp/.gpx
        rec["gp"] = str(gp)                      # gp field = path actually clocked
    else:
        gp = Path(rec["gp"])
    flac = Path(rec["flac"])
    if not (rec["gp"] and gp.exists()):
        rec["note"] = "no-gp"
        _write_sync(lab_root, rec)
        return rec

    onsets = gp_onset_times(gp)
    if onsets is None:
        rec["note"] = "unreadable-gp"
        _write_sync(lab_root, rec)
        return rec

    if not flac.exists():
        rec["note"] = "no-audio"
        _write_sync(lab_root, rec)
        return rec

    from .stems import find_stem

    guitar = find_stem(flac, lab_root / "work" / "stems", "guitar")
    # Prefer the guitar stem (drums gone), fall back to the mix: isolated
    # guitar can mis-peak where the mix does not, and vice versa. Stop as soon
    # as a source yields an `aligned` outcome.
    candidates = ([("guitar", guitar)] if guitar else []) + [("mix", flac)]
    used, ev, kind, offset = None, None, "fail", None
    for label, path in candidates:
        cand = _evaluate_source(path, gp, onsets)
        ckind, coffset = _outcome(cand)
        if ev is None or _OUTCOME_RANK[ckind] > _OUTCOME_RANK[kind]:
            used, ev, kind, offset = label, cand, ckind, coffset
        if kind == "aligned":
            break
    rec["used_stem"] = used
    if kind == "rate":
        # Best fit is the rate-adjusted one; clock_ratio is the stretch applied.
        rec["clock_ratio"] = round(ev["ratio"], 4)
        rec["lag_sec"] = round(ev["rlag"], 4)
        rec["score"] = round(ev["rscore"], 4)
    else:
        rec["clock_ratio"] = 1.0  # no stretch on the aligned/lead-in path
        rec["lag_sec"] = round(ev["lag"], 4)
        rec["score"] = round(ev["score"], 4)
    rec["chroma_lag"] = round(ev["clag"], 4) if ev["clag"] is not None else None
    rec["chroma_score"] = round(ev["cscore"], 4) if ev["cscore"] is not None else None
    rec["sync_ok"] = kind != "fail"
    rec["offset_sec"] = round(offset, 4) if kind == "lead-in" else None
    if kind == "aligned":
        rec["note"] = "ok" if ev["onset_ok"] else "ok (chroma)"
    elif kind == "rate":
        rec["note"] = "ok (rate %.3f)" % ev["ratio"]
    elif kind == "lead-in":
        rec["note"] = "ok (lead-in %.2fs)" % offset
    elif abs(ev["ratio"] - 1.0) > RATE_TOLERANCE and ev["rscore"] > ev["score"] + 0.03:
        rec["note"] = "clock x%.3f (notated tempo differs)" % ev["ratio"]
    elif abs(ev["lag"]) >= LAG_TOLERANCE:
        rec["note"] = "lag %.3fs > %.3fs" % (abs(ev["lag"]), LAG_TOLERANCE)
    else:
        rec["note"] = "low score %.3f < %.3f" % (ev["score"], SCORE_THRESHOLD)
    if kind == "fail":
        extra = _duration_note(gp, flac, rec["lag_sec"])
        if extra:
            rec["note"] = rec["note"] + " · " + extra
    if gp.suffix.lower() in GP7_EXTS:
        rec["note"] = rec["note"] + " · gpif"
    _write_sync(lab_root, rec)
    return rec
