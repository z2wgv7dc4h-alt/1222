"""Tuning and mood-preset loading, JSON-backed.

Tunings and presets are strict JSON data (no comments), per project
convention -- engine internals are Python, but data that a user or a future
editor UI might edit belongs in JSON. `validate_preset` is called from
`load_preset`, the one real preset-loading path, so a malformed preset can
never silently load (see .claude/rules/anti-patterns.md: "a validator that
is not called is not done").
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scales import get_scale

PRESETS_DIR = Path(__file__).resolve().parent / "presets"
TUNINGS_PATH = PRESETS_DIR / "tunings.json"

REQUIRED_PRESET_KEYS = {
    "id", "description", "tuning_key", "scale", "dissonance",
    "bpm", "bars", "feel", "open_chance", "octave_stab", "kick", "vocab",
}
# Old band-linked ids from the ported project, kept working per its own
# documented lesson: "started with band-named presets... deliberately moved
# away from them to mood/archetype names... keeping the old band-linked ids
# as ALIASES purely for backward compatibility." Never a second preset id,
# only a resolver.
ALIASES = {
    "psycho": "tech",
    "sots": "tech",
    "soi": "tech",
    # Was "djent" (an unrelated stand-in from the ported project, never
    # actually calibrated against Born of Osiris). Now real:
    # reference_vocab.py's own 12-song real corpus (Born of Osiris +
    # Veil of Maya, mixed MIDI + Guitar Pro) -> "labyrinth" preset.
    "boo": "labyrinth",
    "vom": "groovy",
    "atb": "melodic",
    # Was "chill" (the closest available proxy when this alias table was
    # ported) -- now points at "progressive", the real Periphery-styled
    # preset (lydian, real user-supplied-reference-calibrated), a better
    # match than an unrelated low-energy preset just because it shared the
    # word "atmosphere" in its old description.
    "periphery": "progressive",
}


def resolve_preset_id(name: str) -> str:
    """Canonical preset id for a name or a stale band-linked alias."""
    key = (name or "").strip().lower()
    return ALIASES.get(key, key)


@dataclass(frozen=True)
class Tuning:
    key: str
    names: list[str]
    open: list[int]


@dataclass(frozen=True)
class Vocab:
    weights: dict[int, int]
    motion: float
    # A real, corpus-derived first-order Markov transition table over
    # interval classes (`{prev_interval: {next_interval: pct}}`), from
    # `reference_vocab.build_preset_from_corpus`'s real corpus-observed
    # note-to-note sequences -- `None` for any preset/vocab not
    # calibrated against real sequence data. See `theory.
    # pick_pitch_interval_markov` for the real fallback-to-marginal-
    # weights behavior when this is `None` or lacks data for a given
    # context.
    markov: dict[int, dict[int, float]] | None = None


@dataclass(frozen=True)
class Preset:
    id: str
    description: str
    tuning_key: str
    scale: str
    dissonance: float
    bpm: int
    bars: int
    feel: str
    open_chance: float
    octave_stab: bool
    kick: str
    vocab: Vocab
    group: int | None = None
    pedal: float | None = None
    # A separately-calibrated interval vocab for solo/lead-guitar
    # generation, distinct from `vocab` (which drives the rhythm-guitar
    # riff). `None` for any preset that hasn't been calibrated against
    # real lead-register reference data -- solo generation falls back to
    # reusing `vocab` itself in that case, never a fabricated guess.
    lead_vocab: Vocab | None = None


def load_tunings(path: Path | None = None) -> dict[str, Tuning]:
    """Load the tuning table from JSON. Raises on malformed rows."""
    source = path if path is not None else TUNINGS_PATH
    data = json.loads(source.read_text())
    tunings: dict[str, Tuning] = {}
    for key, row in data.items():
        names = row["names"]
        open_notes = row["open"]
        if len(names) != len(open_notes):
            raise ValueError(
                f"tuning '{key}': names ({len(names)}) and open ({len(open_notes)}) "
                "length mismatch"
            )
        tunings[key] = Tuning(key=key, names=list(names), open=list(open_notes))
    return tunings


def get_tuning(key: str, tunings: dict[str, Tuning] | None = None) -> Tuning:
    """A single tuning by id. Raises ValueError on an unknown key rather than
    returning a fabricated/default tuning."""
    table = tunings if tunings is not None else load_tunings()
    if key not in table:
        raise ValueError(f"unknown tuning: {key!r}")
    return table[key]


def _validate_interval_weight_map(weight_map: object, preset_id: str, context: str) -> None:
    """Real, shared 0-11-interval-key + non-negative-weight bounds check --
    used for `vocab.weights`/`lead_vocab.weights` AND every real row of a
    `markov` transition table, so this rule lives in exactly one place,
    not three hand-copied checks."""
    if not isinstance(weight_map, dict) or not weight_map:
        raise ValueError(f"preset '{preset_id}': '{context}' must be a non-empty object")
    for interval_str, weight in weight_map.items():
        try:
            interval = int(interval_str)
        except (TypeError, ValueError):
            raise ValueError(f"preset '{preset_id}': {context} interval key '{interval_str}' is not an int") from None
        if not (0 <= interval <= 11):
            raise ValueError(f"preset '{preset_id}': {context} interval {interval} out of 0-11 range")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
            raise ValueError(f"preset '{preset_id}': {context} weight for interval {interval} must be >= 0")


def _validate_vocab_shape(vocab: object, preset_id: str, field_name: str) -> None:
    """Real shape validation shared by `vocab` (required) and
    `lead_vocab` (optional) -- both are the same real
    `{weights, motion, markov?}` shape, so this is one real check, not
    two copies to keep in sync. `markov`, when present, is a real,
    corpus-derived first-order transition table (see `theory.
    pick_pitch_interval_markov`) -- optional, since not every preset is
    calibrated against real sequence data yet."""
    if not isinstance(vocab, dict) or "weights" not in vocab or "motion" not in vocab:
        raise ValueError(f"preset '{preset_id}': '{field_name}' must have 'weights' and 'motion'")
    _validate_interval_weight_map(vocab["weights"], preset_id, f"{field_name}.weights")
    motion = vocab["motion"]
    if isinstance(motion, bool) or not isinstance(motion, (int, float)) or not (0.0 <= float(motion) <= 1.0):
        raise ValueError(f"preset '{preset_id}': '{field_name}.motion' must be within [0, 1]")

    if "markov" in vocab and vocab["markov"] is not None:
        markov = vocab["markov"]
        if not isinstance(markov, dict) or not markov:
            raise ValueError(f"preset '{preset_id}': '{field_name}.markov' must be a non-empty object when present")
        for prev_str, row in markov.items():
            try:
                prev = int(prev_str)
            except (TypeError, ValueError):
                raise ValueError(f"preset '{preset_id}': {field_name}.markov key '{prev_str}' is not an int") from None
            if not (0 <= prev <= 11):
                raise ValueError(f"preset '{preset_id}': {field_name}.markov interval {prev} out of 0-11 range")
            _validate_interval_weight_map(row, preset_id, f"{field_name}.markov[{prev}]")


def validate_preset(
    data: dict,
    tunings: dict[str, Tuning],
    *,
    expected_id: str | None = None,
) -> None:
    """Raise ValueError if `data` is not a well-formed preset.

    Called from `load_preset` below -- this is the real load path, not a
    standalone check nobody invokes.
    """
    if not isinstance(data, dict):
        raise ValueError("preset must be a JSON object")

    missing = REQUIRED_PRESET_KEYS - data.keys()
    if missing:
        raise ValueError(f"preset missing required keys: {sorted(missing)}")

    preset_id = data["id"]
    if not isinstance(preset_id, str) or not preset_id:
        raise ValueError("preset 'id' must be a non-empty string")
    if expected_id is not None and preset_id != expected_id:
        raise ValueError(
            f"preset id '{preset_id}' does not match its filename '{expected_id}'"
        )

    if not isinstance(data["description"], str) or not data["description"]:
        raise ValueError(f"preset '{preset_id}': 'description' must be a non-empty string")

    tuning_key = data["tuning_key"]
    if tuning_key not in tunings:
        raise ValueError(f"preset '{preset_id}': unknown tuning_key '{tuning_key}'")

    try:
        get_scale(data["scale"])
    except ValueError as exc:
        raise ValueError(f"preset '{preset_id}': {exc}") from exc

    dissonance = data["dissonance"]
    if isinstance(dissonance, bool) or not isinstance(dissonance, (int, float)):
        raise ValueError(f"preset '{preset_id}': 'dissonance' must be a number")
    if not (0.0 <= float(dissonance) <= 1.0):
        raise ValueError(f"preset '{preset_id}': 'dissonance' must be within [0, 1]")

    if not isinstance(data["bpm"], (int, float)) or isinstance(data["bpm"], bool) or data["bpm"] <= 0:
        raise ValueError(f"preset '{preset_id}': 'bpm' must be a positive number")
    if not isinstance(data["bars"], int) or isinstance(data["bars"], bool) or data["bars"] <= 0:
        raise ValueError(f"preset '{preset_id}': 'bars' must be a positive int")
    if not isinstance(data["feel"], str) or not data["feel"]:
        raise ValueError(f"preset '{preset_id}': 'feel' must be a non-empty string")
    open_chance = data["open_chance"]
    if isinstance(open_chance, bool) or not isinstance(open_chance, (int, float)) or not (0.0 <= float(open_chance) <= 1.0):
        raise ValueError(f"preset '{preset_id}': 'open_chance' must be a number within [0, 1]")
    if not isinstance(data["octave_stab"], bool):
        raise ValueError(f"preset '{preset_id}': 'octave_stab' must be a bool")
    if not isinstance(data["kick"], str) or not data["kick"]:
        raise ValueError(f"preset '{preset_id}': 'kick' must be a non-empty string")

    _validate_vocab_shape(data["vocab"], preset_id, field_name="vocab")

    if "lead_vocab" in data and data["lead_vocab"] is not None:
        _validate_vocab_shape(data["lead_vocab"], preset_id, field_name="lead_vocab")

    if "group" in data and data["group"] is not None:
        if not isinstance(data["group"], int) or isinstance(data["group"], bool) or data["group"] <= 0:
            raise ValueError(f"preset '{preset_id}': 'group' must be a positive int when present")
    if "pedal" in data and data["pedal"] is not None:
        pedal = data["pedal"]
        if isinstance(pedal, bool) or not isinstance(pedal, (int, float)) or not (0.0 <= float(pedal) <= 1.0):
            raise ValueError(f"preset '{preset_id}': 'pedal' must be within [0, 1] when present")


def _parse_vocab(vocab_data: dict) -> Vocab:
    """Real, shared JSON-dict-to-`Vocab` parsing (int-keyed `weights`,
    real `motion`, optional real int-keyed-nested `markov`) -- used for
    both the main `vocab` and the optional `lead_vocab`, one place, not
    two hand-copied constructions."""
    markov_data = vocab_data.get("markov")
    markov = (
        {int(prev): {int(nxt): w for nxt, w in row.items()} for prev, row in markov_data.items()}
        if markov_data is not None
        else None
    )
    return Vocab(
        weights={int(k): v for k, v in vocab_data["weights"].items()},
        motion=float(vocab_data["motion"]),
        markov=markov,
    )


def load_preset(path: Path, tunings: dict[str, Tuning] | None = None) -> Preset:
    """Load and validate one preset JSON file. The validator runs here, on
    the real load path -- not just available for tests to call directly."""
    table = tunings if tunings is not None else load_tunings()
    data = json.loads(path.read_text())
    validate_preset(data, table, expected_id=path.stem)
    return Preset(
        id=data["id"],
        description=data["description"],
        tuning_key=data["tuning_key"],
        scale=data["scale"],
        dissonance=float(data["dissonance"]),
        bpm=data["bpm"],
        bars=data["bars"],
        feel=data["feel"],
        open_chance=float(data["open_chance"]),
        octave_stab=data["octave_stab"],
        kick=data["kick"],
        vocab=_parse_vocab(data["vocab"]),
        group=data.get("group"),
        pedal=(float(data["pedal"]) if data.get("pedal") is not None else None),
        lead_vocab=(_parse_vocab(data["lead_vocab"]) if data.get("lead_vocab") is not None else None),
    )


def blend_presets(preset_a: Preset, preset_b: Preset, t: float) -> Preset:
    """P9.2/P9.3 -- real linear interpolation of the CONTINUOUS character
    knobs between two real presets, at `t` in `[0, 1]` (`t=0` is exactly
    `preset_a`, `t=1` is exactly `preset_b`). Feeds Guided Mode's
    preset-blend slider (scope sec.15.1: "let the user nudge between two
    presets... e.g. a Born-of-Osiris <-> Infant-Annihilator slider") and
    Pro/regen "more djent"-style character nudges.

    Only real, continuous, genre-CHARACTER fields blend: `vocab.weights`
    (the union of both presets' real interval keys -- a key only one side
    declares is treated as weight 0 on the other side, not dropped),
    `dissonance`, `vocab.motion`, `pedal` (a preset that leaves `pedal`
    `None` is treated as `0.0` for the blend, not skipped), `lead_vocab`
    (a preset that leaves `lead_vocab` `None` falls back to its OWN
    `vocab` for the blend -- the same real fallback solo generation
    itself uses -- so the blended result always carries a real,
    non-`None` `lead_vocab`), and `vocab.markov`/`lead_vocab.markov` (a
    real, corpus-derived transition table -- a side missing real markov
    data is treated as an entirely empty table for the blend, same
    "missing treated as 0" convention as `weights`' own blend; the
    blended result's `markov` is `None` only when NEITHER side has any
    real transition data at all, never a fabricated table). Every
    STRUCTURAL field (tuning_key, scale, bpm, bars, feel, kick, group,
    octave_stab, open_chance, id, description) comes from `preset_a`
    UNCHANGED -- blending two different tunings or scales isn't
    well-defined, a deliberate, documented scope boundary, not an
    oversight."""
    if not (0.0 <= t <= 1.0):
        raise ValueError("t must be within [0, 1]")

    keys = set(preset_a.vocab.weights) | set(preset_b.vocab.weights)
    weights = {
        k: preset_a.vocab.weights.get(k, 0) * (1 - t) + preset_b.vocab.weights.get(k, 0) * t
        for k in keys
    }
    motion = preset_a.vocab.motion * (1 - t) + preset_b.vocab.motion * t
    markov = _blend_markov(preset_a.vocab.markov, preset_b.vocab.markov, t)
    dissonance = preset_a.dissonance * (1 - t) + preset_b.dissonance * t
    pedal_a = preset_a.pedal if preset_a.pedal is not None else 0.0
    pedal_b = preset_b.pedal if preset_b.pedal is not None else 0.0
    pedal = pedal_a * (1 - t) + pedal_b * t

    lead_a = preset_a.lead_vocab if preset_a.lead_vocab is not None else preset_a.vocab
    lead_b = preset_b.lead_vocab if preset_b.lead_vocab is not None else preset_b.vocab
    lead_keys = set(lead_a.weights) | set(lead_b.weights)
    lead_weights = {
        k: lead_a.weights.get(k, 0) * (1 - t) + lead_b.weights.get(k, 0) * t
        for k in lead_keys
    }
    lead_motion = lead_a.motion * (1 - t) + lead_b.motion * t
    lead_markov = _blend_markov(lead_a.markov, lead_b.markov, t)

    return Preset(
        id=preset_a.id,
        description=preset_a.description,
        tuning_key=preset_a.tuning_key,
        scale=preset_a.scale,
        dissonance=dissonance,
        bpm=preset_a.bpm,
        bars=preset_a.bars,
        feel=preset_a.feel,
        open_chance=preset_a.open_chance,
        octave_stab=preset_a.octave_stab,
        kick=preset_a.kick,
        vocab=Vocab(weights=weights, motion=motion, markov=markov),
        group=preset_a.group,
        pedal=pedal,
        lead_vocab=Vocab(weights=lead_weights, motion=lead_motion, markov=lead_markov),
    )


def _blend_markov(
    markov_a: dict[int, dict[int, float]] | None,
    markov_b: dict[int, dict[int, float]] | None,
    t: float,
) -> dict[int, dict[int, float]] | None:
    """Real cell-by-cell blend of two `Vocab.markov` transition tables --
    union of every `(prev, next)` pair across both, missing treated as 0
    on whichever side lacks it (same convention `blend_presets` already
    uses for `vocab.weights`). Returns `None`, never an empty `{}`, when
    NEITHER side has any real transition data -- a blend of nothing
    stays honestly nothing, not a fabricated table."""
    a = markov_a or {}
    b = markov_b or {}
    if not a and not b:
        return None
    blended: dict[int, dict[int, float]] = {}
    for prev in set(a) | set(b):
        row_a = a.get(prev, {})
        row_b = b.get(prev, {})
        row = {
            nxt: row_a.get(nxt, 0) * (1 - t) + row_b.get(nxt, 0) * t
            for nxt in set(row_a) | set(row_b)
        }
        if row:
            blended[prev] = row
    return blended or None


def load_all_presets(presets_dir: Path | None = None) -> dict[str, Preset]:
    """Discover and load every preset JSON file in `presets_dir` via glob --
    never a hardcoded filename list, so a new or broken preset file can't
    silently escape loading."""
    directory = presets_dir if presets_dir is not None else PRESETS_DIR
    tunings = load_tunings()
    presets: dict[str, Preset] = {}
    for file_path in sorted(directory.glob("*.json")):
        if file_path == TUNINGS_PATH or file_path.name == "tunings.json":
            continue
        preset = load_preset(file_path, tunings)
        presets[preset.id] = preset
    return presets
