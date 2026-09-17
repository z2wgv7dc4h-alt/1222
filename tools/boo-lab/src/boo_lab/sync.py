"""Tab-vs-audio clock witness. Map-level only: never touches pins.

Builds a coarse onset series from the GP5 (note starts in seconds on the
tab's own tempo/measure clock) and one from the audio (librosa onset
strength, guitar stem if cached else the mix), then scores their normalized
cross-correlation. Both sides are blurred (~120 ms) first, so an onset only
has to land *near* a tab note -- a raw impulse comb against a broad envelope
is too spiky and latches wrong peaks on repeated riffs. `sync_ok` means the
tab clock is within 350 ms of the audio at the same rate. No new dependencies
(numpy + librosa only).
"""
from __future__ import annotations

import json
from pathlib import Path

LAG_TOLERANCE = 0.35  # seconds -- sync_ok requires |lag| below this
SCORE_THRESHOLD = 0.15  # normalized cross-correlation peak
SMOOTH_SECONDS = 0.12  # blur before correlating: onsets need only land near each other
RATE_TOLERANCE = 0.015  # sync_ok requires the tab clock rate within 1.5% of the audio


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





def gp_onset_times(gp_path: Path) -> list[float] | None:
    """Real note-start times (seconds) on the tab's own tempo/measure clock,
    in playback order (repeats expanded). `None` when the GP cannot be parsed.

    Faithful where it matters: `song.tempo` (per-measure `header.tempo` only
    when set), time signatures, repeat/unroll, dotted and tuplet beats.
    """
    try:
        import guitarpro

        song = guitarpro.parse(str(gp_path))
    except Exception:
        return None
    from .extract import _rhythm_track

    track = _rhythm_track(song) or (song.tracks[0] if song.tracks else None)
    if track is None:
        return None

    onsets: list[float] = []
    t = 0.0
    # `song.tempo` is the file's tempo; defaulting to 120 stretched every tab
    # (a 195 BPM song walked 1.6x too long, so the clock never lined up).
    # Onsets and the measure advance share the same beat-duration arithmetic so
    # the clock stays self-consistent; repeats are expanded via `_playback_order`.
    bpm = float(getattr(song, "tempo", None) or 120.0)
    for idx in _playback_order(track.measures):
        measure = track.measures[idx]
        val = getattr(getattr(measure.header, "tempo", None), "value", None)
        if val:
            bpm = float(val)
        beat_seconds = 60.0 / max(bpm, 1.0)
        for voice in measure.voices:
            for beat in voice.beats:
                if beat.notes:
                    onsets.append(round(t, 4))
                quarters = 4.0 / beat.duration.value
                if beat.duration.isDotted:
                    quarters *= 1.5
                t += quarters * beat_seconds
            break
    return onsets


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


def _smooth(env, window_frames: int):
    import numpy as np

    if window_frames <= 1:
        return env
    kernel = np.ones(window_frames, dtype=float) / window_frames
    return np.convolve(env, kernel, mode="same")


def best_lag_and_score(
    env_gp, env_audio, hop_s: float, smooth_s: float = SMOOTH_SECONDS
) -> tuple[float, float]:
    """Normalized cross-correlation peak of two 1-D envelopes, after blurring
    both so an onset only has to land *near* a tab note (a raw impulse comb vs
    a broad envelope is too spiky and picks wrong peaks on repeated riffs).
    Returns `(lag_seconds, score)`; sign of lag is not meaningful."""
    import numpy as np

    a = np.asarray(env_gp, dtype=float)
    b = np.asarray(env_audio, dtype=float)
    n = max(a.size, b.size)
    if n == 0:
        return 0.0, 0.0
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
        return 0.0, 0.0
    corr = np.correlate(a, b, mode="full") / denom
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


def decide(lag_sec: float, score: float) -> bool:
    return bool(abs(lag_sec) < LAG_TOLERANCE and score >= SCORE_THRESHOLD)


def _write_sync(lab_root: Path, rec: dict) -> None:
    path = Path(lab_root) / "data" / "sync.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = [
        r for r in _read_jsonl(path)
        if not ((r.get("album") or "") == rec["album"] and (r.get("track") or "") == rec["track"])
    ]
    with path.open("w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def sync_track(lab_root: Path, album: str | None, track: str | None) -> dict:
    """Score one song's tab clock against its audio. `ValueError` when either
    `album` or `track` is missing (never the whole catalog)."""
    if not album or not track:
        raise ValueError("need both --album and --track (never the whole catalog)")
    from .catalogue import load_map

    lab_root = Path(lab_root)
    rows = [
        r for r in load_map(lab_root / "data" / "map.csv")
        if (r.get("album") or "") == album and (r.get("track") or "") == track
    ] if (lab_root / "data" / "map.csv").exists() else []
    row = rows[0] if rows else {}

    gp = Path(row.get("gp") or "")
    flac = Path(row.get("flac") or "")
    rec = {
        "album": album, "track": track, "sync_ok": False, "lag_sec": None,
        "score": None, "used_stem": "", "gp": row.get("gp") or "",
        "flac": row.get("flac") or "", "flac_sha256": row.get("flac_sha256") or "",
        "note": "",
    }

    if not (row.get("gp") and gp.exists()):
        rec["note"] = "no-gp"
        _write_sync(lab_root, rec)
        return rec

    onsets = gp_onset_times(gp)
    if onsets is None:
        rec["note"] = "unreadable-gp"
        _write_sync(lab_root, rec)
        return rec

    src = flac if flac.exists() else None
    used = "mix"
    if src is not None:
        from .stems import find_stem

        stem = find_stem(flac, lab_root / "work" / "stems", "guitar")
        if stem:
            src, used = stem, "guitar"
    rec["used_stem"] = used
    if src is None or not Path(src).exists():
        rec["note"] = "no-audio"
        _write_sync(lab_root, rec)
        return rec

    env_audio, hop_s = audio_envelope(Path(src))
    env_gp = envelope_from_times(onsets, len(env_audio), hop_s)
    lag, score = best_lag_and_score(env_gp, env_audio, hop_s)
    # Diagnostic only: a rate that fits better than the raw peak can mean a
    # notated tempo difference, but on a tab that's short because a section is
    # missing it also finds bogus peaks -- so it never overrides the raw lag.
    ratio, _rlag, rscore = best_clock_fit(env_gp, env_audio, hop_s, span=0.08)
    rec["clock_ratio"] = round(ratio, 4)
    rec["lag_sec"] = round(lag, 4)
    rec["score"] = round(score, 4)
    rec["sync_ok"] = decide(lag, score)
    if rec["sync_ok"]:
        rec["note"] = "ok"
    elif abs(ratio - 1.0) > RATE_TOLERANCE and rscore > score + 0.03:
        rec["note"] = "clock x%.3f (notated tempo differs)" % ratio
    elif abs(lag) >= LAG_TOLERANCE:
        rec["note"] = "lag %.3fs > %.3fs" % (abs(lag), LAG_TOLERANCE)
    else:
        rec["note"] = "low score %.3f < %.3f" % (score, SCORE_THRESHOLD)
    _write_sync(lab_root, rec)
    return rec
