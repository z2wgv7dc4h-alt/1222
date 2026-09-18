"""Refresh only the numeric snapshot block in STATUS.md, from real files.

Counts come from disk, never from memory: keeper rows/tracks via
`schema.load_section_rows` (the one reader), drafts + sources, sync_ok/total,
and `map.csv` rows (reusing `data/corpus_health.json` when it is fresh rather
than walking `map.csv` again). The test-count line is deliberately left alone --
this command never runs pytest and never invents a number. Prose paragraphs in
STATUS.md stay; only the block between the status markers is rewritten.
"""
from __future__ import annotations

import json
from pathlib import Path

START = "<!-- status:counts:start -->"
END = "<!-- status:counts:end -->"


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


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _map_rows(lab_root: Path, health: dict | None) -> int:
    """Reuse `corpus_health.json`'s map total when it is at least as new as
    `map.csv`; otherwise count the CSV with the one loader."""
    map_path = lab_root / "data" / "map.csv"
    if health and map_path.exists():
        try:
            health_path = lab_root / "data" / "corpus_health.json"
            if health_path.stat().st_mtime >= map_path.stat().st_mtime:
                total = (health.get("files", {}).get("data/map.csv", {}).get("map") or {}).get("total")
                if total is not None:
                    return int(total)
        except (OSError, TypeError, ValueError):
            pass
    if not map_path.exists():
        return 0
    from .catalogue import load_map

    return len(load_map(map_path))


def collect_counts(lab_root) -> dict:
    from .schema import load_section_rows

    lab_root = Path(lab_root)
    health = _read_json(lab_root / "data" / "corpus_health.json")

    keepers = load_section_rows(lab_root / "data" / "sections.jsonl")
    drafts = _read_jsonl(lab_root / "data" / "drafts.jsonl")
    sync = _read_jsonl(lab_root / "data" / "sync.jsonl")
    return {
        "keeper_rows": len(keepers),
        "keeper_tracks": len({(r.get("album"), r.get("track")) for r in keepers}),
        "draft_rows": len(drafts),
        "draft_sources": sorted({r.get("source") for r in drafts if r.get("source")}),
        "sync_total": len(sync),
        "sync_ok": sum(1 for r in sync if r.get("sync_ok") is True),
        "map_rows": _map_rows(lab_root, health),
    }


def render_block(counts: dict) -> str:
    sources = ", ".join(counts["draft_sources"]) or "none"
    return "\n".join([
        START,
        "## Counts (from disk)",
        "",
        "- keepers: %d row(s) across %d track(s)" % (counts["keeper_rows"], counts["keeper_tracks"]),
        "- drafts: %d row(s); sources: %s" % (counts["draft_rows"], sources),
        "- sync: %d ok / %d row(s)" % (counts["sync_ok"], counts["sync_total"]),
        "- map.csv: %d row(s)" % counts["map_rows"],
        END,
    ])


def refresh_status(lab_root, status_path=None) -> dict:
    """Rewrite only the marker block. Returns `{updated, path, counts}`."""
    path = Path(status_path) if status_path else Path(lab_root) / "STATUS.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if START not in text or END not in text:
        return {"updated": False, "path": str(path), "reason": "status markers not found"}
    counts = collect_counts(lab_root)
    pre = text.split(START, 1)[0]
    post = text.split(END, 1)[1]
    path.write_text(pre + render_block(counts) + post, encoding="utf-8")
    return {"updated": True, "path": str(path), "counts": counts}


def run_status(lab_root) -> dict:
    return refresh_status(lab_root)
