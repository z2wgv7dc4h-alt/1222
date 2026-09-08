"""Real-audio structural/tonal vocabulary -- the audio-analogue of
`midi_vocab.py`'s MIDI-corpus mining.

Per CLAUDE.md's law ("Grid is the writer. Audio models are paint after the
score."), nothing here writes or transcribes notes. This module extracts
STATISTICAL/STRUCTURAL features from a real audio file -- tempo, a
harmonic/percussive rhythm-density split, and coarse tonal-brightness
descriptors -- as reference DATA a preset or generation parameter can be
informed by, exactly the same role the MIDI-vocabulary cache already plays.
It never transcribes a melody, chord, or riff, and never stores or
reproduces the audio itself; only small numeric summaries are kept.

Uses `librosa` (BSD-licensed) for decoding and analysis -- added as a
project dependency alongside `mido`, same rationale: the pragmatic,
well-established choice over hand-rolling DSP. `analyze_track` runs on any
audio file directly (using librosa's own harmonic/percussive split as a
cheap proxy for "drum-like" vs "guitar-like" content).

Optional, not a hard dependency: for real per-instrument stems (actual
drums vs bass vs vocals vs other, rather than a harmonic/percussive
approximation), run Meta's open-source `demucs` model LOCALLY first --
`python -m demucs --two-stems=drums <file>` -- then call `analyze_track` on
each resulting stem file separately. `demucs` is intentionally not added to
requirements.txt (it pulls in PyTorch, a heavy dependency this project
doesn't otherwise need) -- install it ad hoc (`pip install demucs`) only
when a real separation pass is wanted. Never upload audio to a third-party
"online demucs" site for this -- run the real model locally instead, so
the file never leaves the machine.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

try:
    import librosa
except ImportError as exc:  # pragma: no cover - exercised only when librosa is missing
    raise ImportError(
        "audio_vocab requires the 'librosa' package. It is listed in "
        "engine/requirements.txt -- install with `pip install librosa`."
    ) from exc

__all__ = [
    "load_audio",
    "analyze_track",
    "tonal_descriptor",
    "estimate_key",
    "structural_segments",
    "energy_curve",
    "tempo_stability",
    "classify_drum_onsets",
    "guitar_rhythm_pattern",
    "transcribe_and_split_registers",
]

# Krumhansl-Schmuckler key profiles: relative perceived stability of each
# semitone above a tonic, for major and (harmonic-leaning) minor. Standard,
# widely-published profiles -- not derived from any specific copyrighted
# recording. `estimate_key` correlates a track's own chroma content against
# all 24 rotations of these two profiles and reports the best match.
_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_PITCH_CLASS_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Spectral-centroid thresholds (Hz) for a coarse, documented brightness
# label -- not a claim of precision, just a consistent bucketing so results
# are comparable across tracks. Typical high-gain metal rhythm tone sits
# roughly in the 1.5-3kHz "scooped/dark" to "mid-forward" range; anything
# brighter usually reflects cymbals/leads dominating the harmonic split
# rather than the rhythm tone itself.
_DARK_CENTROID_HZ = 1800.0
_BRIGHT_CENTROID_HZ = 3200.0


def load_audio(path: str | Path, sr: int | None = None) -> tuple[np.ndarray, int]:
    """Decode an audio file to a mono waveform. `sr=None` keeps the file's
    native sample rate rather than resampling, matching `librosa.load`'s
    own convention."""
    y, sample_rate = librosa.load(str(path), sr=sr, mono=True)
    return y, sample_rate


def tonal_descriptor(mean_centroid_hz: float) -> str:
    """A coarse, documented brightness label from a mean spectral centroid
    -- "dark/scooped", "balanced", or "bright/aggressive". A label, not a
    claim of amp/pedal identification (that needs a trained classifier,
    not spectral statistics -- see the module docstring)."""
    if mean_centroid_hz < _DARK_CENTROID_HZ:
        return "dark/scooped"
    if mean_centroid_hz > _BRIGHT_CENTROID_HZ:
        return "bright/aggressive"
    return "balanced"


def estimate_key(y: np.ndarray, sr: int) -> dict[str, Any]:
    """Estimate an overall tonal center via Krumhansl-Schmuckler key-profile
    correlation against the track's own averaged chroma vector.

    This is a coarse, well-known statistical technique -- it correlates
    HOW MUCH energy sits on each pitch class overall against two known
    profiles (major/minor), it does not transcribe a melody or chord
    progression. Distorted, palm-muted metal guitar makes fine-grained
    chord-by-chord analysis unreliable anyway; an overall tonal-center
    estimate is the honest level of detail available here.

    Returns `{"root": str, "mode": "major"|"minor", "confidence": float}`
    -- `confidence` is the winning correlation coefficient (roughly 0-1,
    can be low/ambiguous for something as harmonically dense as distorted
    metal -- report it, don't hide the uncertainty).
    """
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mean_chroma = np.mean(chroma, axis=1)

    best_score = -2.0
    best_root = 0
    best_mode = "major"
    for shift in range(12):
        major_score = float(np.corrcoef(mean_chroma, np.roll(_MAJOR_PROFILE, shift))[0, 1])
        minor_score = float(np.corrcoef(mean_chroma, np.roll(_MINOR_PROFILE, shift))[0, 1])
        if major_score > best_score:
            best_score, best_root, best_mode = major_score, shift, "major"
        if minor_score > best_score:
            best_score, best_root, best_mode = minor_score, shift, "minor"

    return {
        "root": _PITCH_CLASS_NAMES[best_root],
        "mode": best_mode,
        "confidence": round(best_score, 4),
    }


def structural_segments(y: np.ndarray, sr: int, n_segments: int = 6) -> list[float]:
    """Real section-boundary timestamps (seconds) via agglomerative
    clustering of a recurrence-weighted MFCC self-similarity matrix --
    i.e. actual detected structural change points, not a naive equal-
    length slice of the track (which is all `analyze_track`'s own
    `section_density_curve` uses). Returns `n_segments - 1` boundary
    times plus 0.0 and the track duration are implied endpoints (not
    included in the returned list)."""
    if n_segments <= 1:
        raise ValueError("n_segments must be > 1")
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    bound_frames = librosa.segment.agglomerative(mfcc, n_segments)
    bound_times = librosa.frames_to_time(bound_frames, sr=sr)
    # agglomerative() includes frame 0; drop it so the result is genuine
    # interior boundaries only.
    return [round(float(t), 3) for t in bound_times if t > 0.0]


def energy_curve(y: np.ndarray, sr: int, n_sections: int = 8) -> list[float]:
    """RMS loudness/energy per equal-length section, relative to the
    track's own overall RMS (1.0 = average, >1.0 = louder/more energetic
    than average -- e.g. a breakdown, <1.0 = quieter, e.g. an intro or
    clean interlude). Same relative-curve convention as `analyze_track`'s
    `section_density_curve`, but measuring loudness rather than onset rate
    -- directly comparable to `theory.arc()`'s "energy" field, which this
    is meant to validate/inform, not replace."""
    if n_sections <= 0:
        raise ValueError("n_sections must be > 0")
    rms = librosa.feature.rms(y=y)[0]
    overall = float(np.mean(rms))
    if overall <= 0:
        return [0.0] * n_sections
    frames_per_section = max(1, len(rms) // n_sections)
    curve = []
    for i in range(n_sections):
        lo = i * frames_per_section
        hi = len(rms) if i == n_sections - 1 else (i + 1) * frames_per_section
        window = rms[lo:hi]
        window_mean = float(np.mean(window)) if len(window) else 0.0
        curve.append(round(window_mean / overall, 4))
    return curve


def tempo_stability(y: np.ndarray, sr: int, n_windows: int = 6) -> dict[str, Any]:
    """Whether the track holds one tempo throughout or actually changes --
    a real per-window local-tempo estimate (`librosa.feature.tempo` on
    successive slices of the signal), not just the single global estimate
    `analyze_track` reports. Directly relevant to this project's own
    internal tempo-curve feature (`structure.tempo_at`, P6.7) -- confirms
    whether a REAL reference track holds a constant tempo (matching this
    project's own Reaper-export decision, scope sec.17.5) or genuinely
    ramps/drops.

    Returns `{"window_tempos_bpm": [float, ...], "max_deviation_bpm": float,
    "stable": bool}` -- `stable` is True when every window's tempo is
    within 5 BPM of the track's median (a documented, simple threshold).
    """
    if n_windows <= 0:
        raise ValueError("n_windows must be > 0")
    window_len = max(1, len(y) // n_windows)
    window_tempos = []
    for i in range(n_windows):
        lo = i * window_len
        hi = len(y) if i == n_windows - 1 else (i + 1) * window_len
        segment = y[lo:hi]
        if len(segment) < sr:  # too short a slice for a meaningful estimate
            continue
        t = librosa.feature.tempo(y=segment, sr=sr)
        window_tempos.append(round(float(np.atleast_1d(t)[0]), 2))

    if not window_tempos:
        return {"window_tempos_bpm": [], "max_deviation_bpm": 0.0, "stable": True}

    median_tempo = float(np.median(window_tempos))
    max_deviation = max(abs(t - median_tempo) for t in window_tempos)
    return {
        "window_tempos_bpm": window_tempos,
        "max_deviation_bpm": round(max_deviation, 2),
        "stable": max_deviation <= 5.0,
    }


def classify_drum_onsets(y: np.ndarray, sr: int, window_s: float = 0.05) -> list[dict[str, Any]]:
    """Classify each detected onset in a (ideally isolated) drum signal by
    frequency-band energy at the onset -- a real, honest reconstruction of
    WHICH drum role likely fired, not just how many onsets there were.

    Coarse, documented heuristic (not a trained classifier): low-band
    energy (<150 Hz) dominant -> "KICK"; high-band (>=2000 Hz) dominant ->
    "HIHAT_OR_CYMBAL" (can't reliably split hi-hat from cymbal/ride from
    spectrum alone -- honestly labeled as a combined bucket rather than
    guessing); otherwise (mid-band, broadband snap) -> "SNARE". Directly
    comparable to `drums.py`'s own role vocabulary (KICK/SNARE/HIHAT_*),
    since that's what a real reference track's actual pattern should
    inform.

    Returns `[{"time": float, "role": str, "low_frac": float,
    "mid_frac": float, "high_frac": float}, ...]` -- the energy fractions
    are included so a caller can judge classification confidence, not just
    trust the label blindly.
    """
    onset_times = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    window_len = max(8, int(window_s * sr))
    results: list[dict[str, Any]] = []
    for t in onset_times:
        start = int(t * sr)
        end = min(len(y), start + window_len)
        segment = y[start:end]
        if len(segment) < 8:
            continue
        spectrum = np.abs(np.fft.rfft(segment))
        freqs = np.fft.rfftfreq(len(segment), 1.0 / sr)
        low_e = float(np.sum(spectrum[freqs < 150]))
        mid_e = float(np.sum(spectrum[(freqs >= 150) & (freqs < 2000)]))
        high_e = float(np.sum(spectrum[freqs >= 2000]))
        total = low_e + mid_e + high_e
        if total <= 0:
            continue
        if low_e >= mid_e and low_e >= high_e:
            role = "KICK"
        elif high_e >= mid_e and high_e >= low_e:
            role = "HIHAT_OR_CYMBAL"
        else:
            role = "SNARE"
        results.append({
            "time": round(float(t), 3),
            "role": role,
            "low_frac": round(low_e / total, 3),
            "mid_frac": round(mid_e / total, 3),
            "high_frac": round(high_e / total, 3),
        })
    return results


def guitar_rhythm_pattern(y: np.ndarray, sr: int) -> dict[str, Any]:
    """Classify a guitar/bass signal's rhythmic ONSET pattern -- straight,
    gallop (short-short-long), or syncopated/irregular -- from onset
    TIMING alone, never pitch. This sidesteps the real unreliability of
    pitch detection on distorted/palm-muted metal guitar entirely: you
    don't need to know what note was played to know the riff's rhythm
    was a gallop.

    Method: onset times from the harmonic/percussive-separated percussive
    component (palm-muted chugs read as transient hits even on a
    nominally "harmonic" instrument); classification looks at CONSECUTIVE
    inter-onset-interval ratios (`ioi[i+1] / ioi[i]`), not each interval
    normalized against a single global median -- a genuine short-short-long
    gallop cycle has its short interval AS the median (it's the majority
    value), so comparing each interval to the global median cannot tell
    short from "normal". Consecutive-ratio buckets: "same" (0.8-1.25),
    "double" (1.6-2.5), "half" (0.4-0.65), else "other". "straight" if
    "same" dominates; "gallop" if "double" and "half" both appear in
    real, comparable proportion (the two transitions a short-short-long
    cycle actually produces); "syncopated" otherwise -- documented, simple
    thresholds, not a claim of exhaustive rhythm taxonomy.

    Returns `{"pattern": str, "n_onsets": int, "ratio_counts":
    {"same": int, "double": int, "half": int, "other": int}}`.
    """
    _, percussive = librosa.effects.hpss(y)
    onset_times = librosa.onset.onset_detect(y=percussive, sr=sr, units="time")
    empty_counts = {"same": 0, "double": 0, "half": 0, "other": 0}
    if len(onset_times) < 5:
        return {"pattern": "insufficient_onsets", "n_onsets": int(len(onset_times)), "ratio_counts": empty_counts}

    iois = np.diff(onset_times)
    if np.any(iois <= 0):
        return {"pattern": "insufficient_onsets", "n_onsets": int(len(onset_times)), "ratio_counts": empty_counts}
    consecutive_ratios = iois[1:] / iois[:-1]

    same = np.sum((consecutive_ratios >= 0.8) & (consecutive_ratios <= 1.25))
    double = np.sum((consecutive_ratios >= 1.6) & (consecutive_ratios <= 2.5))
    half = np.sum((consecutive_ratios >= 0.4) & (consecutive_ratios <= 0.65))
    total = len(consecutive_ratios)
    other = total - int(same) - int(double) - int(half)
    counts = {"same": int(same), "double": int(double), "half": int(half), "other": int(other)}

    if total == 0:
        pattern = "insufficient_onsets"
    elif same / total >= 0.7:
        pattern = "straight"
    elif (double + half) / total >= 0.4 and double > 0 and half > 0:
        pattern = "gallop"
    else:
        pattern = "syncopated"

    return {"pattern": pattern, "n_onsets": int(len(onset_times)), "ratio_counts": counts}


def transcribe_and_split_registers(
    path: str | Path,
    start_s: float = 0.0,
    end_s: float | None = None,
    rhythm_cutoff_midi: int = 52,
) -> dict[str, Any]:
    """Real polyphonic audio-to-note transcription (via Spotify's
    `basic-pitch`, MIT-licensed), then split into a RHYTHM-register layer
    (below `rhythm_cutoff_midi`) and a LEAD-register layer (at/above it) --
    guitar chugging and a melodic/lead line read as two different register
    clusters even when mixed in one stem (e.g. demucs' "no_drums" stem).

    This is the deepest, least reliable analysis in this module -- distorted
    metal guitar is genuinely hard for any pitch-detection model, so treat
    individual note pitches as approximate, not ground truth. What IS a
    real, cross-checkable signal: the rhythm layer's dominant pitch class
    should roughly agree with `estimate_key`'s independent chroma-based
    estimate (two different methods agreeing is real evidence, not proof)
    -- and the two layers' density/note-length statistics (rhythm: fast,
    short, narrow pitch-class cluster; lead: slower, longer, wider spread)
    are a meaningful structural signal even when individual notes aren't
    perfectly accurate.

    Optional: requires `basic_pitch` + `pretty_midi` (NOT in
    requirements.txt -- this package's own dependency pins are genuinely
    fragile on newer Python, needed manual dependency resolution to install
    cleanly with the ONNX backend rather than its pinned old TensorFlow
    range; install ad hoc, same posture as `demucs`). Raises `ImportError`
    with a clear message if unavailable, rather than a confusing traceback
    from a missing transitive dependency.

    Returns `{"rhythm": {"n_notes", "density_per_s", "avg_duration_s",
    "pitch_class_counts"}, "lead": {same shape}}`.
    """
    try:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import predict
    except ImportError as exc:
        raise ImportError(
            "transcribe_and_split_registers requires 'basic_pitch' (and its "
            "own dependencies, notably 'pretty_midi'). Not a hard project "
            "dependency -- install ad hoc: pip install basic-pitch pretty-midi "
            "mir-eval resampy onnxruntime six importlib_resources "
            "(the pinned tensorflow<2.15.1 range in basic-pitch's own "
            "requirements has no wheel for newer Python -- basic_pitch "
            "auto-detects and uses its ONNX model instead once tensorflow "
            "is absent, which is the working path)."
        ) from exc

    _, _, note_events = predict(str(path))
    window = [e for e in note_events if start_s <= e[0] and (end_s is None or e[0] <= end_s)]

    def _summarize(notes: list) -> dict[str, Any]:
        if not notes:
            return {"n_notes": 0, "density_per_s": 0.0, "avg_duration_s": 0.0, "pitch_class_counts": {}}
        span = max(1e-9, (end_s if end_s is not None else max(e[1] for e in notes)) - start_s)
        pc_counts: dict[int, int] = {}
        for e in notes:
            pc = int(e[2]) % 12
            pc_counts[pc] = pc_counts.get(pc, 0) + 1
        return {
            "n_notes": len(notes),
            "density_per_s": round(len(notes) / span, 4),
            "avg_duration_s": round(sum(e[1] - e[0] for e in notes) / len(notes), 4),
            "pitch_class_counts": dict(sorted(pc_counts.items(), key=lambda kv: -kv[1])),
        }

    rhythm_notes = [e for e in window if int(e[2]) < rhythm_cutoff_midi]
    lead_notes = [e for e in window if int(e[2]) >= rhythm_cutoff_midi]
    return {"rhythm": _summarize(rhythm_notes), "lead": _summarize(lead_notes)}


def analyze_track(path: str | Path, n_sections: int = 8) -> dict[str, Any]:
    """Analyze one real audio file for structural/tonal vocabulary.

    Returns a small numeric summary -- never the audio itself, never a
    note/chord transcription:

      {"duration_s": float, "tempo_bpm": float, "n_beats": int,
       "percussive_onsets_per_beat": float, "harmonic_onsets_per_beat": float,
       "mean_spectral_centroid_hz": float, "tonal_descriptor": str,
       "section_density_curve": [float, ...]}

    `section_density_curve` splits the track into `n_sections` equal-length
    windows and reports each window's percussive onset rate relative to the
    track's own overall rate (1.0 = average density, >1.0 = denser than
    average, e.g. a breakdown; <1.0 = sparser, e.g. a clean interlude) --
    the audio-analogue of `midi_vocab`'s per-file hits-per-beat, used the
    same way: as a density-informing PARAMETER, never as material to copy.
    """
    if n_sections <= 0:
        raise ValueError("n_sections must be > 0")

    y, sr = load_audio(path)
    duration_s = len(y) / sr

    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    tempo_bpm = float(np.atleast_1d(tempo)[0])
    n_beats = int(len(beats))

    harmonic, percussive = librosa.effects.hpss(y)

    perc_onset_env = librosa.onset.onset_strength(y=percussive, sr=sr)
    perc_onsets = librosa.onset.onset_detect(onset_envelope=perc_onset_env, sr=sr, units="time")
    harm_onset_env = librosa.onset.onset_strength(y=harmonic, sr=sr)
    harm_onsets = librosa.onset.onset_detect(onset_envelope=harm_onset_env, sr=sr, units="time")

    beats_total = max(1, n_beats)
    percussive_onsets_per_beat = len(perc_onsets) / beats_total
    harmonic_onsets_per_beat = len(harm_onsets) / beats_total

    centroid = librosa.feature.spectral_centroid(y=harmonic, sr=sr)
    mean_centroid_hz = float(np.mean(centroid)) if centroid.size else 0.0

    window_s = duration_s / n_sections
    overall_rate = len(perc_onsets) / duration_s if duration_s > 0 else 0.0
    section_density_curve: list[float] = []
    for i in range(n_sections):
        lo, hi = i * window_s, (i + 1) * window_s
        count = sum(1 for t in perc_onsets if lo <= t < hi)
        window_rate = count / window_s if window_s > 0 else 0.0
        relative = (window_rate / overall_rate) if overall_rate > 0 else 0.0
        section_density_curve.append(round(relative, 4))

    return {
        "duration_s": round(duration_s, 3),
        "tempo_bpm": round(tempo_bpm, 2),
        "n_beats": n_beats,
        "percussive_onsets_per_beat": round(percussive_onsets_per_beat, 4),
        "harmonic_onsets_per_beat": round(harmonic_onsets_per_beat, 4),
        "mean_spectral_centroid_hz": round(mean_centroid_hz, 1),
        "tonal_descriptor": tonal_descriptor(mean_centroid_hz),
        "section_density_curve": section_density_curve,
    }
