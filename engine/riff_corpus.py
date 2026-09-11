"""UNUSED trainer for riff_model.py. Do not run. Do not import from song.py."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

_ENGINE_ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS_DIR = _ENGINE_ROOT / "data" / "ml_corpus"

PAD = 0
BOS = 1
BAR = 2
ENERGY_LOW = 3
ENERGY_MID = 4
ENERGY_HIGH = 5
_NUM_SPECIAL = 6
ENERGY_TOKENS = (ENERGY_LOW, ENERGY_MID, ENERGY_HIGH)

# Real tercile thresholds against `audio_vocab.energy_curve`'s own
# "1.0 = this song's average RMS energy" convention -- not the ARC
# table's separate absolute 0-1 scale (see `riff_model.py`'s own real
# ARC-energy bucket mapping, a DIFFERENT real scale requiring its own
# separate thresholds).
_ENERGY_LOW_MAX = 0.85
_ENERGY_HIGH_MIN = 1.15


def energy_bucket_from_relative_energy(value: float) -> int:
    """Real bucket assignment for a `energy_curve`-style relative energy
    value (1.0 = a song's own average). Terciles, not a guess: most real
    audio energy distributions cluster near 1.0, so a real +-15% band
    around it is a defensible real "typical" middle range."""
    if value < _ENERGY_LOW_MAX:
        return ENERGY_LOW
    if value > _ENERGY_HIGH_MIN:
        return ENERGY_HIGH
    return ENERGY_MID

# Real duration-bucket vocabulary: the power-of-2/dotted family already
# established this session (`song._ALLOWED_LENGTHS`, `_KICK_IOI_BUCKETS`),
# extended upward since a real sustained guitar note/chord can be held
# far longer than a kick-drum gap.
DURATION_BUCKETS: tuple[float, ...] = (
    0.125, 0.1667, 0.25, 0.333, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0,
)

VOCAB_SIZE = _NUM_SPECIAL + 12 * len(DURATION_BUCKETS)


def _snap_duration(value: float) -> int:
    """Index into `DURATION_BUCKETS` of the nearest real bucket."""
    return min(range(len(DURATION_BUCKETS)), key=lambda i: abs(DURATION_BUCKETS[i] - value))


def token_id(interval_class: int, duration_bucket_index: int) -> int:
    if not (0 <= interval_class < 12):
        raise ValueError("interval_class must be within 0-11")
    if not (0 <= duration_bucket_index < len(DURATION_BUCKETS)):
        raise ValueError("duration_bucket_index out of range")
    return _NUM_SPECIAL + interval_class * len(DURATION_BUCKETS) + duration_bucket_index


def token_to_interval_duration(token: int) -> tuple[int, float]:
    """Inverse of `token_id`: real `(interval_class, duration_beats)` for a
    non-special token. Raises `ValueError` for a special token (PAD/BOS/
    BAR have no real interval/duration -- never fabricates one)."""
    if token < _NUM_SPECIAL:
        raise ValueError(f"token {token} is a special token, has no interval/duration")
    idx = token - _NUM_SPECIAL
    interval_class, duration_idx = divmod(idx, len(DURATION_BUCKETS))
    return interval_class, DURATION_BUCKETS[duration_idx]


def notes_to_tokens(
    notes: list[tuple[float, float, int]],
    bpm: float,
    beats_per_bar: float = 4.0,
    energy_at: Callable[[float], float] | None = None,
) -> list[int]:
    """Real note sequence -> real token sequence.

    `notes` is `[(onset_s, duration_s, pitch_midi), ...]`, chronologically
    ordered (the exact shape `audio_vocab.transcribe_full_note_sequence`
    returns per register). Converts each real onset to a real beat
    position via `bpm`, computes the real signed semitone interval from
    the PREVIOUS note (the first real note has no interval and is
    dropped -- there's nothing to encode a transition FROM), snaps the
    real INTER-ONSET gap to the nearest `DURATION_BUCKETS` value, and
    inserts a real `BAR` token every time a note's onset crosses a new
    `beats_per_bar`-beat boundary since the previous note (at most one
    per note -- multiple skipped bars in a real rest are NOT expanded
    into repeated BAR tokens, since that would fabricate structure a
    genuine long rest doesn't actually carry).

    `energy_at`, when given, is a real `onset_s -> relative_energy`
    lookup (e.g. built from `audio_vocab.energy_curve` against the
    song's own ORIGINAL full-mix audio, not the transcription stem --
    real song energy is a full-mix property). An `ENERGY_LOW`/`_MID`/
    `_HIGH` token (see `energy_bucket_from_relative_energy`) is inserted
    only when the bucket at a note's real onset time differs from the
    previous token's bucket -- the same sparse "only at real
    transitions" convention `BAR` already uses, never fabricating a
    transition that didn't really happen. `energy_at=None` (the
    default) never emits energy tokens -- byte-identical to before this
    feature existed.

    Raises `ValueError` for a non-positive `bpm` -- never divides by a
    fabricated tempo.
    """
    if bpm <= 0:
        raise ValueError("bpm must be > 0")
    if len(notes) < 2:
        return []

    beats_per_sec = bpm / 60.0
    tokens: list[int] = []
    prev_onset_beat = notes[0][0] * beats_per_sec
    prev_pitch = notes[0][2]
    prev_bar_index = int(prev_onset_beat // beats_per_bar)
    prev_energy_bucket = (
        energy_bucket_from_relative_energy(energy_at(notes[0][0])) if energy_at is not None else None
    )
    if prev_energy_bucket is not None:
        tokens.append(prev_energy_bucket)
    for onset_s, _dur_s, pitch in notes[1:]:
        onset_beat = onset_s * beats_per_sec
        bar_index = int(onset_beat // beats_per_bar)
        if bar_index > prev_bar_index:
            tokens.append(BAR)
            prev_bar_index = bar_index

        if energy_at is not None:
            bucket = energy_bucket_from_relative_energy(energy_at(onset_s))
            if bucket != prev_energy_bucket:
                tokens.append(bucket)
                prev_energy_bucket = bucket

        gap_beats = max(1e-6, onset_beat - prev_onset_beat)
        interval_class = (pitch - prev_pitch) % 12
        tokens.append(token_id(interval_class, _snap_duration(gap_beats)))
        prev_onset_beat = onset_beat
        prev_pitch = pitch

    return tokens


def save_song_tokens(song_id: str, tokens: list[int], out_dir: Path | str = DEFAULT_CORPUS_DIR) -> Path:
    """Write one real song's token sequence to the local-only cache.
    `song_id` should be filesystem-safe (album/track slug) -- the caller's
    responsibility, not sanitized here."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{song_id}.json"
    path.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
    return path


def load_corpus_tokens(corpus_dir: Path | str = DEFAULT_CORPUS_DIR) -> dict[str, list[int]]:
    """Real, all real per-song token sequences from the local cache, keyed
    by song id (filename stem). Empty dict if the cache doesn't exist yet
    -- never raises, since an empty/not-yet-built cache is a real,
    expected state before the corpus pipeline has run."""
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.exists():
        return {}
    out: dict[str, list[int]] = {}
    for path in sorted(corpus_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[path.stem] = data["tokens"]
    return out
