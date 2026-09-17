"""Tests for src/boo_lab/hear.py -- single-song heard migration. Synthetic
sections.jsonl under tmp_path; no real corpus."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from boo_lab import hear


def _row(album, track, role, source="human", heard=None, start=0.0, end=4.0, figure_id=None):
    rec = {"album": album, "track": track, "role": role, "source": source,
           "start": start, "end": end, "figure_id": figure_id or (role + "-A")}
    if heard is not None:
        rec["heard"] = heard
    return rec


def _lab(tmp_path, rows):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "sections.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return lab


def _rows(base):
    path = Path(base) / "data" / "sections.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _by_role(rows, track):
    return {r["role"]: r for r in rows if r["track"] == track}


def test_flips_only_named_track_keepers(tmp_path):
    lab = _lab(tmp_path, [
        _row("A", "T", "riff"),                           # keeper, no heard -> flip
        _row("A", "T", "hook", source="guess-accepted"),   # keeper -> flip
        _row("A", "T", "breakdown", source="guess"),       # not keeper -> untouched
        _row("A", "T", "solo", source="msa-draft"),        # not keeper -> untouched
        _row("A", "T", "pulse", heard=True),               # already heard -> not counted
        _row("A", "Other", "riff"),                        # other track -> untouched
    ])
    report = hear.mark_heard(lab, "A", "T")
    assert report["flipped"] == 2

    t = _by_role(_rows(lab), "T")
    assert t["riff"]["heard"] is True
    assert t["hook"]["heard"] is True
    assert "heard" not in t["breakdown"]
    assert "heard" not in t["solo"]
    assert t["pulse"]["heard"] is True

    other = _by_role(_rows(lab), "Other")["riff"]
    assert "heard" not in other


def test_does_not_change_any_other_field(tmp_path):
    before = _row("A", "T", "riff", start=1.25, end=3.5, figure_id="riff-B")
    lab = _lab(tmp_path, [before])
    hear.mark_heard(lab, "A", "T")
    after = _rows(lab)[0]
    assert after["heard"] is True
    for key in ("role", "start", "end", "figure_id", "source", "album", "track"):
        assert after[key] == before[key]


def test_refuses_without_track(tmp_path):
    lab = _lab(tmp_path, [_row("A", "T", "riff")])
    with pytest.raises(ValueError):
        hear.mark_heard(lab, "A", None)


def test_refuses_without_album(tmp_path):
    lab = _lab(tmp_path, [_row("A", "T", "riff")])
    with pytest.raises(ValueError):
        hear.mark_heard(lab, None, "T")


def test_hear_refuses_malformed_sections_and_leaves_it(tmp_path):
    lab = _lab(tmp_path, [_row("A", "T", "riff")])
    path = lab / "data" / "sections.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + "{ not json\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ValueError):
        hear.mark_heard(lab, "A", "T")

    assert path.read_text(encoding="utf-8") == before  # malformed line never dropped


def test_hear_write_failure_leaves_file_untouched(tmp_path, monkeypatch):
    lab = _lab(tmp_path, [_row("A", "T", "riff")])
    path = lab / "data" / "sections.jsonl"
    before = path.read_text(encoding="utf-8")

    def _boom(p, rows):
        raise OSError("disk full")

    monkeypatch.setattr(hear, "write_jsonl_atomic", _boom)
    with pytest.raises(OSError):
        hear.mark_heard(lab, "A", "T")

    assert path.read_text(encoding="utf-8") == before  # atomic write failed safely


def test_cli_hear_refuses_without_track(tmp_path, monkeypatch):
    from boo_lab import cli

    monkeypatch.setattr(cli, "root", lambda: tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "sections.jsonl").write_text(
        json.dumps(_row("A", "T", "riff")) + "\n", encoding="utf-8")

    rc = cli.main(["hear", "--album", "A"])

    assert rc == 1
    assert "heard" not in _rows(tmp_path)[0]
