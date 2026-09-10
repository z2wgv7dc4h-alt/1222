"""Real, format-agnostic reference-song analysis: parses a real MIDI,
Guitar Pro, or audio file and measures its own real tonal/interval
character (per-track key estimate, interval-vocabulary percentages,
register, note density) -- never reproduces the source's actual notes or
melody in any output, only extracts statistical summaries, per this
project's own established "pattern analysis, never reproduction"
discipline (god-tier-metal-scope.md sec.14.2 item 12).

Found necessary via direct user listening feedback ("you're just
guessing"): ad hoc analysis of one real reference MIDI measurably
improved generated output the same session. This module makes that real
technique tested and reusable for every future reference the user
supplies, accumulating into a real local corpus
(`engine/data/reference_corpus.json`) rather than a fresh one-off script
each time -- the same real cache pattern `midi_vocab.py` already
established for the drum-fill corpus (`extract_*` -> `add_reference`/
`build_vocabulary` -> a committed JSON cache of DERIVED STATISTICS only,
never the source's own notes).

Three real input formats, one shared real analysis core:
  - MIDI (`pretty_midi`) -- the format used for this session's own
    real reference.
  - Guitar Pro `.gp*` (`pyguitarpro`) -- more precise than audio
    transcription (exact fret-resolved pitch, `Note.realValue`) and, per
    a real web search, far more available for a specific song than a raw
    MIDI transcription.
  - Audio (`librosa` via `audio_vocab.py`) -- tempo/structural stats
    always; a real note-level vocabulary too when `basic_pitch` (already
    installed in this environment) can transcribe it, honestly flagged
    `"transcription": "structural_only"` when it can't rather than
    silently claiming note-level precision it doesn't have.

Key estimation reuses `audio_vocab.py`'s own real Krumhansl-Schmuckler
profile arrays directly (not duplicated) -- the same real technique,
just correlated against a symbolic (MIDI/GP note) pitch-class histogram
instead of audio chroma.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from audio_vocab import _MAJOR_PROFILE, _MINOR_PROFILE, analyze_track, estimate_key, load_audio

try:
    import pretty_midi
except ImportError as exc:  # pragma: no cover - exercised only when pretty_midi is missing
    raise ImportError(
        "reference_vocab requires the 'pretty_midi' package. It is listed in "
        "engine/requirements.txt -- install with `pip install pretty_midi`."
    ) from exc

try:
    import guitarpro
except ImportError:  # pragma: no cover - exercised only when pyguitarpro is missing
    guitarpro = None

__all__ = [
    "analyze_midi_reference",
    "analyze_gp_reference",
    "analyze_audio_reference",
    "add_reference",
    "load_reference_corpus",
    "build_preset_from_corpus",
]

_ENGINE_ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS_PATH = _ENGINE_ROOT / "data" / "reference_corpus.json"

# A track with fewer real notes than this is too sparse to measure
# anything meaningful from (a cue track, an empty placeholder, etc).
_MIN_TRACK_NOTES = 8

# Guitar Pro's own internal duration-to-tick convention, confirmed
# directly against a real installed pyguitarpro: Duration(value=4)
# (a quarter note) has `.time == 960`, i.e. 960 ticks/quarter-note --
# the standard MIDI-style PPQ, not guessed.
_GP_TICKS_PER_QUARTER = 960.0

_GP_ROLE_TRACK_NAME_HINTS = ("drum", "percussion")


def _krumhansl_correlate(pitch_class_weights: np.ndarray) -> tuple[int, str, float]:
    """Real key-profile correlation -- the SAME real profiles/technique
    `audio_vocab.estimate_key` already uses against audio chroma, applied
    here to a symbolic (MIDI/GP note) pitch-class histogram instead of
    audio chroma. Returns `(root_pitch_class 0-11, "major"|"minor",
    confidence)`."""
    best_score, best_root, best_mode = -2.0, 0, "major"
    for shift in range(12):
        major_score = float(np.corrcoef(pitch_class_weights, np.roll(_MAJOR_PROFILE, shift))[0, 1])
        minor_score = float(np.corrcoef(pitch_class_weights, np.roll(_MINOR_PROFILE, shift))[0, 1])
        if major_score > best_score:
            best_score, best_root, best_mode = major_score, shift, "major"
        if minor_score > best_score:
            best_score, best_root, best_mode = minor_score, shift, "minor"
    return best_root, best_mode, round(best_score, 4)


def _interval_vocab_from_pitches(pitches: list[int], root_pc: int) -> dict[int, float]:
    """Real interval-vocabulary percentages (0-11, relative to
    `root_pc`) from a real list of MIDI pitches -- the exact real
    technique used ad hoc against the user's own reference MIDI this
    session, now shared by every input format."""
    if not pitches:
        return {}
    counts: dict[int, int] = {}
    for p in pitches:
        interval = (p - root_pc) % 12
        counts[interval] = counts.get(interval, 0) + 1
    total = sum(counts.values())
    return {k: round(v / total * 100, 1) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])}


def _role_guess(pitches: list[int], root_pct: float, notes_per_sec: float) -> str:
    """Real, documented heuristic distinguishing a wide melodic riff from
    a tight pedal/chug doubler from a sparse lead/harmony line -- the
    same real distinction found ad hoc in the user's own reference MIDI
    (Guitar 1/Guitar 2/Harmony) this session, made explicit and reusable.
    Not a claim of exhaustive arrangement classification -- "unknown"
    when nothing clears a real threshold, never a forced guess."""
    if not pitches:
        return "unknown"
    register_span = max(pitches) - min(pitches)
    if root_pct >= 85.0 and register_span <= 15:
        return "pedal"
    if notes_per_sec <= 2.5 and register_span >= 12:
        return "lead"
    if register_span >= 12:
        return "riff"
    return "unknown"


def _track_summary(name: str, pitches: list[int], duration_s: float) -> dict[str, Any] | None:
    if len(pitches) < _MIN_TRACK_NOTES or duration_s <= 0:
        return None
    weights = np.zeros(12)
    for p in pitches:
        weights[p % 12] += 1
    root_pc, mode, confidence = _krumhansl_correlate(weights)
    vocab = _interval_vocab_from_pitches(pitches, root_pc)
    # float(...) throughout: `duration_s` can arrive as a numpy scalar
    # (pretty_midi/librosa both use numpy internally) -- every value here
    # must be a plain, real JSON-safe Python type, never a numpy scalar
    # that happens to compare equal but isn't actually the same type.
    notes_per_sec = round(float(len(pitches) / duration_s), 2)
    return {
        "name": name,
        "role_guess": _role_guess(pitches, vocab.get(0, 0.0), notes_per_sec),
        "key_root_pc": int(root_pc),
        "key_mode": mode,
        "key_confidence": confidence,
        "interval_vocab_pct": vocab,
        "register_low": int(min(pitches)),
        "register_high": int(max(pitches)),
        "notes_per_sec": notes_per_sec,
    }


def analyze_midi_reference(path: str | Path) -> dict[str, Any]:
    """Real per-track analysis of a MIDI reference file -- exactly the ad
    hoc technique used against the user's own reference MIDI this
    session, now real and tested."""
    pm = pretty_midi.PrettyMIDI(str(path))
    duration_s = float(pm.get_end_time())
    tracks = []
    for i, inst in enumerate(pm.instruments):
        if inst.is_drum or not inst.notes:
            continue
        pitches = [n.pitch for n in inst.notes]
        summary = _track_summary(inst.name or f"track_{i}", pitches, duration_s)
        if summary is not None:
            tracks.append(summary)
    try:
        tempo_bpm = float(pm.estimate_tempo())
    except ValueError:
        # pretty_midi's own real contract: needs at least 2 notes across
        # the whole file to estimate a tempo at all -- a real, honest
        # "unknown" for a too-sparse file, not a crash or a fabricated
        # default.
        tempo_bpm = None

    return {
        "source": Path(path).name,
        "format": "midi",
        "tempo_bpm": tempo_bpm,
        "duration_s": round(duration_s, 1),
        "tracks": tracks,
    }


def analyze_gp_reference(path: str | Path) -> dict[str, Any]:
    """Real per-track analysis of a Guitar Pro reference file. Guitar Pro
    encodes exact fret-resolved pitches (`Note.realValue`, string open
    pitch + fret -- no pitch-detection uncertainty at all, unlike audio),
    making this the most precise of the three real input formats when a
    specific song's tab is available."""
    if guitarpro is None:
        raise ImportError(
            "analyze_gp_reference requires the 'guitarpro' (pyguitarpro) package -- "
            "install with `pip install pyguitarpro`."
        )
    song = guitarpro.parse(str(path))
    tempo_bpm = float(song.tempo)
    seconds_per_tick = 60.0 / tempo_bpm / _GP_TICKS_PER_QUARTER

    tracks = []
    song_duration_s = 0.0
    for track in song.tracks:
        if track.isPercussionTrack or any(hint in (track.name or "").lower() for hint in _GP_ROLE_TRACK_NAME_HINTS):
            continue
        pitches: list[int] = []
        elapsed_ticks = 0.0
        for measure in track.measures:
            for voice in measure.voices:
                for beat in voice.beats:
                    elapsed_ticks += beat.duration.time
                    if beat.status == guitarpro.BeatStatus.normal:
                        pitches.extend(note.realValue for note in beat.notes)
        duration_s = elapsed_ticks * seconds_per_tick
        song_duration_s = max(song_duration_s, duration_s)
        summary = _track_summary(track.name or f"track_{track.number}", pitches, duration_s)
        if summary is not None:
            tracks.append(summary)

    return {
        "source": Path(path).name,
        "format": "gp",
        "tempo_bpm": tempo_bpm,
        "duration_s": round(song_duration_s, 1),
        "tracks": tracks,
    }


