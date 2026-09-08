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
    "boo": "djent",
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

    vocab = data["vocab"]
    if not isinstance(vocab, dict) or "weights" not in vocab or "motion" not in vocab:
        raise ValueError(f"preset '{preset_id}': 'vocab' must have 'weights' and 'motion'")
    weights = vocab["weights"]
    if not isinstance(weights, dict) or not weights:
        raise ValueError(f"preset '{preset_id}': 'vocab.weights' must be a non-empty object")
    for interval_str, weight in weights.items():
        try:
            interval = int(interval_str)
        except (TypeError, ValueError):
            raise ValueError(f"preset '{preset_id}': vocab interval key '{interval_str}' is not an int") from None
        if not (0 <= interval <= 11):
            raise ValueError(f"preset '{preset_id}': vocab interval {interval} out of 0-11 range")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight < 0:
            raise ValueError(f"preset '{preset_id}': vocab weight for interval {interval} must be >= 0")
    motion = vocab["motion"]
    if isinstance(motion, bool) or not isinstance(motion, (int, float)) or not (0.0 <= float(motion) <= 1.0):
        raise ValueError(f"preset '{preset_id}': 'vocab.motion' must be within [0, 1]")

    if "group" in data and data["group"] is not None:
        if not isinstance(data["group"], int) or isinstance(data["group"], bool) or data["group"] <= 0:
            raise ValueError(f"preset '{preset_id}': 'group' must be a positive int when present")
    if "pedal" in data and data["pedal"] is not None:
        pedal = data["pedal"]
        if isinstance(pedal, bool) or not isinstance(pedal, (int, float)) or not (0.0 <= float(pedal) <= 1.0):
            raise ValueError(f"preset '{preset_id}': 'pedal' must be within [0, 1] when present")


def load_preset(path: Path, tunings: dict[str, Tuning] | None = None) -> Preset:
    """Load and validate one preset JSON file. The validator runs here, on
    the real load path -- not just available for tests to call directly."""
    table = tunings if tunings is not None else load_tunings()
    data = json.loads(path.read_text())
    validate_preset(data, table, expected_id=path.stem)
    vocab_data = data["vocab"]
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
        vocab=Vocab(
            weights={int(k): v for k, v in vocab_data["weights"].items()},
            motion=float(vocab_data["motion"]),
        ),
        group=data.get("group"),
        pedal=(float(data["pedal"]) if data.get("pedal") is not None else None),
    )


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
