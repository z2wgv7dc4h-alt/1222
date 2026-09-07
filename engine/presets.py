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

REQUIRED_PRESET_KEYS = {"id", "description", "tuning_key", "scale", "dissonance"}


@dataclass(frozen=True)
class Tuning:
    key: str
    names: list[str]
    open: list[int]


@dataclass(frozen=True)
class Preset:
    id: str
    description: str
    tuning_key: str
    scale: str
    dissonance: float


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