def analyze_audio_reference(path: str | Path, drums_path: str | Path | None = None) -> dict[str, Any]:
    """Real analysis of an audio reference file. Always real tempo/
    structural stats (`audio_vocab.analyze_track`), a real rhythm-pattern
    classification (`audio_vocab.guitar_rhythm_pattern` -- straight/
    gallop/syncopated from onset timing, never pitch), and the real
    per-section dynamic/density curve `analyze_track` already computes
    internally (previously measured but discarded here). Attempts a real
    note-level vocabulary too via `audio_vocab.transcribe_and_split_
    registers` (Spotify's real `basic_pitch` polyphonic transcription) --
    honestly flags `"transcription": "structural_only"` (never silently
    claims note-level precision) when that dependency isn't available or
    transcription fails for this file.

    `drums_path`, when given (e.g. a real `demucs` drum stem, isolated
    from `path`'s own guitar/bass content), also runs `audio_vocab.
    classify_drum_onsets` for a real per-role (KICK/SNARE/HIHAT_OR_CYMBAL)
    onset-percentage breakdown -- `drum_role_pct` is `None`, not
    fabricated, when no drum stem is supplied."""
    from audio_vocab import guitar_rhythm_pattern

    y, sr = load_audio(path)
    duration_s = len(y) / sr
    track_stats = analyze_track(path)
    key = estimate_key(y, sr)
    rhythm_pattern = guitar_rhythm_pattern(y, sr)["pattern"]

    drum_role_pct: dict[str, float] | None = None
    if drums_path is not None:
        from audio_vocab import classify_drum_onsets

        drum_y, drum_sr = load_audio(drums_path)
        onsets = classify_drum_onsets(drum_y, drum_sr)
        if onsets:
            role_counts: dict[str, int] = {}
            for onset in onsets:
                role_counts[onset["role"]] = role_counts.get(onset["role"], 0) + 1
            total_onsets = sum(role_counts.values())
            drum_role_pct = {role: round(count / total_onsets * 100, 1) for role, count in role_counts.items()}

    tracks: list[dict[str, Any]] = []
    transcription = "structural_only"
    try:
        from audio_vocab import transcribe_and_split_registers

        registers = transcribe_and_split_registers(path)
        transcription = "full"
        # transcribe_and_split_registers already splits by register into
        # "rhythm" (the real pedal/riff layer) and "lead" -- reuse ITS
        # own real labels directly rather than re-guessing a role, and
        # note it returns pitch-CLASS counts (mod-12), not absolute
        # pitches, so register_low/high aren't meaningful here and are
        # honestly omitted rather than fabricated.
        for layer_name, role in (("rhythm", "riff"), ("lead", "lead")):
            layer = registers.get(layer_name) or {}
            n_notes = layer.get("n_notes", 0)
            if n_notes < _MIN_TRACK_NOTES:
                continue
            pc_counts = layer.get("pitch_class_counts") or {}
            weights = np.zeros(12)
            for pc, count in pc_counts.items():
                weights[int(pc) % 12] = count
            root_pc, mode, confidence = _krumhansl_correlate(weights)
            total = sum(pc_counts.values()) or 1
            vocab: dict[int, float] = {}
            for pc, count in pc_counts.items():
                interval = (int(pc) - root_pc) % 12
                vocab[interval] = vocab.get(interval, 0.0) + count
            vocab = {k: round(v / total * 100, 1) for k, v in sorted(vocab.items(), key=lambda kv: -kv[1])}
            tracks.append({
                "name": layer_name,
                "role_guess": role,
                "key_root_pc": root_pc,
                "key_mode": mode,
                "key_confidence": confidence,
                "interval_vocab_pct": vocab,
                "notes_per_sec": layer.get("density_per_s", 0.0),
            })
    except ImportError:
        pass

    return {
        "source": Path(path).name,
        "format": "audio",
        "tempo_bpm": track_stats["tempo_bpm"],
        "duration_s": round(duration_s, 1),
        "structural_key": key,
        "tonal_descriptor": track_stats["tonal_descriptor"],
        "transcription": transcription,
        "rhythm_pattern": rhythm_pattern,
        "section_density_curve": track_stats["section_density_curve"],
        "drum_role_pct": drum_role_pct,
        "tracks": tracks,
    }


