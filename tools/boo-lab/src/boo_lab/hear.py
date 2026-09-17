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

from .schema import is_keeper, write_jsonl_atomic


def _read_jsonl(path: Path) -> tuple[list[dict], list[int]]:
    """`(rows, malformed_line_numbers)`. Malformed lines are reported, never
    silently dropped -- the caller decides, because rewriting the file would
    otherwise destroy them."""
    if not path.exists():
        return [], []
    rows: list[dict] = []
    malformed: list[int] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            malformed.append(lineno)
            continue
        if not isinstance(rec, dict):
            malformed.append(lineno)
            continue
        rows.append(rec)
    return rows, malformed


def mark_heard(lab_root: Path, album: str | None, track: str | None) -> dict:
    """Flip `heard=true` on already-keeper rows for `album` + `track` only.
    Raises `ValueError` when either is missing, or when `sections.jsonl`
    contains a malformed line (fail closed -- never drop it on rewrite)."""
    if not album or not track:
        raise ValueError("need both --album and --track (never the whole catalog)")

    path = Path(lab_root) / "data" / "sections.jsonl"
    rows, malformed = _read_jsonl(path)
    if malformed:
        raise ValueError(
            "sections.jsonl has malformed line(s) %s; fix them before `hear`" % malformed
        )
    flipped = 0
    for rec in rows:
        if (rec.get("album") or "") != album or (rec.get("track") or "") != track:
            continue
        if is_keeper(rec.get("source")) and not rec.get("heard"):
            rec["heard"] = True
            flipped += 1

    if path.exists() or rows:
        write_jsonl_atomic(path, rows)  # atomic: a failure leaves the file intact
    return {"album": album, "track": track, "flipped": flipped, "rows": len(rows)}
