"""Pin schema. Humans → sections.jsonl. Machines → drafts.jsonl."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

ROLES = (
    "intro", "build", "riff", "hook", "breakdown",
    "solo", "chill", "pulse", "outro",
)
FIGURE_ROLES = frozenset({"riff", "hook", "solo", "pulse"})
FUNCTION_ROLES = frozenset({"intro", "build", "breakdown", "chill", "outro"})
SOURCES = frozenset({"human", "guess-accepted", "guess", "msa-draft", "songformer-draft"})
KEEPER_SOURCES = frozenset({"human", "guess-accepted"})

# Real instrument vocabulary for a box. Empty string is allowed (unknown/mixed).
INSTRUMENTS = ("", "rhythm", "lead", "bass", "drums", "synth", "vocal", "mix")

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


def canonical_role(role: str | None) -> str | None:
    """This project's canonical role, or `None` when the input maps to none.

    Never fabricates a role: an unknown/empty/None role returns `None`
    (mirroring `engine/riff_bank._resolve_role` and `extract.py`'s deliberate
    dropping of `pulse`). Callers must handle `None` honestly -- a box with no
    resolvable role is rejected at Save, not stamped as a riff."""
    text = (role or "").strip().lower()
    text = _ALIASES.get(text, text)
    return text if text in ROLES else None


def layer_for(role: str | None) -> str:
    return "figure" if canonical_role(role) in FIGURE_ROLES else "function"


def msa_label_to_lab(label: str | None) -> str | None:
    text = (label or "").strip().lower()
    return MSA_TO_LAB.get(text, canonical_role(text))


def is_keeper(source: str | None) -> bool:
    """Fail closed: only an explicit keeper source counts. Missing/empty/None
    is NOT a keeper (it is an unstamped or malformed row)."""
    return source in KEEPER_SOURCES


def load_section_rows(path: str | Path, *, keepers_only: bool = True) -> list[dict]:
    """The ONE reader for `data/sections.jsonl`.

    `keepers_only` (default) keeps only real labeled rows -- the full keeper
    law: a truthy `role`, `is_keeper(source)`, AND `heard is True`. Malformed
    lines are skipped. Every consumer that reads labeled boxes
    (pack/drums/vocal/holdout) goes through this, so the "source == human"
    precedence bug cannot reappear in a copy."""
    path = Path(path)
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        if keepers_only:
            if not (rec.get("role") and is_keeper(rec.get("source"))
                    and rec.get("heard") is True):
                continue
        out.append(rec)
    return out


def write_jsonl_atomic(
    path: str | Path, rows: list[dict], *, ensure_ascii: bool = True
) -> None:
    """Atomically replace `path` with `rows` (one JSON object per line): a temp
    file in the same directory, flush + fsync, then `os.replace` (atomic on
    Windows and POSIX). A crash, full disk, or power loss mid-write leaves the
    original file intact. The one writer for the human/derived JSONL stores."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for rec in rows:
                f.write(json.dumps(rec, ensure_ascii=ensure_ascii) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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


def _bars(value: Any) -> int | None:
    """1-based GP measure, or None. Never guesses a bar from seconds."""
    if value is None or value == "":
        return None
    try:
        bar = int(value)
    except (TypeError, ValueError):
        return None
    return bar if bar > 0 else None


def stamp_box(start: float, end: float, role: str | None, *, source: str = "human",
              figure_id: str | None = None, heard: bool = False,
              form: str | None = None, unique: bool = False,
              instrument: str | None = None,
              start_bar: Any = None, end_bar: Any = None,
              extra: dict[str, Any] | None = None) -> dict[str, Any]:
    canon = canonical_role(role)
    if canon is None:
        raise ValueError(
            f"unknown role {role!r}; expected one of {sorted(ROLES)}"
        )
    if source not in SOURCES:
        raise ValueError(
            f"unknown source {source!r}; expected one of {sorted(SOURCES)}"
        )
    role = canon
    inst = (instrument or "").strip().lower()
    rec: dict[str, Any] = {
        "start": float(start), "end": float(end), "role": role,
        "layer": layer_for(role),
        "form": (form or "A").strip().upper() or "A",
        "figure_id": (figure_id or "").strip() or f"{role}-A",
        "unique": bool(unique),
        "instrument": inst if inst in INSTRUMENTS else "",
        "start_bar": _bars(start_bar),
        "end_bar": _bars(end_bar),
        "source": source,
        "heard": bool(heard),
    }
    if extra:
        for k, v in extra.items():
            rec.setdefault(k, v)
    return rec
