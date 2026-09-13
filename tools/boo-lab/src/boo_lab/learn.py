"""Learn section roles from your corrections.

Not a song writer. After ~20–40 human sections, a small classifier on
cheap audio features can relabel allin1 chunks. It will not invent riffs.

Telling songs apart = nearest-neighbour on whole-track features
(BPM, energy curve) against your catalogue — retrieval, not generation.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import json


def load_human_sections(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("source") == "human":
            out.append(rec)
    return out


def role_prior(sections: list[dict]) -> dict[str, float]:
    c = Counter(s.get("role") for s in sections if s.get("role"))
    n = sum(c.values()) or 1
    return {k: v / n for k, v in c.items()}


def record(lab_root: Path, album: str, track: str, sections: list[dict]) -> None:
    path = lab_root / "data" / "learn-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"album": album, "track": track, "n": len(sections)}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def note(lab_root: Path) -> str:
    secs = load_human_sections(lab_root / "data" / "sections.jsonl")
    return "labelled %s boxes" % len(secs)


def enough_to_train(sections: list[dict], min_per_role: int = 4) -> bool:
    c = Counter(s.get("role") for s in sections)
    useful = [k for k, v in c.items() if v >= min_per_role]
    return len(useful) >= 3
