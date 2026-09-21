"""CLI `extract` command: per-song notes_source resolution via tab_plan.

A song with no GP and no pack resolves notes=None and must fall through to
the existing audio fallback (or a clean skip when there is no FLAC either),
never be silently dropped -- and an all-skip run must not blank riffs.jsonl.
"""
from __future__ import annotations

from pathlib import Path

from boo_lab import cli
from boo_lab.catalogue import save_map


def _row(album="A", track="T"):
    return {"album": album, "track": track, "year": "", "flac": "", "gp": "",
            "tuning": "", "match": "unknown", "notes": "", "flac_sha256": ""}


def _lab(tmp_path, monkeypatch, rows):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    save_map(lab / "data" / "map.csv", rows)
    monkeypatch.setattr(cli, "root", lambda: lab)
    monkeypatch.setattr(cli, "data_dir", lambda: lab / "data")
    # No filesystem GP discovery: the song truly has neither GP nor pack.
    from boo_lab import guess

    monkeypatch.setattr(guess, "_prefer_tab", lambda gp, track: None)
    return lab


def test_extract_notes_none_song_skips_cleanly_and_keeps_riffs_file(tmp_path, monkeypatch, capsys):
    lab = _lab(tmp_path, monkeypatch, [_row()])
    out = lab / "data" / "riffs.jsonl"
    out.write_text('{"album":"A","track":"KEPT"}\n', encoding="utf-8")
    before = out.read_text(encoding="utf-8")

    rc = cli.main(["extract"])

    printed = capsys.readouterr().out
    assert rc == 0
    assert "SKIP extract" in printed              # considered, not dropped
    assert "leaving riffs.jsonl untouched" in printed
    assert out.read_text(encoding="utf-8") == before


def test_extract_notes_none_song_with_flac_attempts_audio_fallback(tmp_path, monkeypatch, capsys):
    lab = _lab(tmp_path, monkeypatch, [_row()])
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    # Absolute flac path survives resolve() even with no BOO_FLAC_ROOT.
    save_map(lab / "data" / "map.csv", [dict(_row(), flac=str(flac))])

    from boo_lab import audio_extract

    called = []

    def _fake_audio(path, stems, song):
        called.append((path, song))
        return []

    monkeypatch.setattr(audio_extract, "extract_fragments_from_audio", _fake_audio)

    rc = cli.main(["extract"])

    assert rc == 0
    assert called and called[0][1] == "A::T"


def test_extract_pack_notes_resolves_pack_source(tmp_path, monkeypatch, capsys):
    from boo_lab import extract as ex

    lab = _lab(tmp_path, monkeypatch, [dict(_row(track="Tiny Pack"), match="no")])
    import shutil

    src = Path(__file__).parent / "fixtures" / "tabnotes_tiny"
    (lab / "data" / "tabnotes").mkdir(parents=True)
    shutil.copytree(src, lab / "data" / "tabnotes" / "tabnotes_tiny")

    calls = []
    real = ex.extract_riffs_from_pack

    def _spy(pack, song, human_sections=None, **k):
        calls.append((pack.title, song))
        return real(pack, song, human_sections=human_sections, **k)

    monkeypatch.setattr(ex, "extract_riffs_from_pack", _spy)

    rc = cli.main(["extract"])

    assert rc == 0
    assert calls and calls[0] == ("Tiny Pack", "A::Tiny Pack")
