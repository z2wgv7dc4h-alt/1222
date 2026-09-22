"""data/rebirth-sections.jsonl is a true snapshot of the live Rebirth windows
(and never a writer / keeper-read path)."""
from __future__ import annotations

import json
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SECTIONS = LAB / "data" / "sections.jsonl"
SNAPSHOT = LAB / "data" / "rebirth-sections.jsonl"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _key(r: dict):
    return (r.get("album"), r.get("track"), round(float(r["start"]), 3),
            round(float(r["end"]), 3), r.get("role"), r.get("source"))


def test_snapshot_windows_match_live_rebirth():
    snap = _rows(SNAPSHOT)
    live = [r for r in _rows(SECTIONS)
            if (r.get("album"), r.get("track")) == ("2009 - A Higher Place", "01 - Rebirth")]

    assert sorted(map(_key, snap)) == sorted(map(_key, live))
    assert snap and all(r.get("heard") is True for r in snap)


def test_live_rebirth_rows_are_grandfathered_keepers():
    from boo_lab.schema import load_section_rows

    keepers = load_section_rows(SECTIONS)
    rebirth = [r for r in keepers
               if r.get("album") == "2009 - A Higher Place" and r.get("track") == "01 - Rebirth"]

    # the pre-stamp rows (no layer, empty figure_id) still pass the reader
    assert len(rebirth) == len(_rows(SNAPSHOT))
    assert any(not r.get("layer") for r in rebirth)


def test_no_source_path_reads_the_snapshot_as_keepers():
    for p in (LAB / "src" / "boo_lab").glob("*.py"):
        for line in p.read_text(encoding="utf-8").splitlines():
            assert not ("load_section_rows" in line and "rebirth-sections" in line), p.name
