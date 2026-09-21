"""Beat/downbeat grid export from optional research interns.

Prefers `beat_this` File2Beats; falls back to allin1 beats/downbeats. Writes
`data/beats.jsonl` -- never `sections.jsonl`. Both trackers are optional
extras (`pip install -e ".[intern]"`); the suite mocks them so no torch is
required.

`build_beats` MERGES by album+track into existing `beats.jsonl` (never wipe-
replaces a batch over the whole corpus). Per-track `beat_this` results are
also cached under `work/beats/` so a wiped or partial jsonl does not mean
re-inference.
"""
from __future__ import annotations

import json
from pathlib import Path


def _beats_cache_path(lab_root: Path, flac: Path) -> Path:
    key = "%s_%s" % (flac.stem, flac.stat().st_size)
    return Path(lab_root) / "work" / "beats" / (key + ".json")


def _load_beats_cache(lab_root: Path, flac: Path) -> tuple[list[float], list[float], str] | None:
    path = _beats_cache_path(lab_root, flac)
    if not path.is_file():
        return None
    try:
        if path.stat().st_mtime < flac.stat().st_mtime:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        beats = [float(x) for x in (payload.get("beats") or [])]
        downbeats = [float(x) for x in (payload.get("downbeats") or [])]
        source = str(payload.get("source") or "cache")
        if not beats:
            return None
        return beats, downbeats, source + "+cache"
    except Exception:
        return None


def _save_beats_cache(lab_root: Path, flac: Path, beats, downbeats, source: str) -> None:
    try:
        path = _beats_cache_path(lab_root, flac)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "beats": beats, "downbeats": downbeats, "source": source,
            "flac": str(flac),
        }), encoding="utf-8")
    except Exception:
        pass


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
    flac: Path, cache_dir: Path | None = None, *, lab_root: Path | None = None
) -> tuple[list[float], list[float], str]:
    """beat_this if installed, else allin1; `("none", ...)` when neither.

    When `lab_root` is set, reuse `work/beats/<stem>_<size>.json` before GPU.
    """
    if lab_root is not None:
        hit = _load_beats_cache(lab_root, flac)
        if hit is not None:
            return hit
    try:
        beats, downbeats, source = _beat_this(flac)
        if lab_root is not None:
            _save_beats_cache(lab_root, flac, beats, downbeats, source)
        return beats, downbeats, source
    except ImportError:
        pass
    try:
        beats, downbeats, source = _allin1(flac, cache_dir=cache_dir)
        if lab_root is not None and beats:
            _save_beats_cache(lab_root, flac, beats, downbeats, source)
        return beats, downbeats, source
    except ImportError:
        return [], [], "none"


def build_beats(lab_root: Path, rows: list[dict], album: str | None = None) -> dict:
    lab_root = Path(lab_root)
    out = lab_root / "data" / "beats.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    skipped = 0
    cached = 0
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
            flac, cache_dir=lab_root / "work" / "allin1", lab_root=lab_root
        )
        if source == "none":
            skipped += 1
            print("SKIP beats", r.get("track"), "no beat tracker installed")
            continue
        if source.endswith("+cache"):
            cached += 1
            print("CACHE beats", r.get("track"), source, len(beats))
        else:
            print("BEATS", r.get("track"), source, len(beats))
        records.append({"album": r.get("album"), "track": r.get("track"),
                        "beats": beats, "downbeats": downbeats,
                        "source": source.replace("+cache", "")})
    # Merge by album+track — never wipe other albums with the current batch.
    if records:
        existing: list[dict] = []
        if out.exists():
            for line in out.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    existing.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        by_key = {
            ((e.get("album") or ""), (e.get("track") or "")): e for e in existing
        }
        for rec in records:
            by_key[((rec.get("album") or ""), (rec.get("track") or ""))] = rec
        merged = list(by_key.values())
        tmp = out.with_name(out.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for rec in merged:
                f.write(json.dumps(rec) + "\n")
        tmp.replace(out)
        print("beats: wrote %d new/updated (%d from disk cache), %d total"
              % (len(records), cached, len(merged)))
    else:
        print("beats: 0 rows written; leaving existing", out.name, "untouched")
    return {"written": len(records), "skipped": skipped, "cached": cached,
            "out": str(out)}
