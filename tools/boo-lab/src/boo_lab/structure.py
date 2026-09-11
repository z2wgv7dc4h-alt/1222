from __future__ import annotations

import json
from pathlib import Path


POP_ROLES = {
    "intro",
    "verse",
    "pre-chorus",
    "chorus",
    "bridge",
    "inst",
    "instrumental",
    "outro",
    "silence",
}


def relabel_breakdown(seg: dict) -> dict:
    """Placeholder: caller may attach stem stats later.

    If the analyze JSON already has half_time or kick_lock flags, promote to breakdown.
    """
    out = dict(seg)
    label = (out.get("label") or "").lower()
    if out.get("half_time") or out.get("kick_lock"):
        out["role"] = "breakdown"
        return out
    if label in {"chorus", "verse"} and out.get("energy") == "low":
        out["role"] = "chill"
        return out
    role_map = {
        "intro": "intro",
        "verse": "verse",
        "pre-chorus": "build",
        "chorus": "chorus",
        "bridge": "interlude",
        "inst": "solo",
        "instrumental": "solo",
        "outro": "outro",
        "silence": "chill",
    }
    out["role"] = role_map.get(label, label or "verse")
    return out


def load_allin1_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def segments_from_allin1(result: dict) -> list[dict]:
    raw = result.get("segments") or result.get("paths") or []
    segs = []
    for s in raw:
        if isinstance(s, dict):
            segs.append(
                {
                    "start": float(s.get("start", s.get("begin", 0))),
                    "end": float(s.get("end", 0)),
                    "label": s.get("label") or s.get("function") or "",
                }
            )
    return [relabel_breakdown(s) for s in segs]


def run_allin1(flac: Path) -> dict:
    import allin1  # optional extra

    result = allin1.analyze(str(flac))
    if hasattr(result, "__dict__"):
        payload = {
            "bpm": getattr(result, "bpm", None),
            "beats": list(getattr(result, "beats", []) or []),
            "downbeats": list(getattr(result, "downbeats", []) or []),
            "segments": [
                {
                    "start": getattr(s, "start", 0),
                    "end": getattr(s, "end", 0),
                    "label": getattr(s, "label", ""),
                }
                if not isinstance(s, dict)
                else s
                for s in (getattr(result, "segments", None) or [])
            ],
        }
        return payload
    if isinstance(result, dict):
        return result
    return {"raw": str(result)}
