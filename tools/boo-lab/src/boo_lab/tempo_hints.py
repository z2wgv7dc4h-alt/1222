"""Tempo-automation boundary hints -- candidate section cuts, not boxes.

A BPM jump inside a tab-notes pack (`raw/parts/N.json.automations.tempo`,
already parsed by `tabnotes.tempo_map`) often lands on a real section change
in this genre, but it never implies a role (verse vs breakdown vs outro) --
so this module emits point-in-time hint rows only, never a
`sections.jsonl`-shaped box. Machines never write keepers; output is drafts
with `source="tempo-automation"`, written to `data/tempo_hints.jsonl` under
the same never-blank-on-a-zero-row law as `beats`/`structure`/`figures`.
Tabnotes-only: a matched GP file's own tempo automations aren't wired here.
"""
from __future__ import annotations

import json
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def build_tempo_hints(lab_root, rows, *, album=None, track=None) -> dict:
    """One row per BPM change in each song's tab-notes pack. Replaces only
    the songs it rebuilt (keyed by album+track); a run that yields zero rows
    leaves an existing `data/tempo_hints.jsonl` untouched."""
    from .schema import write_jsonl_atomic
    from .tabnotes import discover_pack, load_pack, tempo_map

    lab_root = Path(lab_root)
    out = lab_root / "data" / "tempo_hints.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    if album and track:
        from .catalogue import resolve_row

        target = resolve_row(rows, album, track)
        if target is not None:
            album = target.get("album") or album
            track = target.get("track") or track
    akey = album.casefold() if album else None
    tkey = track.casefold() if track else None

    sync_by = {(s.get("album"), s.get("track")): s
               for s in _read_jsonl(lab_root / "data" / "sync.jsonl")}

    produced: list[dict] = []
    rebuilt: set[tuple[str, str]] = set()
    songs = 0
    skipped = 0

    for r in rows:
        ra = r.get("album") or ""
        rt = r.get("track") or ""
        if akey is not None and ra.casefold() != akey:
            continue
        if tkey is not None and rt.casefold() != tkey:
            continue

        try:
            pack_path = discover_pack(lab_root, ra, rt)
        except Exception as exc:
            print("SKIP tempo-hints", rt, exc)
            skipped += 1
            continue
        if pack_path is None:
            skipped += 1
            continue

        try:
            tmap = tempo_map(load_pack(pack_path))
        except Exception as exc:
            print("SKIP tempo-hints", rt, exc)
            skipped += 1
            continue

        rebuilt.add((ra, rt))
        songs += 1
        if len(tmap) < 2:
            print("TEMPO-HINTS", rt, "0 changes")
            continue

        trusted = bool((sync_by.get((ra, rt)) or {}).get("sync_ok") is True)
        for i in range(1, len(tmap)):
            sec, bpm_after = tmap[i]
            bpm_before = tmap[i - 1][1]
            produced.append({
                "album": ra, "track": rt,
                "sec": round(sec, 3) if trusted else None,
                "bpm_before": bpm_before, "bpm_after": bpm_after,
                "times_trusted": trusted, "source": "tempo-automation",
            })
        print("TEMPO-HINTS", rt, len(tmap) - 1, "change(s)",
              "(times trusted)" if trusted else "(sec untrusted; sync not ok)")

    if not produced:
        print("tempo-hints: 0 rows written; leaving", out.name, "untouched")
        return {"songs": songs, "written": 0, "skipped": skipped, "out": str(out)}

    existing = _read_jsonl(out)
    keep = [x for x in existing if (x.get("album"), x.get("track")) not in rebuilt]
    write_jsonl_atomic(out, keep + produced)
    return {"songs": songs, "written": len(produced), "skipped": skipped, "out": str(out)}


def load_tempo_hints(lab_root, album, track) -> list[dict]:
    """`data/tempo_hints.jsonl` rows for one song (empty when not computed)."""
    path = Path(lab_root) / "data" / "tempo_hints.jsonl"
    return [r for r in _read_jsonl(path)
            if (r.get("album") or "") == (album or "")
            and (r.get("track") or "") == (track or "")]
