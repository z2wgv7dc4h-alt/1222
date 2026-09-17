from __future__ import annotations

import sys
from pathlib import Path

import librosa
import numpy as np

# Real cross-package import of the engine's own already-built audio
# vocabulary + riff-bank dataclass -- same sys.path pattern as extract.py's
# `_engine_riff_bank()` / drums_extract.py's `_engine_audio_vocab()`. Never a
# second transcription or delta implementation.
_EPS = 1e-6

# Audio has no notated bar grid, so one fragment is one real 4/4 measure
# (4 quarter-note beats) at the track's own estimated tempo -- the same
# one-bar-per-fragment granularity `riff_bank.extract_fragments_from_file`
# uses (`_FRAGMENT_BARS = 1`).
_BEATS_PER_MEASURE = 4.0
_ANALYSIS_SR = 22050

# The engine's own already-established rhythm/lead register split cutoff
# (`audio_vocab.transcribe_and_split_registers`'s `rhythm_cutoff_midi`
# default). A transcribed riff is the rhythm register.
_RHYTHM_CUTOFF_MIDI = 52


def _engine_modules():
    engine_root = Path(__file__).resolve().parents[4] / "engine"
    if str(engine_root) not in sys.path:
        sys.path.insert(0, str(engine_root))
    import audio_vocab
    import riff_bank

    return audio_vocab, riff_bank


def _find_audio_stem(flac: Path, cache: Path) -> tuple[Path | None, str]:
    """Cached demucs stem best suited to transcription: `no_drums`
    (guitar+bass+other, the ideal real source), else `other`, else none.
    Reads an existing separation; never re-runs demucs."""
    from .stems import find_stem

    for name in ("no_drums", "other"):
        hit = find_stem(flac, cache, name)
        if hit:
            return hit, name
    return None, ""


def _measure_cell_deltas(
    notes: list[tuple[float, float, int]],
    measure_start_s: float,
    measure_len_s: float,
    sec_per_beat: float,
) -> tuple[list[dict], list[int]]:
    """One real measure's `(cell, deltas)` from transcribed notes.

    Reuses `riff_bank`'s own real delta convention verbatim: first note's
    delta is 0, every later delta is the real semitone interval from the
    previous note. Cell durations are real quarter-note beats; gaps between
    notes become real rests, and any trailing span up to the measure end is
    a final rest, so the cell sums to the full measure exactly like a real
    notated bar."""
    cell: list[dict] = []
    deltas: list[int] = []
    prev_pitch: int | None = None
    cursor_s = measure_start_s
    measure_end_s = measure_start_s + measure_len_s
    for onset_s, dur_s, pitch in sorted(notes, key=lambda n: n[0]):
        gap_beats = (onset_s - cursor_s) / sec_per_beat
        if gap_beats > _EPS:
            cell.append({"duration": round(gap_beats, 4), "is_rest": True})
        note_end_s = min(onset_s + max(dur_s, 0.0), measure_end_s)
        note_beats = max(_EPS, (note_end_s - onset_s) / sec_per_beat)
        cell.append({"duration": round(note_beats, 4), "is_rest": False})
        deltas.append(0 if prev_pitch is None else int(pitch) - prev_pitch)
        prev_pitch = int(pitch)
        cursor_s = max(cursor_s, note_end_s)
    tail_beats = (measure_end_s - cursor_s) / sec_per_beat
    if tail_beats > _EPS:
        cell.append({"duration": round(tail_beats, 4), "is_rest": True})
    return cell, deltas


def extract_fragments_from_audio(
    flac: str | Path, cache_dir: str | Path, source_song: str,
) -> list["object"]:
    """Real riff fragments reconstructed from an audio stem, for a song with
    no matched GP file -- one real measure per `riff_bank.RiffFragment`.

    Uses the engine's own real transcription (`audio_vocab.
    transcribe_full_note_sequence`, the timed/absolute-pitch sibling of
    `transcribe_and_split_registers`: same real `basic_pitch` predict call,
    same rhythm/lead register split, but it also keeps each note's real
    onset and duration. `transcribe_and_split_registers` itself exposes only
    mod-12 pitch classes with no timing, which cannot produce the real
    semitone deltas this dataclass requires).

    Every returned fragment is tagged `source_type="audio_transcribed"` --
    an honest fallback that any downstream selector must prefer
    `tab_verbatim` data over for the same role.
    """
    audio_vocab, riff_bank = _engine_modules()

    flac = Path(flac)
    cache_dir = Path(cache_dir)
    stem, stem_name = _find_audio_stem(flac, cache_dir)
    source = stem if stem is not None else flac
    if not source.exists():
        return []

    y, sr = librosa.load(str(source), sr=_ANALYSIS_SR, mono=True)
    if y.size == 0:
        return []
    tempo = librosa.beat.beat_track(y=y, sr=sr)[0]
    bpm = float(np.atleast_1d(tempo)[0]) if np.size(tempo) else 0.0
    if not np.isfinite(bpm) or bpm <= 0:
        bpm = 120.0
    sec_per_beat = 60.0 / bpm
    measure_len_s = _BEATS_PER_MEASURE * sec_per_beat

    sequence = audio_vocab.transcribe_full_note_sequence(
        source, rhythm_cutoff_midi=_RHYTHM_CUTOFF_MIDI,
    )
    by_measure: dict[int, list[tuple[float, float, int]]] = {}
    for onset_s, dur_s, pitch in sequence.get("rhythm", []):
        by_measure.setdefault(int(float(onset_s) // measure_len_s), []).append(
            (float(onset_s), float(dur_s), int(pitch))
        )

    fragments = []
    for measure_index in sorted(by_measure):
        measure_start_s = measure_index * measure_len_s
        cell, deltas = _measure_cell_deltas(
            by_measure[measure_index], measure_start_s, measure_len_s, sec_per_beat,
        )
        if not cell or not deltas:
            continue
        fragments.append(
            riff_bank.RiffFragment(
                source_song=source_song,
                source_file=flac.name,
                measure_index=measure_index,
                track=stem_name or source.stem,
                cell=cell,
                deltas=deltas,
                role=None,
                raw_marker=None,
                source_type="audio_transcribed",
            )
        )
    return fragments
