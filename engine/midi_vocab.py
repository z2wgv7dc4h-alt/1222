"""Reference-MIDI density/placement vocabulary -- Phase 4 task P4.4.

god-tier-metal-scope.md sec. 18.6 identified a real, legally-clean MIDI
reference corpus (Whack Studio's "Breakdown Essentials" GM pack, plus
JJDoge's free "Lakeside Camping" / "Lamb Chops" / "Dreaming In Theaters"
groove packs) extracted to `reference/midi-corpus/` (gitignored -- 1967
`.mid` files across four packs, organized by BPM-range folders with
Grooves/Fills subfolders).

This module mines that corpus for realistic drum-fill DENSITY vocabulary --
hits-per-beat, fill length in beats, how many distinct note numbers a fill
touches -- as reference DATA, never as literal patterns to copy. Per
CLAUDE.md's law ("Grid is the writer. Audio models are paint after the
score."), `rhythm.py`/`drums.py` remain the actual writer: this corpus only
teaches `vocabulary_informed_hit_chance` what realistic fill density looks
like at a given BPM, as one more input alongside the caller's own
`hit_chance` choice.

Three-stage pipeline, deliberately split so tests never have to touch the
1967-file corpus:
  1. `extract_file_stats` / `extract_corpus_stats` -- parse real `.mid` files
     with `mido` (added to requirements.txt; pure-Python, MIT-licensed --
     the pragmatic choice over hand-rolling a binary MIDI parser).
  2. `aggregate_vocabulary` -- roll per-file stats into small summary
     buckets (by BPM range and by source pack).
  3. `build_vocabulary` writes that summary to a small cached JSON file
     (`engine/data/midi_vocab.json`); `load_vocabulary` /
     `vocabulary_informed_hit_chance` read the cache -- nothing downstream
     re-parses MIDI on every call.

Hard law from CLAUDE.md this file obeys:
  - Grid is the writer. This module only produces a density *parameter*
    (`hit_chance`); it never emits notes/cells itself.
  - Seeded RNG: N/A here -- this module is pure data extraction/lookup, no
    randomness.
  - Glob the directory (`rglob("*.mid")`), never a hardcoded file list --
    anti-patterns.md.
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import mido
except ImportError as exc:  # pragma: no cover - exercised only when mido is missing
    raise ImportError(
        "midi_vocab requires the 'mido' package. It is listed in "
        "engine/requirements.txt -- install with `pip install mido`."
    ) from exc

_EPS = 1e-9

_ENGINE_ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS_DIR = _ENGINE_ROOT.parent / "reference" / "midi-corpus"
DEFAULT_CACHE_PATH = _ENGINE_ROOT / "data" / "midi_vocab.json"

# BPM buckets are 20-BPM-wide bands keyed by their floor, e.g. "200-220".
_BUCKET_WIDTH = 20

# This corpus's own naming convention: a folder like "01 - 220 - 240 BPM" (a
# declared range) or a filename like "1. 147 BPM.mid" (a single value).
_BPM_RANGE_RE = re.compile(r"(\d{2,3})\s*-\s*(\d{2,3})\s*BPM", re.IGNORECASE)
_BPM_SINGLE_RE = re.compile(r"(\d{2,3})\s*BPM", re.IGNORECASE)

# Documented fallback hit_chance when no vocabulary data is available at all
# (cache missing, corpus empty) -- a flat, musically reasonable default, not
# 0.0 or 1.0, so a caller who forgets to build the cache still gets a
# playable fill rather than silence or a wall of hits.
FALLBACK_HIT_CHANCE = 0.55

# hits-per-beat -> hit_chance conversion factor: this corpus's fills read as
# roughly a sixteenth-note-ish grid (4 slots/beat) in the source material, so
# hits-per-beat is divided by 4.0 to land in a [0, 1] hit_chance range. This
# is a documented, simple proxy -- not a claim that every drums.py fill uses
# literal 16th-note cells.
_HITS_PER_BEAT_TO_HIT_CHANCE = 4.0
_MIN_HIT_CHANCE = 0.05
_MAX_HIT_CHANCE = 1.0

# Note 36 ("Bass Drum 1") is the one note number trustworthy across an
# ARBITRARY foreign MIDI pack's own authoring convention -- kick/snare are
# the two notes essentially every real-world drum-MIDI convention (GM,
# Superior Drummer, EZdrummer, Slate, ...) agrees on; everything past that
# is genuinely kit-dependent (this project's OWN kit already remaps note 48
# away from GM's meaning -- see `drums.py`'s own module docstring). Only
# note 36 is tracked positionally below; a real, documented, deliberate
# scope limit, not an oversight.
_KICK_NOTE = 36

# Real IOI (inter-onset-interval) bucket vocabulary for the kick-pattern
# Markov chain below -- evidenced directly, not guessed: measuring every
# real kick-to-kick gap across the "whack_breakdown" pack's 104 real files
# (4446 real gaps) found dominant clusters at 0.25/0.5/1.0/0.75 beats (the
# power-of-2 + dotted family) plus a real, smaller but non-trivial cluster
# around 0.167/0.333 beats (the triplet family -- the same real triplet
# character `reference_vocab.build_preset_from_corpus`'s own rhythm-feel
# calibration independently confirmed corpus-wide for guitar rhythm).
_KICK_IOI_BUCKETS: tuple[float, ...] = (0.125, 0.1667, 0.25, 0.333, 0.5, 0.75, 1.0, 1.5, 2.0)

# Only this pack is genuinely breakdown-genre-specific programming (the
# three JJ packs are generic multi-genre groove packs spanning 70-240 BPM,
# not written for this project's own breakdown/chug convention) -- pooling
# the kick-pattern Markov chain from every pack would dilute a real,
# genre-relevant signal with a lot of irrelevant material.
_KICK_MARKOV_PACK = "whack_breakdown"


def _snap_to_bucket(value: float, buckets: tuple[float, ...] = _KICK_IOI_BUCKETS) -> float:
    """Nearest-bucket snap for a real measured IOI -- never fabricates a
    value outside the real, evidenced bucket vocabulary above."""
    return min(buckets, key=lambda b: abs(b - value))


def _ioi_transitions_from_sequence(iois: list[float]) -> dict[float, dict[float, int]]:
    """Real bigram transition COUNTS over bucket-snapped consecutive IOIs
    -- deliberately raw counts, not a per-file percentage (mirrors
    `reference_vocab._interval_transitions_from_sequence`'s own,
    already-proven reasoning: a single file's own transition table is too
    sparse for a reliable per-file percentage; pool raw counts across many
    real files first, normalize once at the very end)."""
    counts: dict[float, dict[float, int]] = defaultdict(lambda: defaultdict(int))
    snapped = [_snap_to_bucket(v) for v in iois]
    for prev, nxt in zip(snapped, snapped[1:]):
        counts[prev][nxt] += 1
    return {k: dict(v) for k, v in counts.items()}


def _pool_kick_ioi_markov(files: list[dict[str, Any]]) -> dict[float, dict[float, float]] | None:
    """Real corpus-wide pooling of `_ioi_transitions_from_sequence` across
    every file in the real, genre-specific `_KICK_MARKOV_PACK` -- raw
    counts summed first, then each `prev`-row normalized to real
    percentages once at the end (same shape as `reference_vocab.
    _pool_transition_counts`). Returns `None` when no real kick-IOI data
    exists at all in that pack, rather than fabricating an empty table."""
    totals: dict[float, dict[float, int]] = defaultdict(lambda: defaultdict(int))
    for f in files:
        if f.get("pack") != _KICK_MARKOV_PACK:
            continue
        for prev, row in _ioi_transitions_from_sequence(f.get("kick_ioi_beats", [])).items():
            for nxt, count in row.items():
                totals[prev][nxt] += count
    if not totals:
        return None
    return {
        prev: {nxt: round(100.0 * count / sum(row.values()), 4) for nxt, count in row.items()}
        for prev, row in totals.items()
    }


def _bpm_from_path(path: Path) -> float | None:
    """Best-effort BPM extraction from this corpus's own folder/file naming
    convention. Returns the midpoint of a declared range (e.g. "220 - 240
    BPM" -> 230.0), a single declared value (e.g. "147 BPM" -> 147.0), or
    None if no path component encodes a BPM at all."""
    for part in reversed(path.parts):
        m = _BPM_RANGE_RE.search(part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            return (lo + hi) / 2.0
    for part in reversed(path.parts):
        m = _BPM_SINGLE_RE.search(part)
        if m:
            return float(m.group(1))
    return None


def _fill_or_groove(path: Path) -> str:
    """Classify a corpus file as "fill", "groove", or "other" from its path
    components (this corpus organizes files into Grooves/Fills/Straight/
    Backbeat/etc. subfolders -- see sec. 18.6)."""
    joined = "/".join(path.parts).lower()
    if "fill" in joined:
        return "fill"
    if "groove" in joined or "straight" in joined or "backbeat" in joined:
        return "groove"
    return "other"


def _bpm_bucket(bpm: float | None) -> str:
    if bpm is None:
        return "unknown"
    floor = int(bpm // _BUCKET_WIDTH) * _BUCKET_WIDTH
    return f"{floor}-{floor + _BUCKET_WIDTH}"


def extract_file_stats(
    path: Path | str | None = None,
    midi_file: "mido.MidiFile | None" = None,
) -> dict[str, Any]:
    """Parse one MIDI file and return its density stats.

    Pass either `path` (a file on disk) or an already-open `midi_file` --
    the latter is how tests build a small synthetic `mido.MidiFile` in
    memory without touching disk (see tests/test_midi_vocab.py), keeping the
    main correctness test fast and independent of the real corpus.

    Returns `{"hits": int, "beats": float, "hits_per_beat": float,
    "distinct_notes": int, "note_counts": {note: count}, "tempo_bpm":
    float|None, "kick_ioi_beats": list[float]}`.

    Duration (`beats`) is measured via `ticks_per_beat` against the file's
    own tick data, not derived from tempo: ticks-per-beat already gives an
    exact tick->beat conversion regardless of tempo. `tempo_bpm` is only
    captured as an optional label, from the first `set_tempo` meta event
    found (if any) -- most files in this corpus carry no tempo meta at all
    (their BPM is documented in the filename/folder instead, see
    `_bpm_from_path`).

    `kick_ioi_beats` is the real, chronological sequence of gaps (in
    beats) between consecutive note-36 ("KICK" in every common MIDI
    drum-map convention, GM included) onsets -- note 36 is deliberately
    the ONLY note this function tracks positionally, since it is the one
    note number trustworthy across an arbitrary pack's own foreign kit
    convention (this project's own kit already remaps other notes, e.g.
    48 is a hi-hat here, not GM's hi-mid tom -- see `drums.py`'s own
    module docstring). Computed per-track (never bridging a gap across
    two different tracks) then concatenated; `[]` when a file has fewer
    than two real note-36 onsets in any single track.
    """
    if midi_file is None:
        if path is None:
            raise ValueError("must pass either path or midi_file")
        midi_file = mido.MidiFile(str(path))

    ticks_per_beat = midi_file.ticks_per_beat
    if not ticks_per_beat:
        raise ValueError("MIDI file has no ticks_per_beat (not a tick-based file)")

    total_ticks = 0
    hits = 0
    note_counts: Counter[int] = Counter()
    tempo_usec: int | None = None
    kick_ioi_beats: list[float] = []
    for track in midi_file.tracks:
        abs_ticks = 0
        kick_onset_ticks: list[int] = []
        for msg in track:
            abs_ticks += msg.time
            if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
                hits += 1
                note_counts[msg.note] += 1
                if msg.note == _KICK_NOTE:
                    kick_onset_ticks.append(abs_ticks)
            elif msg.type == "set_tempo" and tempo_usec is None:
                tempo_usec = msg.tempo
        total_ticks = max(total_ticks, abs_ticks)
        kick_ioi_beats.extend(
            (b - a) / ticks_per_beat
            for a, b in zip(kick_onset_ticks, kick_onset_ticks[1:])
            if b > a
        )

    beats = total_ticks / ticks_per_beat
    hits_per_beat = (hits / beats) if beats > _EPS else 0.0
    tempo_bpm = mido.tempo2bpm(tempo_usec) if tempo_usec else None

    return {
        "hits": hits,
        "beats": beats,
        "hits_per_beat": hits_per_beat,
        "distinct_notes": len(note_counts),
        "note_counts": dict(note_counts),
        "tempo_bpm": tempo_bpm,
        "kick_ioi_beats": kick_ioi_beats,
    }


def extract_corpus_stats(corpus_dir: Path | str = DEFAULT_CORPUS_DIR) -> dict[str, Any]:
    """Walk `corpus_dir` for every `*.mid` file (via `rglob` -- never a
    hardcoded file list, per anti-patterns.md), parse each with `mido`, and
    return per-file stats plus a skip count.

    A file that fails to parse (corrupt or non-standard MIDI) is counted in
    `skipped` and its relative path recorded (capped at 20 examples) rather
    than crashing the whole walk.

    Returns `{"files": [...], "skipped": int, "skipped_examples": [str]}`.
    Each entry in `files` is `extract_file_stats`'s dict plus `"pack"`
    (top-level corpus subfolder, e.g. "jj_lamb"), `"kind"` ("fill"/"groove"/
    "other"), `"bpm"` (float or None), `"bucket"` (BPM-bucket key), and
    `"path"` (corpus-relative).
    """
    corpus_dir = Path(corpus_dir)
    files_out: list[dict[str, Any]] = []
    skipped = 0
    skipped_examples: list[str] = []

    for path in sorted(corpus_dir.rglob("*.mid")):
        try:
            stats = extract_file_stats(path)
        except Exception:
            skipped += 1
            if len(skipped_examples) < 20:
                skipped_examples.append(str(path.relative_to(corpus_dir)))
            continue

        rel = path.relative_to(corpus_dir)
        pack = rel.parts[0] if rel.parts else "unknown"
        bpm = _bpm_from_path(path)
        if bpm is None:
            bpm = stats["tempo_bpm"]

        files_out.append(
            {
                **stats,
                "pack": pack,
                "kind": _fill_or_groove(path),
                "bpm": bpm,
                "bucket": _bpm_bucket(bpm),
                "path": str(rel),
            }
        )

    return {"files": files_out, "skipped": skipped, "skipped_examples": skipped_examples}


def _summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    hits_per_beat = [i["hits_per_beat"] for i in items]
    fill_lengths = [i["beats"] for i in items if i["kind"] == "fill"]
    distinct_notes = [i["distinct_notes"] for i in items]
    return {
        "file_count": len(items),
        "avg_hits_per_beat": round(statistics.fmean(hits_per_beat), 4) if hits_per_beat else 0.0,
        "fill_length_beats": {
            "count": len(fill_lengths),
            "min": round(min(fill_lengths), 4) if fill_lengths else None,
            "median": round(statistics.median(fill_lengths), 4) if fill_lengths else None,
            "max": round(max(fill_lengths), 4) if fill_lengths else None,
        },
        "avg_distinct_notes_per_file": (
            round(statistics.fmean(distinct_notes), 4) if distinct_notes else 0.0
        ),
    }


def aggregate_vocabulary(extraction: dict[str, Any]) -> dict[str, Any]:
    """Roll per-file stats (from `extract_corpus_stats`) up into the small
    summary shape the cache file / `vocabulary_informed_hit_chance` consume:
    bucketed by BPM range and, separately, by source pack. Per bucket/pack:
    average hits-per-beat, a min/median/max distribution of FILL lengths in
    beats (only files classified `"kind": "fill"`), and the average count of
    distinct MIDI note numbers per file (a density-of-vocabulary proxy).

    Also computes a real, corpus-wide `kick_ioi_markov` (see
    `_pool_kick_ioi_markov`) -- a first-order Markov chain over real
    kick-to-kick timing gaps, pooled only from the genre-specific
    `_KICK_MARKOV_PACK`, `None` when that pack contributed no real kick
    data at all."""
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_pack: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in extraction["files"]:
        by_bucket[f["bucket"]].append(f)
        by_pack[f["pack"]].append(f)

    return {
        "bucket_width_bpm": _BUCKET_WIDTH,
        "total_files_parsed": len(extraction["files"]),
        "skipped_files": extraction["skipped"],
        "by_bpm_bucket": {b: _summarize(items) for b, items in sorted(by_bucket.items())},
        "by_pack": {p: _summarize(items) for p, items in sorted(by_pack.items())},
        "kick_ioi_markov": _pool_kick_ioi_markov(extraction["files"]),
    }


def build_vocabulary(
    corpus_dir: Path | str = DEFAULT_CORPUS_DIR,
    cache_path: Path | str = DEFAULT_CACHE_PATH,
) -> dict[str, Any]:
    """(Re)generate the cached vocabulary JSON from the real corpus.

    Run this once (or whenever the corpus changes) -- e.g.
    `python -c "import midi_vocab; midi_vocab.build_vocabulary()"` from
    `engine/`. Downstream code (`load_vocabulary`,
    `vocabulary_informed_hit_chance`) reads the resulting cache; it never
    re-parses the corpus's 1967 files per call.
    """
    extraction = extract_corpus_stats(corpus_dir)
    vocab = aggregate_vocabulary(extraction)
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(vocab, indent=2, sort_keys=True), encoding="utf-8")
    return vocab


def load_vocabulary(cache_path: Path | str = DEFAULT_CACHE_PATH) -> dict[str, Any]:
    """Load the cached vocabulary JSON written by `build_vocabulary`.

    Raises `FileNotFoundError` (or `json.JSONDecodeError` on a corrupted
    cache) if the cache has never been built -- callers wanting a graceful
    fallback instead should catch those explicitly, as
    `vocabulary_informed_hit_chance` does.
    """
    with Path(cache_path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _bucket_floor(bpm: float) -> int:
    return int(bpm // _BUCKET_WIDTH) * _BUCKET_WIDTH


def vocabulary_informed_hit_chance(
    bpm: Any,
    vocab: dict[str, Any] | None = None,
    default: float = FALLBACK_HIT_CHANCE,
) -> float:
    """Map a target BPM to a `hit_chance` in [0, 1] derived from the real
    reference corpus's density vocabulary -- usable directly as the
    `hit_chance` argument to `rhythm.generate_rhythm` /
    `drums.generate_blast_fill` (see `drums.generate_vocabulary_informed_
    blast_fill`, which is the real, wired call path for this).

    Resolution order (documented "falls back sensibly" behavior for bad
    input, per P4.4's bad-input-test requirement):
      1. `bpm` must be a finite real number -- anything else (a string,
         None, NaN, +-inf) returns `default` rather than raising.
      2. Load `vocab` (or the cached JSON at `DEFAULT_CACHE_PATH` if `vocab`
         is None). A missing/corrupt cache also returns `default`.
      3. Otherwise, among BPM buckets that actually have files (excluding
         "unknown"), pick the NEAREST bucket by floor distance to `bpm`'s
         own bucket -- an out-of-range BPM (5, or 5000) still resolves to
         the closest real data instead of crashing or extrapolating
         nonsense. An empty vocabulary (no populated buckets at all) also
         returns `default`.
      4. That bucket's `avg_hits_per_beat` is divided by
         `_HITS_PER_BEAT_TO_HIT_CHANCE` (4.0 -- a documented 16th-note-ish
         grid proxy) and clamped to `[_MIN_HIT_CHANCE, _MAX_HIT_CHANCE]`
         (0.05..1.0) so the result is always a valid, non-degenerate
         `hit_chance`.
    """
    try:
        bpm_value = float(bpm)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(bpm_value):
        return default

    if vocab is None:
        try:
            vocab = load_vocabulary()
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    buckets = vocab.get("by_bpm_bucket", {})
    populated = {
        key: b
        for key, b in buckets.items()
        if key != "unknown" and b.get("file_count", 0) > 0
    }
    if not populated:
        return default

    target_floor = _bucket_floor(bpm_value)
    nearest_key = min(populated, key=lambda k: abs(int(k.split("-")[0]) - target_floor))
    avg_hits_per_beat = populated[nearest_key]["avg_hits_per_beat"]

    hit_chance = avg_hits_per_beat / _HITS_PER_BEAT_TO_HIT_CHANCE
    return max(_MIN_HIT_CHANCE, min(_MAX_HIT_CHANCE, hit_chance))


if __name__ == "__main__":
    result = build_vocabulary()
    print(
        f"Parsed {result['total_files_parsed']} files "
        f"({result['skipped_files']} skipped) into "
        f"{len(result['by_bpm_bucket'])} BPM buckets -> {DEFAULT_CACHE_PATH}"
    )
