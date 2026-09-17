"""Tests for src/boo_lab/pack.py -- tiny synthetic WAV/FLAC fixtures under
tmp_path only; no real audio, matching the package's synthetic-fixture
discipline."""
from __future__ import annotations

import json

import numpy as np
import pytest

soundfile = pytest.importorskip("soundfile")

from boo_lab import pack as packmod  # noqa: E402
from boo_lab import stems as stemsmod  # noqa: E402

_SR = 8000
_SECONDS = 2.0
_CORE_STEMS = ("drums", "bass", "other", "vocals")
_SIX_STEMS = ("drums", "bass", "other", "vocals", "guitar", "piano")


def _write_audio(path, seconds=_SECONDS, sr=_SR, fmt=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.zeros((int(seconds * sr), 2), dtype="float32")
    soundfile.write(str(path), data, sr, format=fmt)
    return path


def _lab_with_one_section(tmp_path, role="intro", start=0.0, end=1.0):
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    rec = {"album": "A", "track": "T", "start": start, "end": end, "role": role, "source": "human", "heard": True}
    (tmp_path / "data" / "sections.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    return _write_audio(tmp_path / "T.flac", fmt="FLAC")


def test_build_pack_includes_guitar_and_piano_from_6s_cache(tmp_path):
    flac = _lab_with_one_section(tmp_path)
    cache = tmp_path / "cache"
    sdir = cache / "htdemucs_6s" / "T"
    for name in _SIX_STEMS:
        _write_audio(sdir / f"{name}.wav")

    report = packmod.build_pack(tmp_path, [{"album": "A", "track": "T", "flac_path": str(flac)}], cache)

    assert report["written"] == 1
    box = tmp_path / "work" / "pack" / "A_T_00_intro"
    meta = json.loads((box / "meta.json").read_text(encoding="utf-8"))
    for label in ("drums", "bass", "other", "guitar", "piano", "vocals", "no_vocals"):
        assert label in meta["files"], label
        assert (box / f"{label}.wav").stat().st_size > 0


def test_build_pack_4stem_fallback_packs_without_guitar_piano(tmp_path, monkeypatch):
    flac = _lab_with_one_section(tmp_path)
    cache = tmp_path / "cache"
    sdir = cache / "htdemucs" / "T"
    for name in _CORE_STEMS:
        _write_audio(sdir / f"{name}.wav")

    calls = []
    monkeypatch.setattr(stemsmod, "run_demucs", lambda *a, **k: calls.append(1))

    report = packmod.build_pack(tmp_path, [{"album": "A", "track": "T", "flac_path": str(flac)}], cache)

    assert report["written"] == 1
    assert calls == []  # a full 4-stem cache must never force a re-separation
    box = tmp_path / "work" / "pack" / "A_T_00_intro"
    meta = json.loads((box / "meta.json").read_text(encoding="utf-8"))
    assert "drums" in meta["files"]
    assert "guitar" not in meta["files"]
    assert "piano" not in meta["files"]