def _analyze_by_extension(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in (".mid", ".midi"):
        return analyze_midi_reference(path)
    if suffix in (".gp", ".gp3", ".gp4", ".gp5", ".gpx"):
        return analyze_gp_reference(path)
    if suffix in (".mp3", ".wav", ".flac", ".ogg", ".m4a"):
        return analyze_audio_reference(path)
    raise ValueError(f"unsupported reference file type: {suffix!r}")


def add_reference(
    path: str | Path,
    corpus_path: str | Path = DEFAULT_CORPUS_PATH,
    drums_path: str | Path | None = None,
) -> dict[str, Any]:
    """Analyze one real reference file and add/update its entry in the
    real local corpus cache (`engine/data/reference_corpus.json` by
    default) -- the real accumulation the user asked for ("feed you
    songs and you learn from that"). Keyed by filename, so re-feeding the
    same file updates rather than duplicates its entry.

    `drums_path` (audio references only) passes a real isolated drum stem
    (e.g. from `demucs`) through to `analyze_audio_reference` for real
    per-role onset classification; ignored for MIDI/GP references, which
    have no such stem concept."""
    path = Path(path)
    if drums_path is not None:
        result = analyze_audio_reference(path, drums_path=drums_path)
    else:
        result = _analyze_by_extension(path)
    corpus = load_reference_corpus(corpus_path)
    corpus[path.name] = result
    corpus_path = Path(corpus_path)
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path.write_text(json.dumps(corpus, indent=2))
    return result


def load_reference_corpus(corpus_path: str | Path = DEFAULT_CORPUS_PATH) -> dict[str, Any]:
    """Load the real local reference corpus cache. Returns `{}` if it has
    never been built yet -- a missing cache is a real, valid "no
    references fed yet" state, not an error."""
    corpus_path = Path(corpus_path)
    if not corpus_path.exists():
        return {}
    return json.loads(corpus_path.read_text())


def _nearest_scale(interval_weights: dict[int, float]) -> str:
    """Real, simple scale match: scores every candidate scale in
    `scales.SCALES` by how much of `interval_weights`' total weight falls
    on that scale's own real interval set, picks the best-covering one.
    `scales.py` has no existing scale-matcher (confirmed) -- this is real
    new logic, not reuse, and it's an honest, simple heuristic, not a
    claim of musicological rigor. "chromatic" is excluded (it trivially
    "covers" everything, which would make it always win); ties broken by
    preferring the SMALLER (more specific) scale."""
    from scales import SCALES

    total = sum(interval_weights.values()) or 1.0
    best_name = "minor"
    best_coverage = -1.0
    best_size = 99
    for name, intervals in SCALES.items():
        if name == "chromatic":
            continue
        covered = sum(w for i, w in interval_weights.items() if i in intervals)
        coverage = covered / total
        size = len(intervals)
        if coverage > best_coverage or (coverage == best_coverage and size < best_size):
            best_name, best_coverage, best_size = name, coverage, size
    return best_name


def _aggregate_role_vocab(corpus: dict[str, Any], role: str) -> tuple[dict[int, float], list[dict[str, Any]]]:
    """Real, shared aggregation: averages `interval_vocab_pct` across
    every corpus entry's own real track matching `role` (one vote per
    SONG, not per note -- the same real discipline `build_preset_from_
    corpus` has always used for its main riff vocab, now shared so a
    second role, e.g. `"lead"`, calibrates identically rather than via a
    second hand-copied loop). Returns `(aggregate, matching_tracks)` --
    an empty `aggregate` and `[]` when no track matches, never raises
    (the caller decides whether that's fatal for ITS particular use)."""
    matching_tracks = []
    for entry in corpus.values():
        for track in entry.get("tracks", []):
            if track["role_guess"] == role:
                matching_tracks.append(track)
                break  # one real track per song, not every matching-role track in it
    if not matching_tracks:
        return {}, []
    aggregate: dict[int, float] = {}
    for track in matching_tracks:
        for interval, pct in track["interval_vocab_pct"].items():
            aggregate[int(interval)] = aggregate.get(int(interval), 0.0) + pct
    aggregate = {k: round(v / len(matching_tracks), 1) for k, v in aggregate.items()}
    return aggregate, matching_tracks


def build_preset_from_corpus(
    preset_id: str,
    description: str,
    tuning_key: str,
    output_dir: str | Path | None = None,
    track_role: str = "riff",
    corpus: dict[str, Any] | None = None,
) -> "Preset":
    """Real preset calibration from every reference fed so far (or a
    specific `corpus` dict, e.g. for testing): averages `interval_vocab_
    pct` across every corpus entry's own real track matching `track_
    role` (weighted equally per SONG, not per note, so one long/dense
    reference can't silently dominate the aggregate), picks the best-
    fitting real scale, and writes a real preset JSON file into
    `engine/presets/` via the exact schema `presets.validate_preset`
    already enforces -- automatically discoverable afterward through
    `load_all_presets`'s own real glob, no separate registration step.
    Raises `ValueError` if no corpus entry has a real track matching
    `track_role` -- never fabricates a preset from nothing."""
    from presets import PRESETS_DIR, Preset, Vocab, load_tunings, validate_preset

    corpus = corpus if corpus is not None else load_reference_corpus()
    aggregate, matching_tracks = _aggregate_role_vocab(corpus, track_role)
    if not matching_tracks:
        raise ValueError(f"no corpus reference has a real '{track_role}' track yet")

    modes = [t["key_mode"] for t in matching_tracks]
    scale_name = "major" if modes.count("major") > modes.count("minor") else "minor"
    scale_name = _nearest_scale(aggregate) if aggregate else scale_name

    # Real pedal-bias calibration from every corpus entry's own real
    # "pedal" track (the second-guitar/chug-doubler role `_role_guess`
    # already detects) -- this data has been sitting in the corpus since
    # X.17.1's real reference-MIDI analysis, just never consumed here.
    # Root-heaviness (interval 0's own pct) maps directly onto
    # `preset.pedal`'s existing 0-1 root-bias scale. Falls back to the
    # original 0.5 default, not a fabricated number, when no corpus entry
    # has a real pedal track yet.
    pedal_tracks = []
    for entry in corpus.values():
        for track in entry.get("tracks", []):
            if track["role_guess"] == "pedal":
                pedal_tracks.append(track)
                break
    if pedal_tracks:
        # `interval_vocab_pct`'s keys are real ints in a freshly-analyzed
        # entry but become real JSON STRING keys once loaded back from
        # `load_reference_corpus` (the same real JSON round-trip effect
        # `test_add_reference_and_load_reference_corpus_round_trip`
        # already documents) -- `int(k)` every key rather than looking up
        # the bare int 0 directly, or this silently finds nothing on any
        # corpus loaded from disk (confirmed: it did, on the real 31-song
        # corpus, before this fix -- avg_root_pct computed as 0.0 for
        # every real pedal track).
        avg_root_pct = sum(
            {int(k): v for k, v in t["interval_vocab_pct"].items()}.get(0, 0.0) for t in pedal_tracks
        ) / len(pedal_tracks)
        pedal_bias = round(min(1.0, avg_root_pct / 100.0), 2)
    else:
        pedal_bias = 0.5

    # Real, SEPARATE lead-guitar vocab calibration from every corpus
    # entry's own real "lead" track (basic_pitch's transcribed lead
    # register for audio references, `_role_guess`'s sparse/wide/high
    # heuristic for MIDI/GP references) -- previously measured and
    # stored in the corpus but never consumed anywhere: solo/chorus-lead
    # generation reused the RIFF vocab wholesale. `None` when the corpus
    # has no real lead track yet, never a fabricated vocab -- callers
    # (song.py) already fall back to the main riff vocab in that case.
    lead_aggregate, lead_tracks = _aggregate_role_vocab(corpus, "lead")
    lead_vocab = Vocab(weights=lead_aggregate, motion=0.55) if lead_tracks else None

    preset = Preset(
        id=preset_id,
        description=description,
        tuning_key=tuning_key,
        scale=scale_name,
        dissonance=0.3,
        bpm=int(round(sum(e.get("tempo_bpm") or 152 for e in corpus.values()) / max(1, len(corpus)))),
        bars=8,
        feel="bounce",
        open_chance=0.5,
        octave_stab=True,
        kick="euclid",
        vocab=Vocab(weights=aggregate, motion=0.45),
        pedal=pedal_bias,
        lead_vocab=lead_vocab,
    )

    directory = Path(output_dir) if output_dir is not None else PRESETS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    out_path = directory / f"{preset_id}.json"
    payload = {
        "id": preset.id,
        "description": preset.description,
        "tuning_key": preset.tuning_key,
        "scale": preset.scale,
        "dissonance": preset.dissonance,
        "bpm": preset.bpm,
        "bars": preset.bars,
        "feel": preset.feel,
        "open_chance": preset.open_chance,
        "octave_stab": preset.octave_stab,
        "kick": preset.kick,
        "pedal": preset.pedal,
        "vocab": {"weights": {str(k): v for k, v in preset.vocab.weights.items()}, "motion": preset.vocab.motion},
    }
    if preset.lead_vocab is not None:
        payload["lead_vocab"] = {
            "weights": {str(k): v for k, v in preset.lead_vocab.weights.items()},
            "motion": preset.lead_vocab.motion,
        }
    validate_preset(payload, load_tunings(), expected_id=preset_id)
    out_path.write_text(json.dumps(payload, indent=2))
    return preset
