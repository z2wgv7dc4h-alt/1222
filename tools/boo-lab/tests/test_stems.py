"""Tests for src/boo_lab/stems.py -- subprocess/env wiring only; no real
demucs run."""
from __future__ import annotations

from boo_lab import stems


def test_run_demucs_forces_utf8_subprocess_env(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured.update(kw)

        class _Result:
            pass

        return _Result()

    monkeypatch.setattr(stems.subprocess, "run", fake_run)
    out = stems.run_demucs(tmp_path / "a.flac", tmp_path / "out")

    assert captured["cmd"][:3] == [stems.sys.executable, "-m", "demucs"]
    assert captured["env"].get("PYTHONUTF8") == "1"
    assert captured["env"].get("PYTHONIOENCODING") == "utf-8"
    assert out == tmp_path / "out" / "htdemucs_6s" / "a"
