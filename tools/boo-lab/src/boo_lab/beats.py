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

    from .device import torch_device

    device = torch_device()
    file2beats = File2Beats(device=device, float16=device == "cuda")
    beats, downbeats = file2beats(str(flac))
    return [float(x) for x in beats], [float(x) for x in downbeats], "beat_this"


def _allin1(
    flac: Path, cache_dir: Path | None = None
) -> tuple[list[float], list[float], str]:
    from .structure import run_allin1

    payload = run_allin1(flac, cache_dir=cache_dir)
    return (
        [float(x) for x in (payload.get("beats") or [])],
        [float(x) for x in (payload.get("downbeats") or [])],
        "allin1",
    )


def track_beats(
    flac: Path, cache_dir: Path | None = None
) -> tuple[list[float], list[float], str]:
    """beat_this if installed, else allin1; `("none", ...)` when neither."""
    try:
        return _beat_this(flac)
    except ImportError:
        pass
    try:
        return _allin1(flac, cache_dir=cache_dir)
    except ImportError:
        return [], [], "none"


def build_beats(lab_root: Path, rows: list[dict], album: str | None = None) -> dict:
    lab_root = Path(lab_root)
    out = lab_root / "data" / "beats.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    skipped = 0
    for r in rows:
        if album and (r.get("album") or "") != album:
            continue
        fp = r.get("flac_path") or r.get("flac")
        flac = Path(fp) if fp else None
        if not flac or not flac.exists():
            skipped += 1
            print("SKIP beats", r.get("track"), "no flac")
            continue
        beats, downbeats, source = track_beats(
            flac, cache_dir=lab_root / "work" / "allin1"
        )
        if source == "none":
            skipped += 1
            print("SKIP beats", r.get("track"), "no beat tracker installed")
            continue
        records.append({"album": r.get("album"), "track": r.get("track"),
                        "beats": beats, "downbeats": downbeats, "source": source})
        print("BEATS", r.get("track"), source, len(beats))
    # Non-destructive on a zero-row run: a `--album` that matches nothing, or
    # a batch where every track is skipped, must not blank a good
    # `data/beats.jsonl`. Write via a temp file and replace only on success.
    if records:
        tmp = out.with_name(out.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
        tmp.replace(out)
    else:
        print("beats: 0 rows written; leaving existing", out.name, "untouched")
    return {"written": len(records), "skipped": skipped, "out": str(out)}
