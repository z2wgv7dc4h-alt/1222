"""Corpus hygiene. Does not invent pins."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .schema import canonical_role, is_keeper, load_section_rows, same_role_overlaps


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
