"""Tests for src/boo_lab/structure.build_drafts -- MSA + SongFormer drafts
into drafts.jsonl only. Intern APIs are mocked; no allin1/torch."""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab import structure


def _lab(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    flac = tmp_path / "T.flac"
    flac.write_bytes(b"x")
    return lab, flac


def _drafts(lab):
    path = lab / "data" / "drafts.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_writes_msa_and_songformer_sources(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)
    monkeypatch.setattr(structure, "run_allin1", lambda p: {
        "bpm": 120,
        "segments": [{"start": 0, "end": 4, "label": "verse"},
                     {"start": 4, "end": 8, "label": "chorus"}],
    })
    monkeypatch.setattr(structure, "songformer_available", lambda: True)
    monkeypatch.setattr(structure, "run_songformer", lambda p: {
        "segments": [{"start": 0, "end": 6, "label": "intro"},
                     {"start": 6, "end": 12, "label": "break"}],
    })

    report = structure.build_drafts(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    assert report["written"] == 4 and report["songformer"] is True
    drafts = _drafts(lab)
    assert {d["source"] for d in drafts} == {"msa-draft", "songformer-draft"}
    tagged = {d["source"] + "|" + d["role"] for d in drafts}
    assert {"msa-draft|riff", "msa-draft|hook"} <= tagged
    assert {"songformer-draft|intro", "songformer-draft|breakdown"} <= tagged
    # never writes sections.jsonl
    assert not (lab / "data" / "sections.jsonl").exists()


def test_allin1_failure_still_writes_songformer(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)

    def boom(_p):
        raise RuntimeError("no allin1")

    monkeypatch.setattr(structure, "run_allin1", boom)
    monkeypatch.setattr(structure, "songformer_available", lambda: True)
    monkeypatch.setattr(structure, "run_songformer", lambda p: {"segments": [{"start": 0, "end": 4, "label": "intro"}]})

    report = structure.build_drafts(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    assert report["written"] == 1
    assert _drafts(lab)[0]["source"] == "songformer-draft"


def test_no_songformer_only_msa(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)
    monkeypatch.setattr(structure, "run_allin1", lambda p: {"segments": [{"start": 0, "end": 4, "label": "verse"}]})
    monkeypatch.setattr(structure, "songformer_available", lambda: False)

    report = structure.build_drafts(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    assert report["written"] == 1 and report["songformer"] is False
    assert {d["source"] for d in _drafts(lab)} == {"msa-draft"}


def test_preserves_other_album_drafts(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)
    (lab / "data" / "drafts.jsonl").write_text(
        json.dumps({"album": "Other", "track": "X", "role": "riff", "source": "msa-draft"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(structure, "run_allin1", lambda p: {"segments": [{"start": 0, "end": 4, "label": "verse"}]})
    monkeypatch.setattr(structure, "songformer_available", lambda: False)

    structure.build_drafts(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    albums = {d["album"] for d in _drafts(lab)}
    assert albums == {"Other", "A"}
