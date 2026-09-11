from __future__ import annotations

from pathlib import Path


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
