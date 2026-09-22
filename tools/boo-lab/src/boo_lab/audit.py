"""Corpus hygiene. Does not invent pins."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .schema import (
    FIGURE_ROLES,
    FUNCTION_ROLES,
    canonical_role,
    is_keeper,
    load_section_rows,
    same_role_overlaps,
)

# Read-only reference copy of the live Rebirth windows (never a writer path --
# see CURRENT.md). audit compares its windows to the live rows, nothing more.
_SNAPSHOT_NAME = "rebirth-sections.jsonl"


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _section_rows(lab_root: Path) -> list[dict]:
    return load_section_rows(lab_root / "data" / "sections.jsonl")


def _schema_gaps(secs: list[dict]) -> list[dict]:
    """Keepers whose pre-stamp rows predate the CURRENT box contract: no
    `layer`, or a figure-role keeper with an empty `figure_id`. Advisory only;
    the live grandfather rows are never rewritten."""
    gaps: list[dict] = []
    for rec in secs:
        reasons: list[str] = []
        if not rec.get("layer"):
            reasons.append("missing layer")
        role = canonical_role(rec.get("role"))
        if role in FIGURE_ROLES and not (rec.get("figure_id") or "").strip():
            reasons.append("figure-role empty figure_id")
        if reasons:
            gaps.append({
                "album": rec.get("album") or "",
                "track": rec.get("track") or "",
                "role": role,
                "reasons": reasons,
            })
    return gaps


def _swallow_warnings(secs: list[dict]) -> list[dict]:
    """Function boxes that cover >= 90% of their track's full span while
    another function role sits entirely inside them (e.g. an intro-sized
    box that swallows the outro). Advisory; never edits a box."""
    by_track: dict[tuple[str, str], list[dict]] = {}
    for rec in secs:
        by_track.setdefault((rec.get("album") or "", rec.get("track") or ""), []).append(rec)

    out: list[dict] = []
    for (album, track), rows in sorted(by_track.items()):
        starts = [float(r.get("start", 0.0)) for r in rows]
        ends = [float(r.get("end", 0.0)) for r in rows]
        span = max(ends) - min(starts)
        if span <= 0:
            continue
        funcs = [(canonical_role(r.get("role")), r) for r in rows
                 if canonical_role(r.get("role")) in FUNCTION_ROLES]
        for role, box in funcs:
            start = float(box.get("start", 0.0))
            end = float(box.get("end", 0.0))
            if end <= start or (end - start) / span < 0.9:
                continue
            inside = {other_role for other_role, other in funcs
                      if other_role != role
                      and float(other.get("start", 0.0)) >= start - 1e-9
                      and float(other.get("end", 0.0)) <= end + 1e-9}
            if inside:
                out.append({
                    "album": album, "track": track, "role": role,
                    "start": start, "end": end,
                    "swallows": sorted(inside),
                })
    return out


def _window_key(rec: dict) -> tuple:
    return (
        round(float(rec.get("start", 0.0)), 3),
        round(float(rec.get("end", 0.0)), 3),
        canonical_role(rec.get("role")),
    )


def _snapshot_drift(lab_root: Path, secs: list[dict]) -> dict:
    """Live Rebirth windows vs the `data/rebirth-sections.jsonl` reference
    copy, keyed by `(start, end, role)`. Advisory: the snapshot is never a
    writer path and the live rows are never rewritten to match it."""
    path = lab_root / "data" / _SNAPSHOT_NAME
    if not path.exists():
        return {"snapshot": _SNAPSHOT_NAME, "present": False,
                "only_live": [], "only_snapshot": []}
    snap = _jsonl(path)
    keys = {(r.get("album") or "", r.get("track") or "") for r in snap}
    live = [r for r in secs if (r.get("album") or "", r.get("track") or "") in keys]
    live_keys = [_window_key(r) for r in live]
    snap_keys = [_window_key(r) for r in snap]
    live_c, snap_c = Counter(live_keys), Counter(snap_keys)
    return {
        "snapshot": _SNAPSHOT_NAME, "present": True,
        "live_count": len(live_keys), "snapshot_count": len(snap_keys),
        "only_live": sorted((live_c - snap_c).elements()),
        "only_snapshot": sorted((snap_c - live_c).elements()),
    }


def audit_lab(lab_root: Path) -> dict:
    secs = _section_rows(lab_root)
    drafts = _jsonl(lab_root / "data" / "drafts.jsonl")
    by_track: dict[tuple[str, str], list[dict]] = {}
    sources = Counter()
    roles = Counter()
    heard_n = 0
    short = 0
    keepers = 0
    for rec in secs:
        sources[rec.get("source") or "(legacy)"] += 1
        roles[canonical_role(rec.get("role"))] += 1
        if rec.get("heard"):
            heard_n += 1
        if is_keeper(rec.get("source")):
            keepers += 1
        if float(rec.get("end", 0)) - float(rec.get("start", 0)) < 1.0:
            short += 1
        by_track.setdefault((rec.get("album") or "", rec.get("track") or ""), []).append(rec)

    overlaps = []
    for (album, track), boxes in sorted(by_track.items()):
        for i, j, role in same_role_overlaps(boxes):
            overlaps.append({"album": album, "track": track, "role": role, "i": i, "j": j})

    draft_tracks = {(d.get("album"), d.get("track")) for d in drafts}
    pinned = set(by_track)
    return {
        "section_rows": len(secs),
        "keeper_rows": keepers,
        "draft_rows": len(drafts),
        "tracks_pinned": len(pinned),
        "tracks_with_drafts": len(draft_tracks),
        "sources": dict(sources),
        "roles": dict(roles),
        "heard": heard_n,
        "boxes_under_1s": short,
        "same_role_overlaps": overlaps,
        "pinned_without_draft": sorted(
            f"{a} / {t}" for a, t in pinned - draft_tracks if a or t
        )[:20],
        # Advisory warnings only -- audit never rewrites a file or blocks Save.
        "schema_gaps": _schema_gaps(secs),
        "swallow_warnings": _swallow_warnings(secs),
        "snapshot_drift": _snapshot_drift(lab_root, secs),
    }


def print_audit(report: dict) -> None:
    print("boo-lab audit")
    print("=" * 60)
    print(f"  sections.jsonl rows:     {report['section_rows']}")
    print(f"  keepers (extractable):   {report['keeper_rows']}")
    print(f"  drafts.jsonl rows:       {report['draft_rows']}")
    print(f"  tracks pinned:           {report['tracks_pinned']}")
    print(f"  heard boxes:             {report['heard']}")
    print(f"  boxes < 1s:              {report['boxes_under_1s']}")
    print(f"  sources:                 {report['sources'] or '{}'}")
    print(f"  roles:                   {report['roles'] or '{}'}")
    ov = report["same_role_overlaps"]
    print(f"  same-role overlaps:      {len(ov)}")
    for hit in ov[:12]:
        print(f"    {hit['album']} / {hit['track']}  {hit['role']}  boxes {hit['i']}+{hit['j']}")
    if len(ov) > 12:
        print(f"    … {len(ov) - 12} more")

    gaps = report.get("schema_gaps", [])
    print(f"  schema gaps:             {len(gaps)}")
    for g in gaps[:12]:
        print(f"    {g['album']} / {g['track']}  {g['role']}  {', '.join(g['reasons'])}")
    if len(gaps) > 12:
        print(f"    … {len(gaps) - 12} more")

    swallows = report.get("swallow_warnings", [])
    print(f"  swallow warnings:        {len(swallows)}")
    for w in swallows[:12]:
        print(f"    {w['album']} / {w['track']}  {w['role']} covers {w['start']:.2f}-{w['end']:.2f}"
              f"  swallows {', '.join(w['swallows'])}")
    if len(swallows) > 12:
        print(f"    … {len(swallows) - 12} more")

    drift = report.get("snapshot_drift", {})
    only_live = drift.get("only_live", [])
    only_snap = drift.get("only_snapshot", [])
    print(f"  snapshot drift:          {len(only_live) + len(only_snap)}"
          f"  ({drift.get('snapshot', '?')}{'' if drift.get('present') else ' missing'})")
    for key in only_live[:12]:
        print(f"    only live:     {key}")
    for key in only_snap[:12]:
        print(f"    only snapshot: {key}")
