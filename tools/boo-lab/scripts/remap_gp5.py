"""Prefer extracted GP5 files over GP7 .gp in map.csv."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # god-tier-metal
MAP = ROOT / "tools" / "boo-lab" / "data" / "map.csv"
GP_ROOT = ROOT / "reference" / "gp-tabs"


def norm(s: str) -> str:
    s = s.lower().replace("∆", "a").replace("Δ", "a")
    s = re.sub(r"^\d+\s*[-_.]\s*", "", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def main() -> int:
    if not MAP.exists():
        print("missing", MAP)
        return 1
    gps = {}
    if GP_ROOT.exists():
        for p in GP_ROOT.rglob("*.gp5"):
            gps.setdefault(norm(p.stem), p)
    print("gp5 on disk:", len(gps))
    rows = list(csv.DictReader(MAP.open(encoding="utf-8", newline="")))
    fields = list(rows[0].keys()) if rows else ["album", "year", "track", "flac", "gp", "match", "notes"]
    hit = 0
    for r in rows:
        key = norm(r.get("track") or "")
        p = gps.get(key)
        if not p:
            continue
        r["gp"] = str(p).replace("\\", "/")
        flac = Path(r.get("flac") or "")
        r["match"] = "yes" if flac.exists() else "gp5"
        hit += 1
    with MAP.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print("mapped gp5 onto", hit, "rows")
    print("wrote", MAP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
