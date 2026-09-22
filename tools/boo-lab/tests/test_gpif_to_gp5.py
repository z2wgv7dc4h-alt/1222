"""`gpif_to_gp5` is off the live surface -- not importable and not wired.

The GPIF onset/duration fallback in `sync` is still real; the GP7->GP5
converter is not. Uses the hand-made `tests/fixtures/tiny.gp`; no commercial
tab is vendored.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boo_lab import sync

FIX = Path(__file__).parent / "fixtures" / "tiny.gp"
LAB = Path(__file__).resolve().parents[1]
SRC = LAB / "src" / "boo_lab"


def test_gpif_to_gp5_is_not_importable_from_the_package():
    with pytest.raises(ImportError):
        from boo_lab import gpif_to_gp5  # noqa: F401


def test_no_source_module_references_gpif_to_gp5():
    for p in SRC.glob("*.py"):
        assert "gpif_to_gp5" not in p.read_text(encoding="utf-8"), p.name


def test_cli_has_no_write_gp5_flag():
    assert "write-gp5" not in (SRC / "cli.py").read_text(encoding="utf-8")


def test_sync_falls_back_to_gpif_onsets_and_duration():
    # pyguitarpro cannot read the zip, so the GPIF path clocks the tab.
    onsets = sync.gp_onset_times(FIX)
    assert onsets is not None
    assert len(onsets) == 10  # 5 notes x 2 repeat passes
    assert onsets[0] == 0.0
    assert sync._tab_play_seconds(FIX) == pytest.approx(8.0)


def test_gpif_events_none_for_a_non_gp_suffix(tmp_path):
    other = tmp_path / "x.gp5"
    other.write_bytes(b"nope")
    assert sync._gpif_events(other) is None
