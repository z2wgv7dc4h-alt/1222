from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

# Real f0 search range for a sung/screamed metal vocal line -- C2 (the low
# end of a male chest voice) up to C7 (falsetto/scream harmonics).
_PYIN_FMIN = librosa.note_to_hz("C2")
_PYIN_FMAX = librosa.note_to_hz("C7")

# Pitch/timing analysis doesn't need the source's full 44.1kHz bandwidth.
_ANALYSIS_SR = 22050

# Real default pitch tracker: `torchcrepe`'s CREPE -- a published
# deep-learning monophonic pitch estimator, meaningfully more accurate than
# pyin on real vocal audio. CREPE's model runs at 16kHz; `torchcrepe.predict`
# pads/frames at `hop_length`, so frame i is centered at `i*hop/sr` seconds.
_CREPE_SR = 16000
_CREPE_HOP = 160  # 10 ms frames at 16 kHz
_CREPE_CONFIDENCE = 0.5  # periodicity below this = an honest unvoiced frame
_FMIN_HZ = max(50.0, float(librosa.note_to_hz("C2")))
_FMAX_HZ = 2006.0  # torchcrepe's own MAX_FMAX


def _find_vocals(flac: Path, cache: Path) -> Path | None:
    """Cached demucs `vocals.wav` for one FLAC -- the exact same directory
    pattern as `stems.find_drums`, just the vocals stem. Reads an existing
    separation; never re-runs demucs."""
    name = flac.stem
    for model in ("htdemucs", "htdemucs_ft", "mdx_extra", "mdx_extra_q"):
        p = cache / model / name / "vocals.wav"
        if p.exists():
            return p
    near = [
        flac.parent / "stems" / (name + ".vocals.wav"),
        flac.parent / "stems" / "vocals.wav",
        flac.parent / (name + ".vocals.wav"),
    ]
    for p in near:
        if p.exists():
            return p
    return None


