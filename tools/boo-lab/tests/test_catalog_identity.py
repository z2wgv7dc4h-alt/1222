"""data/CATALOG.md must match the current FLAC tree identity.

The 2026-09-12 table swapped two BoO folders (Soul Sphere vs Discovery/FYE);
these tests fail if that wrong story comes back.
"""
from __future__ import annotations

from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "data" / "CATALOG.md"


def _text() -> str:
    return CATALOG.read_text(encoding="utf-8")


def _table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows


def test_soul_sphere_folder_is_not_mapped_to_discovery():
    for cells in _table_rows(_text()):
        if len(cells) >= 2 and "Soul Sphere" in cells[0]:
            assert "Discovery" not in cells[1], (
                "CATALOG.md still maps the Soul Sphere folder to The Discovery"
            )


def test_discovery_fye_folder_is_not_mapped_to_simulation():
    for cells in _table_rows(_text()):
        if len(cells) >= 2 and "Discovery" in cells[0]:
            assert "Simulation" not in cells[1], (
                "CATALOG.md still maps the Discovery FYE folder to The Simulation"
            )


def test_soul_sphere_flacs_are_not_claimed_missing():
    for line in _text().splitlines():
        assert not ("Soul Sphere" in line and "not in this tree" in line), (
            "CATALOG.md still claims Soul Sphere FLACs are not in the tree"
        )


def test_catalog_table_matches_current_flac_tree():
    by_folder = {cells[0]: cells[1] for cells in _table_rows(_text())
                 if len(cells) >= 2}

    soul = next(v for k, v in by_folder.items() if "Soul Sphere" in k)
    assert "Soul Sphere" in soul and "Discovery" not in soul

    fye = next(v for k, v in by_folder.items() if "Discovery" in k)
    assert "Discovery" in fye and "Simulation" not in fye

    sim = next(v for k, v in by_folder.items()
               if k.startswith("Born of Osiris - The Simulation"))
    assert "Simulation" in sim


def test_catalog_has_no_machine_absolute_paths():
    text = _text()
    assert "C:\\Users\\" not in text
    assert "C:/Users/" not in text
    assert "RIGGUSPIG" not in text
    assert "<CORPUS>/born_of_osiris" in text
