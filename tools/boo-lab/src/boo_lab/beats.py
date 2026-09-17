"""Beat/downbeat grid export from optional research interns.

Prefers `beat_this` File2Beats; falls back to allin1 beats/downbeats. Writes
`data/beats.jsonl` -- never `sections.jsonl`. Both trackers are optional
extras (`pip install -e ".[intern]"`); the suite mocks them so no torch is
required.
"""
from __future__ import annotations

import json
from pathlib import Path


def _beat_this(flac: Path) -> tuple[list[float], list[float], str]:
    from beat_this.inference import File2Beats

    file2beats = File2Beats()
    beats, downbeats = file2beats(str(flac))
    return [float(x) for x in beats], [float(x) for x in downbeats], "beat_this"


def _allin1(flac: Path) -> tuple[list[float], list[float], str]:
    from .structure import run_allin1

    payload = run_allin1(flac)
    return (
        [float(x) for x in (payload.get("beats") or [])],
        [float(x) for x in (payload.get("downbeats") or [])],
        "allin1",
    )


def track_beats(flac: Path) -> tuple[list[float], list[float], str]:
    """beat_this if installed, else allin1; `("none", ...)` when neither."""
    try:
        return _beat_this(flac)
    except ImportError:
        pass
    try:
        return _allin1(flac)
    except ImportError:
        return [], [], "none"


def build_beats(lab_root: Path, rows: list[dict], album: str | None = None) -> dict:
    lab_root = Path(lab_root)
    out = lab_root / "data" / "beats.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            if album and (r.get("album") or "") != album:
                continue
            fp = r.get("flac_path") or r.get("flac")
            flac = Path(fp) if fp else None
            if not flac or not flac.exists():
                skipped += 1
                print("SKIP beats", r.get("track"), "no flac")
                continue
            beats, downbeats, source = track_beats(flac)
            if source == "none":
                skipped += 1
                print("SKIP beats", r.get("track"), "no beat tracker installed")
                continue
            rec = {"album": r.get("album"), "track": r.get("track"),
                   "beats": beats, "downbeats": downbeats, "source": source}
            f.write(json.dumps(rec) + "\n")
            written += 1
            print("BEATS", r.get("track"), source, len(beats))
    return {"written": written, "skipped": skipped, "out": str(out)}
