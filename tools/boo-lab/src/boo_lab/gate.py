from __future__ import annotations

import os
import re
from pathlib import Path

# A GP under this size is a fragment/stub, never a full-song tab to bank.
MIN_GP_BYTES = 10_000

# Non-bankable name markers (CATALOG's "skip *_solo*, tiny stubs, cover/bass-only
# tabs, Misha mixes when banking a song"). `\bcover\b` deliberately does NOT hit
# "Discovery" (no word boundary after "cover").
_SOLO_RE = re.compile(r"(^|[\s_-])solo\b")
_SWEEP_RE = re.compile(r"\bsweep\b")
_COVER_RE = re.compile(r"\bcover\b")
_LEAD_NUM = re.compile(r"^\s*\d{1,3}\s*[-._]?\s*")


def _title_after_number(s) -> str:
    """A filename/token's title with extension and leading track number gone,
    casefolded -- so `01 - Intro` is exactly `intro`, `The Origin` is not."""
    name = os.path.splitext(str(s or ""))[0]
    return _LEAD_NUM.sub("", name).strip().casefold()


def is_bankable_track(track_token, filename: str = "") -> bool:
    """False for a name that must not be banked as a song (Misha mix, *_solo*,
    sweep, cover, bass-only, or an `intro`-only stub). True otherwise. This is
    a name check only; size is `is_stub_gp`'s job. Nothing on disk is renamed."""
    low = ("%s %s" % (track_token or "", filename or "")).casefold()
    if "misha mansoor" in low or "demo mix" in low:
        return False
    if _SOLO_RE.search(low):        # "_solo" / " solo" / "-solo" / "outro solo"
        return False
    if _SWEEP_RE.search(low):
        return False
    if _COVER_RE.search(low):
        return False
    if "bass only" in low or "_bass" in low:
        return False
    for raw in (track_token, filename):
        if raw and _title_after_number(raw) == "intro":
            return False
    return True


def is_stub_gp(path, size_bytes: int | None = None) -> bool:
    """True when a GP file is not bankable: missing, under `MIN_GP_BYTES`, or a
    non-bankable name (`Devastate Solo.gp5`, a Misha mix, ...). A missing file
    is a stub, never assumed good."""
    p = Path(path)
    if not p.exists():
        return True
    if size_bytes is None:
        try:
            size_bytes = p.stat().st_size
        except OSError:
            return True
    if size_bytes < MIN_GP_BYTES:
        return True
    return not is_bankable_track(p.stem, p.name)


def lock_score(beat_times: list[float], note_times: list[float], window: float = 0.08) -> float:
    """Fraction of GP note onsets that fall near an audio beat or half-beat."""
    if not note_times or not beat_times:
        return 0.0
    grid = list(beat_times)
    if len(beat_times) >= 2:
        # also allow offbeats
        grid += [(a + b) / 2 for a, b in zip(beat_times, beat_times[1:])]
    hits = 0
    for t in note_times:
        if min(abs(t - g) for g in grid) <= window:
            hits += 1
    return hits / len(note_times)


def pass_gate(score: float, threshold: float = 0.55) -> bool:
    return score >= threshold


def write_report(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["track,score,pass"]
    for r in rows:
        lines.append(f"{r['track']},{r['score']:.3f},{r['ok']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
