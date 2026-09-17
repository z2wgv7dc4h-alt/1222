"""Tests for src/boo_lab/lyrics.py -- plain-vs-synced handling, using a
monkeypatched LRCLIB fetch (no network)."""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab import lyrics as ly


def _plain_only(track, artist="Born of Osiris", duration=None):
    return {"ok": True, "source": "lrclib", "instrumental": False,
            "plain": "line one\n\nline two\n", "synced": "", "lines": []}


def test_parse_lrc_gives_start_and_end():
    lines = ly.parse_lrc("[00:01.00] hello\n[00:03.50] world\n")
    assert lines[0]["start"] == 1.0
    assert lines[0]["text"] == "hello"
    assert lines[0]["end"] == 3.5
    assert [ln["text"] for ln in lines] == ["hello", "world"]


def test_build_lyrics_surfaces_plain_when_no_synced(tmp_path, monkeypatch):
    monkeypatch.setattr(ly, "fetch_lrclib", _plain_only)
    payload = ly.build_lyrics(tmp_path, "02 - Elimination", None, None)
    assert payload["lines"] == []
    assert payload["plain_lines"] == ["line one", "line two"]
    assert payload["note"].startswith("lrclib plain")
    # the cache round-trips plain_lines
    assert ly.load_lyrics(tmp_path, "02 - Elimination")["plain_lines"] == ["line one", "line two"]


def test_build_lyrics_keeps_synced_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ly, "fetch_lrclib",
        lambda track, artist="Born of Osiris", duration=None: {
            "ok": True, "plain": "a\nb", "synced": "[00:01.00] hi",
            "lines": [{"start": 1.0, "end": 1.4, "text": "hi"}],
        },
    )
    payload = ly.build_lyrics(tmp_path, "T", None, None)
    assert [ln["text"] for ln in payload["lines"]] == ["hi"]
    assert payload["plain_lines"] == ["a", "b"]
    assert payload["note"] == "lrclib synced"


def test_load_lyrics_backfills_plain_lines_from_old_cache(tmp_path):
    d = tmp_path / "work" / "lyrics"
    d.mkdir(parents=True)
    (d / "t.json").write_text(
        json.dumps({"lines": [], "plain": "x\ny", "note": "lrclib plain"}), encoding="utf-8"
    )
    assert ly.load_lyrics(tmp_path, "T")["plain_lines"] == ["x", "y"]


def test_save_lyrics_preserves_cached_plain_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(ly, "fetch_lrclib", _plain_only)
    ly.build_lyrics(tmp_path, "T", None, None)
    payload = ly.save_lyrics(tmp_path, "T", [{"start": 5.0, "text": "a"}])
    assert payload["plain_lines"] == ["line one", "line two"]
    assert [ln["text"] for ln in payload["lines"]] == ["a"]


def test_load_lyrics_missing_is_empty(tmp_path):
    got = ly.load_lyrics(tmp_path, "nope")
    assert got["lines"] == []
    assert "plain_lines" not in got
