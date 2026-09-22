"""Tests for src/boo_lab/status.py -- counts from files, block-only rewrite."""
from __future__ import annotations

import json

from boo_lab import status
from boo_lab.catalogue import save_map


def _lab(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "role": "riff", "source": "human",
                    "heard": True}) + "\n"
        + json.dumps({"album": "A", "track": "U", "role": "riff", "source": "guess",
                      "heard": False}) + "\n",
        encoding="utf-8",
    )
    (lab / "data" / "drafts.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "role": "riff", "source": "msa-draft"}) + "\n",
        encoding="utf-8",
    )
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "sync_ok": True}) + "\n"
        + json.dumps({"album": "A", "track": "U", "sync_ok": False}) + "\n",
        encoding="utf-8",
    )
    save_map(lab / "data" / "map.csv", [{"album": "A", "track": "T"}])
    return lab


def test_refresh_status_rewrites_only_the_block(tmp_path):
    lab = _lab(tmp_path)
    status_path = lab / "STATUS.md"
    status_path.write_text(
        "# S\n\n" + status.START + "\nSTALE_BLOCK\n" + status.END
        + "\n\nProse 999 tests pass.\n",
        encoding="utf-8",
    )

    report = status.refresh_status(lab, status_path=status_path)

    text = status_path.read_text(encoding="utf-8")
    assert report["updated"] is True
    assert "keepers: 1 row(s) across 1 track(s)" in text   # keepers-only reader
    assert "drafts: 1 row(s); sources: msa-draft" in text
    assert "sync: 1 ok / 2 row(s)" in text
    assert "map.csv: 1 row(s)" in text
    assert "STALE_BLOCK" not in text
    assert "Prose 999 tests pass." in text                  # test line untouched


def test_refresh_status_counts_figures_and_tempo_hints(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "figures.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "figure_id": "riff-A"}) + "\n"
        + json.dumps({"album": "A", "track": "T", "figure_id": "bass-riff-A"}) + "\n"
        + json.dumps({"album": "A", "track": "U", "figure_id": "riff-A"}) + "\n",
        encoding="utf-8",
    )
    (lab / "data" / "tempo_hints.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "sec": 5.0}) + "\n",
        encoding="utf-8",
    )
    status_path = lab / "STATUS.md"
    status_path.write_text(
        "# S\n\n" + status.START + "\nold\n" + status.END + "\n", encoding="utf-8")

    status.refresh_status(lab, status_path=status_path)

    text = status_path.read_text(encoding="utf-8")
    assert "figures: 3 row(s) across 2 track(s)" in text
    assert "tempo hints: 1 row(s) across 1 track(s)" in text


def test_refresh_status_zero_figures_and_tempo_hints(tmp_path):
    lab = _lab(tmp_path)  # no figures.jsonl / tempo_hints.jsonl written
    status_path = lab / "STATUS.md"
    status_path.write_text(
        "# S\n\n" + status.START + "\nold\n" + status.END + "\n", encoding="utf-8")

    status.refresh_status(lab, status_path=status_path)

    text = status_path.read_text(encoding="utf-8")
    assert "figures: 0 row(s) across 0 track(s)" in text
    assert "tempo hints: 0 row(s) across 0 track(s)" in text


def test_empty_gold_reports_zero_keepers_and_prefer_none(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sections.jsonl").write_text("", encoding="utf-8")

    counts = status.collect_counts(tmp_path)

    assert counts["keeper_rows"] == 0 and counts["keeper_tracks"] == 0
    assert counts["prefer"] == "none"
    block = status.render_block(counts)
    assert "keepers: 0 row(s) across 0 track(s)" in block
    assert "prefer=: none" in block


def test_holdout_only_keepers_report_prefer_none(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "holdout.csv").write_text(
        "album,track\nA,T\n", encoding="utf-8")
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "role": "riff",
                    "source": "human", "heard": True}) + "\n", encoding="utf-8")

    assert status.collect_counts(lab)["prefer"] == "none"


def test_status_never_writes_a_pytest_count(tmp_path):
    lab = _lab(tmp_path)
    status_path = lab / "STATUS.md"
    status_path.write_text(
        "# S\n\n" + status.START + "\nstale\n" + status.END
        + "\n\nNow: run pytest -q; do not freeze the number here.\n",
        encoding="utf-8",
    )

    status.refresh_status(lab, status_path=status_path)

    text = status_path.read_text(encoding="utf-8")
    assert "passed" not in text
    assert text.rstrip().endswith("Now: run pytest -q; do not freeze the number here.")
    assert "passed" not in status.render_block(status.collect_counts(lab))


def test_missing_markers_is_not_updated(tmp_path):
    lab = _lab(tmp_path)
    status_path = lab / "STATUS.md"
    status_path.write_text("# S\n\nno markers here\n", encoding="utf-8")

    assert status.refresh_status(lab, status_path=status_path)["updated"] is False
    assert status_path.read_text(encoding="utf-8") == "# S\n\nno markers here\n"
