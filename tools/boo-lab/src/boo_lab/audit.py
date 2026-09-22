"""Corpus hygiene. Does not invent pins."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .gate import is_stub_gp
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

_MATCH_YES = {"yes", "y", "1", "true"}
_LEGACY_GP_EXTS = (".gp3", ".gp4", ".gp5")


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


def _map_rows(lab_root: Path) -> list[dict]:
    """Raw `data/map.csv` rows (gitignored, may be absent -> [])."""
    path = lab_root / "data" / "map.csv"
    if not path.exists():
        return []
    try:
        from .catalogue import load_map

        return load_map(path)
    except Exception:
        return []


def _is_zip_gpif(path) -> bool:
    """Content sniff: the existing GPIF reader opens it (zip with
    `Content/score.gpif`). Reused -- never a second sniffer."""
    try:
        from .gpif import open_gp

        with open_gp(Path(path)):
            return True
    except Exception:
        return False


def _gp_readable(path) -> bool:
    """True when the real reader for this extension can open it: GPIF for
    `.gp`/`.gpx`, pyguitarpro for GP3/4/5. Never guesses."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return False
    if p.suffix.lower() in (".gp", ".gpx"):
        return _is_zip_gpif(p)
    try:
        import guitarpro

        guitarpro.parse(str(p))
        return True
    except Exception:
        return False


def _map_warnings(rows: list[dict]) -> dict:
    """Map-level quality gates: match=yes GP unopenable / stub, and a legacy
    GP extension whose content is actually zip/GPIF (mislabeled)."""
    unopenable: list[dict] = []
    stubs: list[dict] = []
    mislabeled: list[dict] = []
    for r in rows:
        gp = r.get("gp_path") or r.get("gp") or ""
        p = Path(gp) if gp else None
        if gp and p is not None and p.suffix.lower() in _LEGACY_GP_EXTS \
                and _is_zip_gpif(p):
            mislabeled.append({"album": r.get("album") or "", "track": r.get("track") or "",
                               "gp": gp})
        if (r.get("match") or "").lower() not in _MATCH_YES:
            continue
        if not gp or p is None or not p.exists():
            unopenable.append({"album": r.get("album") or "", "track": r.get("track") or "",
                               "gp": gp, "reason": "missing"})
        elif not _gp_readable(p):
            unopenable.append({"album": r.get("album") or "", "track": r.get("track") or "",
                               "gp": gp, "reason": "unreadable"})
        if p is not None and p.exists() and is_stub_gp(p):
            stubs.append({"album": r.get("album") or "", "track": r.get("track") or "", "gp": gp})
    return {"map_unopenable": unopenable, "stub_matches": stubs, "mislabeled_gps": mislabeled}


def _identity_gaps(secs: list[dict]) -> list[dict] | None:
    """Keeper `(album, track)` pairs with no `identity.csv` row. `None` (skip)
    when identity.py is unavailable."""
    try:
        from . import identity
    except Exception:
        return None
    gaps: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for rec in secs:
        key = (rec.get("album") or "", rec.get("track") or "")
        if not any(key) or key in seen:
            continue
        seen.add(key)
        if identity.album_id_for(key[0], key[1]) is None:
            gaps.append({"album": key[0], "track": key[1]})
    return gaps


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
        "identity_gaps": _identity_gaps(secs),
        **_map_warnings(_map_rows(lab_root)),
    }


def _print_list(label: str, items: list, fmt) -> None:
    """Print one warning list, capped at 12 rows + `… N more`."""
    print(f"  {label:<24} {len(items)}")
    for it in items[:12]:
        print("    " + fmt(it))
    if len(items) > 12:
        print(f"    … {len(items) - 12} more")


def _print_keys(label: str, items: list) -> None:
    for it in items[:12]:
        print(f"    {label} {it}")
    if len(items) > 12:
        print(f"    … {len(items) - 12} more {label.strip()}")


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

    _print_list("same-role overlaps:",
                report["same_role_overlaps"],
                lambda h: f"{h['album']} / {h['track']}  {h['role']}  boxes {h['i']}+{h['j']}")
    _print_list("schema gaps:", report.get("schema_gaps", []),
                lambda g: f"{g['album']} / {g['track']}  {g['role']}  {', '.join(g['reasons'])}")
    _print_list("swallow warnings:", report.get("swallow_warnings", []),
                lambda w: (f"{w['album']} / {w['track']}  {w['role']} covers "
                           f"{w['start']:.2f}-{w['end']:.2f}  swallows {', '.join(w['swallows'])}"))
    _print_list("map not openable:", report.get("map_unopenable", []),
                lambda m: f"{m['album']} / {m['track']}  [{m['reason']}]  {m['gp']}")
    _print_list("mislabeled GP ext:", report.get("mislabeled_gps", []),
                lambda m: f"{m['album']} / {m['track']}  {m['gp']}")
    _print_list("stub match=yes:", report.get("stub_matches", []),
                lambda m: f"{m['album']} / {m['track']}  {m['gp']}")

    ident = report.get("identity_gaps")
    if ident is None:
        print("  identity gaps:            (skipped: no identity.py)")
    else:
        _print_list("identity gaps:", ident, lambda g: f"{g['album']} / {g['track']}")

    drift = report.get("snapshot_drift", {})
    only_live = drift.get("only_live", [])
    only_snap = drift.get("only_snapshot", [])
    print(f"  snapshot drift:          {len(only_live) + len(only_snap)}"
          f"  ({drift.get('snapshot', '?')}{'' if drift.get('present') else ' missing'})")
    _print_keys("only live:    ", only_live)
    _print_keys("only snapshot:", only_snap)
