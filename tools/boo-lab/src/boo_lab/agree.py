"""Two-pass agreement snapshots for keeper pins -- research-grade QA.

Snapshots the SAVED keeper boxes for one song so a human can re-pin the
same song later and measure boundary/role/figure agreement between pass 1
and pass 2. NEVER writes `sections.jsonl`; snapshots live in
`data/agree.jsonl`. At most two passes per track.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .schema import canonical_role


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


def _agree_path(lab_root: Path) -> Path:
    return Path(lab_root) / "data" / "agree.jsonl"


def keeper_boxes(lab_root: Path, album: str, track: str) -> list[dict]:
    """Current saved keeper boxes for one song (read-only)."""
    path = Path(lab_root) / "data" / "sections.jsonl"
    return [
        rec for rec in _read_jsonl(path)
        if (rec.get("album") or "") == album and (rec.get("track") or "") == track
    ]


def load_passes(lab_root: Path, album: str, track: str) -> list[dict]:
    return [
        rec for rec in _read_jsonl(_agree_path(lab_root))
        if (rec.get("album") or "") == album and (rec.get("track") or "") == track
    ]


def snapshot(lab_root: Path, album: str, track: str, boxes: list[dict] | None = None) -> dict:
    """First snapshot -> pass 1; any later snapshot -> pass 2 (replacing an
    existing pass 2). Never invents a third pass. Returns the record."""
    if boxes is None:
        boxes = keeper_boxes(lab_root, album, track)
    existing = load_passes(lab_root, album, track)
    this_pass = 1 if not existing else 2

    rec = {"album": album, "track": track, "pass": this_pass,
           "ts": round(time.time(), 3), "boxes": boxes}

    path = _agree_path(lab_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = [
        r for r in _read_jsonl(path)
        if not ((r.get("album") or "") == album and (r.get("track") or "") == track
                and r.get("pass") == this_pass)
    ]
    from .schema import write_jsonl_atomic

    write_jsonl_atomic(path, kept + [rec])
    return rec


# --- diff -------------------------------------------------------------------


def _boundaries(boxes: list[dict]) -> list[float]:
    out: list[float] = []
    for b in boxes:
        out.append(float(b.get("start", 0.0)))
        out.append(float(b.get("end", 0.0)))
    return sorted(out)


def boundary_hit_rate(pass1: list[dict], pass2: list[dict], tol: float) -> float:
    """Role-agnostic fraction of pass-1 boundaries (start/end times) that
    have a pass-2 boundary within `tol` seconds."""
    a = _boundaries(pass1)
    b = _boundaries(pass2)
    if not a:
        return 0.0
    return sum(1 for x in a if any(abs(x - y) <= tol for y in b)) / len(a)


def _overlap(a: dict, b: dict) -> float:
    return max(0.0, min(float(a.get("end", 0)), float(b.get("end", 0)))
               - max(float(a.get("start", 0)), float(b.get("start", 0))))


def hit_pairs(pass1: list[dict], pass2: list[dict], min_frac: float = 0.5) -> list[tuple[int, int]]:
    """Deterministic greedy matching: a box pair is a hit when they overlap
    by at least `min_frac` of the shorter box. Highest overlap wins; each box
    is used once."""
    cand: list[tuple[float, int, int]] = []
    for i, a in enumerate(pass1):
        for j, b in enumerate(pass2):
            ov = _overlap(a, b)
            dur = min(float(a.get("end", 0)) - float(a.get("start", 0)),
                      float(b.get("end", 0)) - float(b.get("start", 0)))
            if dur > 0 and ov / dur >= min_frac:
                cand.append((ov, i, j))
    cand.sort(key=lambda t: (-t[0], t[1], t[2]))
    used1: set[int] = set()
    used2: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _ov, i, j in cand:
        if i in used1 or j in used2:
            continue
        used1.add(i)
        used2.add(j)
        pairs.append((i, j))
    return pairs


def diff_passes(pass1: list[dict], pass2: list[dict]) -> dict:
    pairs = hit_pairs(pass1, pass2)
    if pairs:
        role_ag = sum(1 for i, j in pairs
                      if canonical_role(pass1[i].get("role")) == canonical_role(pass2[j].get("role"))) / len(pairs)
        fig_ag = sum(1 for i, j in pairs
                     if (pass1[i].get("figure_id") or "") == (pass2[j].get("figure_id") or "")) / len(pairs)
    else:
        role_ag = fig_ag = 0.0
    return {
        "boxes_pass1": len(pass1),
        "boxes_pass2": len(pass2),
        "boundary_hit_0_5": round(boundary_hit_rate(pass1, pass2, 0.5), 3),
        "boundary_hit_3_0": round(boundary_hit_rate(pass1, pass2, 3.0), 3),
        "hit_pairs": len(pairs),
        "role_agreement": round(role_ag, 3),
        "figure_agreement": round(fig_ag, 3),
    }


def format_diff(album: str, track: str, pass1: list[dict], pass2: list[dict]) -> str:
    d = diff_passes(pass1, pass2)
    return "\n".join([
        "agree diff: %s / %s" % (album, track),
        "  boxes            pass1=%d  pass2=%d" % (d["boxes_pass1"], d["boxes_pass2"]),
        "  boundary hit @0.5s   %.3f" % d["boundary_hit_0_5"],
        "  boundary hit @3.0s   %.3f" % d["boundary_hit_3_0"],
        "  hit pairs            %d" % d["hit_pairs"],
        "  role agreement       %.3f" % d["role_agreement"],
        "  figure agreement     %.3f" % d["figure_agreement"],
    ])
