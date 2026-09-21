"""Export keeper pins as JAMS 0.3, split into figure vs function layers.

A model never enters the keeper file: this reads `data/sections.jsonl`
(keepers only) and writes one `.jams` per song. It never writes
`sections.jsonl`, and it skips validation-split songs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .holdout import ensure_holdout, load_holdout, split_for
from .schema import FIGURE_ROLES, FUNCTION_ROLES, canonical_role, is_keeper, load_section_rows


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


def keeper_boxes_by_song(lab_root: Path) -> dict[tuple[str, str], list[dict]]:
    """Keeper boxes only: `schema.is_keeper(source)` AND `heard`."""
    out: dict[tuple[str, str], list[dict]] = {}
    for rec in load_section_rows(Path(lab_root) / "data" / "sections.jsonl"):
        if not is_keeper(rec.get("source")) or not rec.get("heard"):
            continue
        key = (rec.get("album") or "", rec.get("track") or "")
        out.setdefault(key, []).append(rec)
    return out


def _observation(rec: dict) -> dict:
    start = float(rec.get("start", 0.0))
    end = float(rec.get("end", 0.0))
    role = canonical_role(rec.get("role"))
    return {
        "time": round(start, 3),
        "duration": round(max(0.0, end - start), 3),
        "value": {"role": role, "figure_id": rec.get("figure_id") or (role + "-A")},
        "confidence": 1.0 if rec.get("heard") else 0.0,
    }


def build_jam(album: str, track: str, boxes: list[dict]) -> dict:
    figure = [_observation(b) for b in boxes if canonical_role(b.get("role")) in FIGURE_ROLES]
    function = [_observation(b) for b in boxes if canonical_role(b.get("role")) in FUNCTION_ROLES]
    meta = {"annotator": {"name": "boo-lab"}}
    return {
        "file_metadata": {"title": track, "artist": album, "release": album},
        "annotations": [
            {"namespace": "segment_lab_figure", "annotation_metadata": meta, "data": figure},
            {"namespace": "segment_lab_function", "annotation_metadata": meta, "data": function},
        ],
        "sandbox": {"source": "boo-lab"},
    }


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s or "").strip("_") or "x"


def export_jam_one(lab_root, album, track, out_dir=None) -> dict:
    """One song's keeper JAMS to `work/jams/<album>/<track>.jams` (or
    `out_dir`). Refuses -- never writes -- when the song has no keepers or is a
    validation-split song. Never touches `sections.jsonl`."""
    lab_root = Path(lab_root)
    boxes = [b for (a, t), bs in keeper_boxes_by_song(lab_root).items()
             if a == (album or "") and t == (track or "") for b in bs]
    if not boxes:
        return {"written": 0, "reason": "no keepers to export"}
    if split_for(album, track, load_holdout(lab_root)) == "val":
        return {"written": 0, "reason": "VAL song - JAMS export is skipped"}
    dest_dir = Path(out_dir) if out_dir else lab_root / "work" / "jams"
    dest = dest_dir / _safe(album) / (_safe(track) + ".jams")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(build_jam(album, track, boxes), indent=2), encoding="utf-8")
    return {"written": 1, "path": str(dest)}


def export_jams(lab_root: Path, out_dir: Path, rows: list[dict] | None = None) -> dict:
    lab_root = Path(lab_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    holdout = ensure_holdout(lab_root, rows) if rows is not None else load_holdout(lab_root)

    written = 0
    skipped_val = 0
    for (album, track), boxes in sorted(keeper_boxes_by_song(lab_root).items()):
        if not boxes:
            continue
        if split_for(album, track, holdout) == "val":
            skipped_val += 1
            continue
        jam = build_jam(album, track, boxes)
        (out_dir / f"{_safe(album)}__{_safe(track)}.jams").write_text(
            json.dumps(jam, indent=2), encoding="utf-8"
        )
        written += 1
    return {"written": written, "skipped_val": skipped_val, "out": str(out_dir)}
