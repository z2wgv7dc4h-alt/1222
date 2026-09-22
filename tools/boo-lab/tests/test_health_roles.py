"""Health JSON uses schema.ROLES exactly and lab keepers only.

Engine/MSA labels (verse/chorus/interlude) must never be summed into lab
coverage, and no machine-absolute path may leak into the report.
"""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab import report as report_mod
from boo_lab.schema import ROLES


def _lab(tmp_path: Path) -> Path:
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    return lab


def test_build_report_role_vocabulary_is_schema_roles(tmp_path, monkeypatch):
    monkeypatch.delenv("BOO_GP_ROOT", raising=False)
    rep = report_mod.build_report(_lab(tmp_path))

    assert tuple(rep["role_vocabulary"]) == ROLES
    assert "blast" in rep["role_vocabulary"]


def test_lab_coverage_comes_from_keepers_not_engine_role_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("BOO_GP_ROOT", raising=False)
    lab = _lab(tmp_path)
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 4.0,
                    "role": "intro", "source": "human", "heard": True}) + "\n",
        encoding="utf-8",
    )
    # riffs.jsonl carries the ENGINE role vocabulary; it must not become lab riff.
    (lab / "data" / "riffs.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "role": "verse"}) + "\n",
        encoding="utf-8",
    )

    rep = report_mod.build_report(lab)

    assert rep["role_totals"].get("intro") == 1
    assert "verse" not in rep["role_totals"]
    assert all(k in ROLES for k in rep["role_totals"])
    assert "riff" in rep["roles_zero_coverage"]        # no keeper riff
    assert "intro" not in rep["roles_zero_coverage"]


def test_health_paths_are_relative_and_machine_free(tmp_path, monkeypatch):
    monkeypatch.delenv("BOO_GP_ROOT", raising=False)
    lab = _lab(tmp_path)
    rep = report_mod.build_report(lab)

    for entry in rep["files"].values():
        p = entry["path"]
        assert not Path(p).is_absolute(), p
        assert "Users" not in p
        assert not p.startswith("C:")

    text = (lab / "data" / "corpus_health.json").read_text(encoding="utf-8")
    assert "C:\\Users" not in text and "C:/Users" not in text
