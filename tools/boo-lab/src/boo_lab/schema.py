"""Pin schema. Humans → sections.jsonl. Machines → drafts.jsonl."""
from __future__ import annotations

from typing import Any

ROLES = (
    "intro", "build", "riff", "hook", "breakdown",
    "solo", "chill", "pulse", "outro",
)
FIGURE_ROLES = frozenset({"riff", "hook", "solo", "pulse"})
FUNCTION_ROLES = frozenset({"intro", "build", "breakdown", "chill", "outro"})
SOURCES = frozenset({"human", "guess-accepted", "guess", "msa-draft", "songformer-draft"})
KEEPER_SOURCES = frozenset({"human", "guess-accepted"})

MSA_TO_LAB = {
    "intro": "intro", "start": "intro",
    "verse": "riff",
    "pre-chorus": "build", "prechorus": "build", "pre_chorus": "build",
    "chorus": "hook",
    "bridge": "chill",
    "inst": "solo", "instrumental": "solo", "solo": "solo",
    "outro": "outro", "end": "outro",
    "silence": "chill", "break": "breakdown", "breakdown": "breakdown",
}
_ALIASES = {
    "verse": "riff", "chorus": "hook", "interlude": "chill",
    "lead": "solo", "inst": "solo", "instrumental": "solo",
}


def canonical_role(role: str | None) -> str:
    text = (role or "").strip().lower()
    text = _ALIASES.get(text, text)
    return text if text in ROLES else "riff"


def layer_for(role: str) -> str:
    return "figure" if canonical_role(role) in FIGURE_ROLES else "function"


def msa_label_to_lab(label: str | None) -> str:
    text = (label or "").strip().lower()
    return MSA_TO_LAB.get(text, canonical_role(text))


def is_keeper(source: str | None) -> bool:
    return True if not source else source in KEEPER_SOURCES


def same_role_overlaps(boxes: list[dict[str, Any]]) -> list[tuple[int, int, str]]:
    hits: list[tuple[int, int, str]] = []
    for i, a in enumerate(boxes):
        ra = canonical_role(a.get("role"))
        sa, ea = float(a.get("start", 0)), float(a.get("end", 0))
        for j, b in enumerate(boxes):
            if j <= i:
                continue
            if canonical_role(b.get("role")) != ra:
                continue
            sb, eb = float(b.get("start", 0)), float(b.get("end", 0))
            if min(ea, eb) - max(sa, sb) > 0.05:
                hits.append((i, j, ra))
    return hits


def stamp_box(start: float, end: float, role: str | None, *, source: str = "human",
              figure_id: str | None = None, heard: bool = False,
              extra: dict[str, Any] | None = None) -> dict[str, Any]:
    role = canonical_role(role)
    rec: dict[str, Any] = {
        "start": float(start), "end": float(end), "role": role,
        "layer": layer_for(role),
        "figure_id": (figure_id or "").strip() or f"{role}-A",
        "source": source if source in SOURCES else "human",
        "heard": bool(heard),
    }
    if extra:
        for k, v in extra.items():
            rec.setdefault(k, v)
    return rec
