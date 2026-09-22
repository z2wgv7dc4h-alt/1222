"""data/rebirth-sections.jsonl is a DEAD snapshot of the deleted, invalid
Rebirth keepers -- never a keeper-read or writer path. The live file holds no
Rebirth rows."""
from __future__ import annotations

import json
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SECTIONS = LAB / "data" / "sections.jsonl"
SNAPSHOT = LAB / "data" / "rebirth-sections.jsonl"

REBIRTH = ("2009 - A Higher Place", "01 - Rebirth")


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def test_snapshot_is_a_dead_invalid_copy():
    snap = _rows(SNAPSHOT)

    assert len(snap) == 6
    assert all(r.get("invalid") is True for r in snap)
    assert all((r.get("album"), r.get("track")) == REBIRTH for r in snap)


def test_live_file_has_no_rebirth_keepers():
    from boo_lab.schema import load_section_rows

    keepers = load_section_rows(SECTIONS)

    assert [r for r in keepers
            if (r.get("album"), r.get("track")) == REBIRTH] == []
    assert keepers == []  # the six Rebirth rows were the only keepers


def test_no_source_path_reads_the_snapshot_as_keepers():
    for p in (LAB / "src" / "boo_lab").glob("*.py"):
        for line in p.read_text(encoding="utf-8").splitlines():
            assert not ("load_section_rows" in line and "rebirth-sections" in line), p.name
