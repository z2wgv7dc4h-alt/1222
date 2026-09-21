"""Run every intern over the corpus, cached and resumable.

One command that walks the real map rows and runs each analysis pass, skipping
work that is already on disk. Every step is independent and wrapped so one
failure does not abort the rest; re-running resumes where it stopped. Never
writes `sections.jsonl`.

Steps (default order): stems -> beats -> structure -> drums -> vocals ->
lyrics -> sync -> extract -> figures -> tempo_hints -> compare -> learn ->
status. (Step id is `tempo_hints` with an underscore, matching this file's
own `_step_<name>` dispatch convention; the CLI command it runs is the
hyphenated `boo-lab tempo-hints`.)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

STEPS = ("stems", "beats", "structure", "drums", "vocals", "lyrics",
         "sync", "extract", "figures", "tempo_hints", "compare", "learn", "status")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _keys(path: Path) -> set[tuple[str, str]]:
    return {(r.get("album") or "", r.get("track") or "") for r in _read_jsonl(path)}


def _rows(lab_root: Path, flac_root, gp_root, album):
    from .catalogue import load_map, resolve, filter_album

    mp = Path(lab_root) / "data" / "map.csv"
    rows = [resolve(r, flac_root, gp_root) for r in load_map(mp)] if mp.exists() else []
    return filter_album(rows, album)


def _step_stems(lab_root, rows, cache):
    from .stems import find_stem, run_demucs

    done = 0
    for r in rows:
        fp = r.get("flac_path") or r.get("flac")
        if not fp or not Path(fp).exists():
            continue
        flac = Path(fp)
        if find_stem(flac, cache, "drums"):
            continue
        try:
            run_demucs(flac, cache)
            done += 1
            print("STEMS", r.get("track"))
        except Exception as exc:  # noqa: BLE001
            print("SKIP stems", r.get("track"), exc)
    return {"stems_run": done}


def _step_beats(lab_root, rows, cache):
    from .beats import build_beats

    have = _keys(Path(lab_root) / "data" / "beats.jsonl")
    missing = [r for r in rows
               if (r.get("album") or "", r.get("track") or "") not in have
               and (r.get("flac_path") or r.get("flac"))
               and Path(r.get("flac_path") or r.get("flac") or "").exists()]
    if not missing:
        return {"beats_written": 0}
    return build_beats(lab_root, missing)


def _step_structure(lab_root, rows, cache):
    # build_drafts is cache-aware: cached allin1/SongFormer JSON is reused, so
    # passing all rows only does the missing work.
    from .structure import build_drafts

    return build_drafts(lab_root, rows)


def _step_drums(lab_root, rows, cache):
    from .drums_extract import build_drum_patterns

    return build_drum_patterns(lab_root, rows, cache)


def _step_vocals(lab_root, rows, cache):
    from .vocal_melody import build_vocal_melody

    return build_vocal_melody(lab_root, rows, cache)


def _step_lyrics(lab_root, rows, cache):
    from .lyrics import build_lyrics
    from .stems import find_stem

    out_dir = Path(lab_root) / "work" / "lyrics"
    have = {p.stem for p in out_dir.glob("*.json")} if out_dir.exists() else set()
    from .lyrics import _key

    done = 0
    for r in rows:
        fp = r.get("flac_path") or r.get("flac")
        flac = Path(fp) if fp else None
        track = r.get("track") or ""
        if _key(track) in have:
            continue
        voc = find_stem(flac, cache, "vocals") if flac and flac.exists() else None
        try:
            build_lyrics(lab_root, track, flac if flac and flac.exists() else None, voc)
            done += 1
            print("LYRICS", track)
        except Exception as exc:  # noqa: BLE001
            print("SKIP lyrics", track, exc)
    return {"lyrics_fetched": done}


def _step_sync(lab_root, rows, cache):
    from .sync import sync_track

    have = _keys(Path(lab_root) / "data" / "sync.jsonl")
    done = 0
    for r in rows:
        album = r.get("album") or ""
        track = r.get("track") or ""
        if (album, track) in have:
            continue
        gp = r.get("gp_path") or r.get("gp") or ""
        fp = r.get("flac_path") or r.get("flac") or ""
        if not gp or not Path(gp).exists() or not fp or not Path(fp).exists():
            continue
        try:
            sync_track(lab_root, album, track)
            done += 1
            print("SYNC", track)
        except Exception as exc:  # noqa: BLE001
            print("SKIP sync", track, exc)
    return {"sync_run": done}


def _step_extract(lab_root, rows, cache, album):
    cmd = [sys.executable, "-m", "boo_lab.cli", "extract"]
    if album:
        cmd += ["--album", album]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return {"error": (proc.stderr or proc.stdout or "")[-400:]}
    return {"ok": True}


def _step_figures(lab_root, rows, cache, album):
    from .figures import build_figures

    return build_figures(lab_root, rows, album=album)


def _step_tempo_hints(lab_root, rows, cache, album):
    from .tempo_hints import build_tempo_hints

    return build_tempo_hints(lab_root, rows, album=album)


def _step_compare(lab_root, rows, cache, album):
    from .compare import compare, write_report

    report = compare(Path(lab_root), album)
    write_report(report, Path(lab_root) / "data" / "compare.json")
    try:
        from .learn import run_learn

        run_learn(lab_root, album)
    except Exception:  # noqa: BLE001 - ranking must never fail compare
        pass
    return {"tracks": report["micro"]["n_tracks"], "f_0_5": report["micro"]["f_0_5"]}


def _step_learn(lab_root, rows, cache, album):
    from .learn import run_learn

    rank = run_learn(lab_root, album)
    return {"prefer": rank.get("prefer"), "n_voted": rank.get("n_voted")}


def _step_status(lab_root, rows, cache):
    from .status import run_status

    return run_status(lab_root)


def run_interns(lab_root, flac_root=None, gp_root=None, *, album=None,
                steps=None, cache=None) -> dict:
    lab_root = Path(lab_root)
    cache = Path(cache) if cache else lab_root / "work" / "stems"
    steps = list(steps) if steps else list(STEPS)
    rows = _rows(lab_root, flac_root, gp_root, album)
    results: dict = {}
    for step in steps:
        print("=== interns:", step, "===")
        try:
            if step == "stems":
                results[step] = _step_stems(lab_root, rows, cache)
            elif step == "beats":
                results[step] = _step_beats(lab_root, rows, cache)
            elif step == "structure":
                results[step] = _step_structure(lab_root, rows, cache)
            elif step == "drums":
                results[step] = _step_drums(lab_root, rows, cache)
            elif step == "vocals":
                results[step] = _step_vocals(lab_root, rows, cache)
            elif step == "lyrics":
                results[step] = _step_lyrics(lab_root, rows, cache)
            elif step == "sync":
                results[step] = _step_sync(lab_root, rows, cache)
            elif step == "extract":
                results[step] = _step_extract(lab_root, rows, cache, album)
            elif step == "figures":
                results[step] = _step_figures(lab_root, rows, cache, album)
            elif step == "tempo_hints":
                results[step] = _step_tempo_hints(lab_root, rows, cache, album)
            elif step == "compare":
                results[step] = _step_compare(lab_root, rows, cache, album)
            elif step == "learn":
                results[step] = _step_learn(lab_root, rows, cache, album)
            elif step == "status":
                results[step] = _step_status(lab_root, rows, cache)
            else:
                results[step] = {"error": "unknown step"}
        except Exception as exc:  # noqa: BLE001
            results[step] = {"error": str(exc)}
            print("interns step failed", step, exc)
    return results
