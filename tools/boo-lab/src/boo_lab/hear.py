"""Mark already-keeper pins as heard=True for ONE song (migration helper).

Old `sections.jsonl` rows predate the `heard` flag. This flips `heard` to
true on rows that are already keepers (`schema.is_keeper`: human /
guess-accepted / missing source) for a single album+track only. It never
changes role/time/figure_id/source, never touches `guess` / `msa-draft`
rows, and refuses to run without both `--album` and `--track` (never the
whole catalog).
"""
from __future__ import annotations

import json
from pathlib import Path

from .schema import is_keeper


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


def mark_heard(lab_root: Path, album: str | None, track: str | None) -> dict:
    """Flip `heard=true` on already-keeper rows for `album` + `track` only.
    Raises `ValueError` when either is missing."""
    if not album or not track:
        raise ValueError("need both --album and --track (never the whole catalog)")

    path = Path(lab_root) / "data" / "sections.jsonl"
    rows = _read_jsonl(path)
    flipped = 0
    for rec in rows:
        if (rec.get("album") or "") != album or (rec.get("track") or "") != track:
            continue
        if is_keeper(rec.get("source")) and not rec.get("heard"):
            rec["heard"] = True
            flipped += 1

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec) + "\n")
    return {"album": album, "track": track, "flipped": flipped, "rows": len(rows)}
