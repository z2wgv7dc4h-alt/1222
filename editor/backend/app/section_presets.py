"""P9.7 -- real, local-only persistence for named section-level presets.

Per scope sec.10.5's own local-only decision (no cloud, no hosted DB): a
section preset is a real, complete, reproducible `RegenEdit` (mode/role/
hit_chance_bias/regen_seed -- see app/main.py's `RegenEdit`) under a
user-given name, nothing more needs inventing. Persisted as a real local
JSON file, not an in-memory dict, so it survives a backend restart -- the
same real "no session state" discipline `app/edits.py` already applies to
composition, extended here to storage instead of memory.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "section_presets.json"


def _read_all() -> dict:
    if not _DATA_PATH.exists():
        return {}
    return json.loads(_DATA_PATH.read_text())


def _write_all(data: dict) -> None:
    _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DATA_PATH.write_text(json.dumps(data, indent=2))


def list_section_presets() -> dict:
    """Real, JSON-safe `{name: edit}` mapping of every saved preset."""
    return _read_all()


def save_section_preset(name: str, edit: dict) -> None:
    if not name.strip():
        raise ValueError("section preset name must not be empty")
    data = _read_all()
    data[name] = edit
    _write_all(data)


def delete_section_preset(name: str) -> None:
    data = _read_all()
    if name not in data:
        raise KeyError(f"unknown section preset: {name!r}")
    del data[name]
    _write_all(data)