def _pyin_contour(y: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Real per-frame f0 (NaN when unvoiced) + frame times via
    `librosa.pyin` -- the previous tracker, kept callable for real A/B
    comparison."""
    f0, _voiced_flag, _voiced_prob = librosa.pyin(y, fmin=_PYIN_FMIN, fmax=_PYIN_FMAX, sr=sr)
    if f0 is None or len(f0) == 0:
        return np.array([]), np.array([])
    return f0, librosa.times_like(f0, sr=sr)


def crepe_contour(
    y: np.ndarray,
    sr: int,
    *,
    fmin: float = _FMIN_HZ,
    fmax: float = _FMAX_HZ,
    confidence: float = _CREPE_CONFIDENCE,
    hop_length: int = _CREPE_HOP,
) -> tuple[np.ndarray, np.ndarray]:
    """Real per-frame f0 (NaN when periodicity is below `confidence`) + frame
    times via `torchcrepe`'s CREPE 'full' model on GPU when CUDA is available,
    else CPU. Raises `ImportError` when torchcrepe isn't installed.

    The single device/predict codepath for CREPE in this package; callers
    pass their own pitch range/confidence/hop rather than a second copy.
    `_crepe_contour` is the voice-range wrapper.
    """
    import torch
    import torchcrepe

    from .device import torch_device

    audio = torch.from_numpy(np.ascontiguousarray(y, dtype=np.float32)).unsqueeze(0)
    pitch, periodicity = torchcrepe.predict(
        audio, sr, hop_length=hop_length, fmin=fmin, fmax=fmax,
        model="full", batch_size=1024, device=torch_device(),
        return_periodicity=True,
    )
    pitch = pitch.squeeze(0).detach().cpu().numpy().astype(float)
    periodicity = periodicity.squeeze(0).detach().cpu().numpy()
    f0 = np.where(periodicity >= confidence, pitch, np.nan)
    times = np.arange(f0.size) * (hop_length / sr)
    return f0, times


def _crepe_contour(y: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Vocal-range f0 contour -- thin wrapper over `crepe_contour` with this
    module's own voice defaults, kept under its original name."""
    return crepe_contour(y, sr)


def extract_vocal_melody(
    flac: str | Path, cache_dir: str | Path, backend: str = "crepe",
) -> list[dict]:
    """Real vocal MELODY as a note-onset list -- `(time, midi_pitch,
    duration)` per note. Pitch and timing ONLY: this function has no
    access to, and never reads, writes, logs, or returns any lyric text.

    Pipeline (deliberately simple, no invented transcription engine):
      1. read the cached demucs `vocals.wav` (never re-separate);
      2. a real per-frame f0 contour -- `_crepe_contour` (torchcrepe CREPE,
         the default) or `_pyin_contour` (librosa.pyin, the previous
         tracker, selectable for real A/B comparison); unvoiced frames are
         NaN;
      3. `librosa.onset.onset_detect` for real note-onset boundaries, then
         onset-then-hold: each onset's pitch is the median voiced f0 until
         the next onset, and its duration is that hold; an onset whose
         window has no voiced frame is an honest rest and is dropped.

    The output shape is byte-for-byte the same regardless of backend, so
    nothing downstream changes. `backend` must be `"crepe"` or `"pyin"`.
    """
    if backend not in {"crepe", "pyin"}:
        raise ValueError(f"backend must be 'crepe' or 'pyin', got {backend!r}")
    flac = Path(flac)
    cache_dir = Path(cache_dir)
    vocals = _find_vocals(flac, cache_dir)
    if vocals is None:
        return []

    sr = _CREPE_SR if backend == "crepe" else _ANALYSIS_SR
    y, sr = librosa.load(str(vocals), sr=sr, mono=True)
    if y.size == 0:
        return []

    if backend == "crepe":
        try:
            f0, times = _crepe_contour(y, sr)
        except ImportError:
            # Real, honest fallback: torchcrepe not installed here -- keep
            # the pipeline working with the previous tracker rather than
            # failing the whole extraction.
            print("torchcrepe not installed -- falling back to pyin")
            y, sr = librosa.load(str(vocals), sr=_ANALYSIS_SR, mono=True)
            f0, times = _pyin_contour(y, sr)
    else:
        f0, times = _pyin_contour(y, sr)

    if f0 is None or len(f0) == 0:
        return []
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")

    notes: list[dict] = []
    for i, start in enumerate(onsets):
        start = float(start)
        if i + 1 < len(onsets):
            end = float(onsets[i + 1])
        elif times.size:
            end = float(times[-1])
        else:
            continue
        if end <= start:
            continue
        window = (times >= start) & (times < end)
        pitches = f0[window]
        pitches = pitches[np.isfinite(pitches)]
        if pitches.size == 0:
            continue
        midi = int(round(float(librosa.hz_to_midi(float(np.median(pitches))))))
        notes.append({
            "time": round(start, 3),
            "midi_pitch": midi,
            "duration": round(end - start, 3),
        })
    return notes


def build_vocal_melody(lab_root: Path, rows: list[dict], cache: Path) -> dict:
    """For every row in `data/sections.jsonl`, extract that track's real
    vocal melody from its cached demucs vocals stem (once per track), then
    cut the note list to each human-labeled `[start, end]` window -- the
    same alignment `build_drum_patterns` uses.

    Writes one JSON line per section to `data/vocal_melody.jsonl`:
    `{"album","track","role","notes":[{"time","midi_pitch","duration"}]}`.
    Pitch and timing only -- no text/lyric/word field exists in this schema
    or anywhere in this pipeline. A section whose track has no cached
    vocals stem, or whose window contains no onsets, is still written with
    an empty `notes` list -- an honest gap, not a dropped row.
    """
    from .holdout import ensure_holdout, split_for
    from .schema import load_section_rows

    holdout = ensure_holdout(lab_root, rows)
    sec_path = lab_root / "data" / "sections.jsonl"
    sections = load_section_rows(sec_path)
    by_song: dict[tuple[str, str], list[dict]] = {}
    for s in sections:
        by_song.setdefault((s.get("album") or "", s.get("track") or ""), []).append(s)

    row_by = {(r.get("album") or "", r.get("track") or ""): r for r in rows}

    out_path = lab_root / "data" / "vocal_melody.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_sections = 0
    with_notes = 0
    empty = 0
    no_stem = 0
    analyzed: dict[str, list[dict]] = {}
    out_rows: list[dict] = []

    for (album, track), segs in sorted(by_song.items()):
        r = row_by.get((album, track))
        if not r:
            hits = [row for (a, t), row in row_by.items() if t == track]
            r = hits[0] if len(hits) == 1 else None
        flac = None
        if r:
            fp = r.get("flac_path") or r.get("flac") or ""
            flac = Path(fp) if fp else None
        vocals = _find_vocals(flac, cache) if flac else None
        if not vocals:
            print("SKIP vocals", track, "no cached vocals stem")
        elif str(vocals) not in analyzed:
            analyzed[str(vocals)] = extract_vocal_melody(flac, cache)

        all_notes = analyzed.get(str(vocals), []) if vocals else []
        for seg in segs:
            start, end = float(seg["start"]), float(seg["end"])
            notes = [n for n in all_notes if start <= n["time"] < end]
            rec = {
                "album": album,
                "track": track,
                "role": seg.get("role"),
                "split": split_for(album, track, holdout),
                "notes": notes,
            }
            out_rows.append(rec)
            n_sections += 1
            if not vocals:
                no_stem += 1
                empty += 1
            elif notes:
                with_notes += 1
            else:
                empty += 1
            print("VOCALS", track, seg.get("role"), len(notes))

    from .schema import write_jsonl_atomic

    write_jsonl_atomic(out_path, out_rows)
    return {
        "sections": n_sections,
        "with_notes": with_notes,
        "empty": empty,
        "no_stem": no_stem,
        "out": str(out_path),
    }
