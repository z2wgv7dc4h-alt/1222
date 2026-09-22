"""Tests for src/boo_lab/interns.py -- the cached, resumable pass runner.

Every step's real work is mocked; these only prove the dispatcher order, the
resume/skip bookkeeping, that one failure never aborts the rest, and that the
compare/learn/extract steps call the same entry points the CLI does."""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab import compare, interns, learn


def _lab(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    return lab


def _fake_steps(monkeypatch, calls):
    for name in interns.STEPS:
        def make(n):
            def _fn(lab_root, rows, cache, *args, **kwargs):
                calls.append(n)
                return {"step": n}
            return _fn
        monkeypatch.setattr(interns, "_step_" + name, make(name))


def test_runs_every_step_in_order(monkeypatch, tmp_path):
    lab = _lab(tmp_path)
    calls: list[str] = []
    _fake_steps(monkeypatch, calls)
    monkeypatch.setattr(interns, "_rows", lambda *a, **k: [])

    report = interns.run_interns(lab)

    skipped = set(interns._EMPTY_GOLD_SKIP)
    assert calls == [s for s in interns.STEPS if s not in skipped]
    assert report["stems"] == {"step": "stems"}
    assert report["status"] == {"step": "status"}
    for name in skipped:
        assert report[name] == {"skipped": "no keepers"}


def test_explicit_steps_run_extract_on_empty_gold(monkeypatch, tmp_path):
    lab = _lab(tmp_path)
    calls: list[str] = []
    _fake_steps(monkeypatch, calls)
    monkeypatch.setattr(interns, "_rows", lambda *a, **k: [])
    interns.run_interns(lab, steps=["extract", "status"])
    assert calls == ["extract", "status"]


def test_subset_steps_preserve_given_order(monkeypatch, tmp_path):
    lab = _lab(tmp_path)
    calls: list[str] = []
    _fake_steps(monkeypatch, calls)
    monkeypatch.setattr(interns, "_rows", lambda *a, **k: [])

    interns.run_interns(lab, steps=["status", "beats"])

    assert calls == ["status", "beats"]


def test_one_failure_does_not_abort_the_rest(monkeypatch, tmp_path):
    lab = _lab(tmp_path)
    monkeypatch.setattr(interns, "_rows", lambda *a, **k: [])

    def _boom(*_a, **_k):
        raise RuntimeError("GPU on fire")

    monkeypatch.setattr(interns, "_step_beats", _boom)
    monkeypatch.setattr(interns, "_step_status", lambda *a, **k: {"ok": True})

    report = interns.run_interns(lab, steps=["beats", "status"])

    assert "GPU on fire" in report["beats"]["error"]
    assert report["status"] == {"ok": True}


def test_unknown_step_is_reported_not_raised(monkeypatch, tmp_path):
    lab = _lab(tmp_path)
    monkeypatch.setattr(interns, "_rows", lambda *a, **k: [])

    report = interns.run_interns(lab, steps=["bogus"])

    assert report["bogus"] == {"error": "unknown step"}


def test_compare_step_writes_report_and_runs_learn(monkeypatch, tmp_path):
    lab = _lab(tmp_path)
    written: dict = {}
    voted: dict = {}

    monkeypatch.setattr(compare, "compare", lambda root, album=None, track=None: {
        "tracks": [],
        "micro": {"n_tracks": 2, "n_rows": 2, "f_0_5": 0.5,
                  "f_3_0": 0.6, "role_agree_3_0": 0.2}})
    monkeypatch.setattr(compare, "write_report", lambda report, path: written.update(path=Path(path)))

    def _learn(root, album=None):
        voted["album"] = album
        return {"prefer": None}

    monkeypatch.setattr(learn, "run_learn", _learn)

    out = interns._step_compare(lab, [], None, "A")

    assert out == {"tracks": 2, "f_0_5": 0.5}
    assert written["path"] == lab / "data" / "compare.json"
    assert voted["album"] == "A"


def test_learn_step_returns_rank_summary(monkeypatch, tmp_path):
    lab = _lab(tmp_path)
    monkeypatch.setattr(learn, "run_learn",
                        lambda root, album=None: {"prefer": "msa-draft", "n_voted": 7})

    assert interns._step_learn(lab, [], None, "A") == {"prefer": "msa-draft", "n_voted": 7}


def test_extract_step_passes_album_flag(monkeypatch, tmp_path):
    lab = _lab(tmp_path)
    captured: dict = {}

    class _Done:
        returncode = 0
        stdout = ""
        stderr = ""

    def _run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Done()

    monkeypatch.setattr(interns.subprocess, "run", _run)

    assert interns._step_extract(lab, [], None, "A") == {"ok": True}
    assert captured["cmd"][-2:] == ["--album", "A"]


def test_extract_step_reports_stderr_on_failure(monkeypatch, tmp_path):
    lab = _lab(tmp_path)

    class _Done:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(interns.subprocess, "run", lambda cmd, **k: _Done())

    assert interns._step_extract(lab, [], None, None) == {"error": "boom"}


def test_keys_dedupes_pairs(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text(
        json.dumps({"album": "A", "track": "T"}) + "\n"
        + json.dumps({"album": "A", "track": "T"}) + "\n"
        + json.dumps({"album": "B", "track": "T"}) + "\n",
        encoding="utf-8")

    assert interns._keys(path) == {("A", "T"), ("B", "T")}
