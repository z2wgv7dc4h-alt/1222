from __future__ import annotations

import sys
from pathlib import Path


def _engine_audio_vocab():
    """Real cross-package import of engine/audio_vocab.py — same repo,
    sibling package (this file: tools/boo-lab/src/boo_lab/drums_extract.py).
    CLAUDE.md: 'do not reimplement onset classification' — this calls the
    real, already-tested `classify_drum_onsets` instead of carrying a second
    copy of the band-energy heuristic. sys.path pattern copied verbatim from
    extract.py's own `_engine_riff_bank()`."""
    engine_root = Path(__file__).resolve().parents[4] / "engine"
    if str(engine_root) not in sys.path:
        sys.path.insert(0, str(engine_root))
    import audio_vocab

    return audio_vocab


# engine's own role vocabulary -> this output's documented lowercase set.
_ROLE_MAP = {
    "KICK": "kick",
    "SNARE": "snare",
    "HIHAT_OR_CYMBAL": "hihat",
}

# Real, measured low-confidence rule for the failure mode `audio_vocab.
# classify_drum_onsets` itself documents: on dense, cymbal-heavy mixes it
# undercounts snares and over-reads hihat/cymbal. A section with a real
# hihat onsets but no/near-zero snare is exactly that mode, so it must not
# be presented as ground truth.
_MIN_HIHAT_FOR_RATIO = 8
_HIHAT_SNARE_RATIO = 10.0


def _drum_confidence(onsets: list[dict]) -> dict:
    """Real, measured per-section confidence signal: the actual per-class
    onset counts and hihat:snare ratio, plus an honest `low_confidence`
    flag when the ratio is extreme (the known undercount-snare/over-read-
    cymbal failure mode). `hihat_snare_ratio` is `None` when it is
    undefined (no hihat, or no snare to divide by) -- the counts remain
    readable in that case."""
    counts = {"kick": 0, "snare": 0, "hihat": 0}
    for o in onsets:
        role = o.get("role")
        if role in counts:
            counts[role] += 1
    hihat, snare = counts["hihat"], counts["snare"]
    ratio = round(hihat / snare, 3) if (hihat and snare) else None

    low = False
    reason = None
    if hihat >= _MIN_HIHAT_FOR_RATIO and snare == 0:
        low = True
        reason = (
            f"{hihat} hihat/cymbal onsets but 0 snare -- classify_drum_onsets "
            "is documented to undercount snares and over-read cymbals on dense mixes"
        )
    elif hihat >= _MIN_HIHAT_FOR_RATIO and snare and (hihat / snare) >= _HIHAT_SNARE_RATIO:
        low = True
        reason = (
            f"hihat:snare {round(hihat / snare, 1)}:1 ({hihat} hihat vs {snare} snare) -- "
            "classify_drum_onsets is documented to undercount snares on dense cymbal mixes"
        )

    out = {
        "low_confidence": low,
        "drum_class_counts": counts,
        "hihat_snare_ratio": ratio,
    }
    if low:
        out["confidence_reason"] = reason
    return out


def classify_drums(drum_path: Path) -> list[dict]:
    """Real per-onset classification for a whole isolated drum stem, via
    `audio_vocab.classify_drum_onsets` — one decode and one onset pass per
    track, reused across every labeled section on that track."""
    audio_vocab = _engine_audio_vocab()
    y, sr = audio_vocab.load_audio(str(drum_path))
    raw = audio_vocab.classify_drum_onsets(y, sr)
    return [
        {"time": round(float(o["time"]), 3), "role": _ROLE_MAP.get(o["role"], o["role"].lower())}
        for o in raw
    ]


def build_drum_patterns(lab_root: Path, rows: list[dict], cache: Path) -> dict:
    """For every row in `data/sections.jsonl`, take that track's cached
    demucs drum stem (`stems.find_drums`), classify its real onsets once,
    then cut the onset list to each human-labeled `[start, end]` window.

    Writes one JSON line per section to `data/drum_patterns.jsonl`:
    `{"album","track","role","start","end","split","low_confidence",
    "drum_class_counts","hihat_snare_ratio","confidence_reason"?,
    "onsets":[{"time","role"}]}` where `role` is one of
    `kick`/`snare`/`hihat` (engine's own KICK/SNARE/HIHAT_OR_CYMBAL mapped
    down). `low_confidence` is a real, measured flag for the documented
    classify_drum_onsets failure mode (undercounted snares / over-read
    cymbals), with a short `confidence_reason` when set. A section whose
    track has no cached stem, or whose window contains no detected onset,
    is still written with an empty `onsets` list — an honest gap, not a
    dropped row.
    """
    from .holdout import ensure_holdout, split_for
    from .schema import load_section_rows
    from .stems import find_drums

    holdout = ensure_holdout(lab_root, rows)
    sec_path = lab_root / "data" / "sections.jsonl"
    sections = load_section_rows(sec_path)
    by_song: dict[tuple[str, str], list[dict]] = {}
    for s in sections:
        by_song.setdefault((s.get("album") or "", s.get("track") or ""), []).append(s)

    row_by = {(r.get("album") or "", r.get("track") or ""): r for r in rows}

    out_path = lab_root / "data" / "drum_patterns.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_sections = 0
    with_onsets = 0
    empty = 0
    no_stem = 0
    low_confidence = 0
    analyzed: dict[str, list[dict]] = {}
    out_rows: list[dict] = []

    for (album, track), segs in sorted(by_song.items()):
        r = row_by.get((album, track))
        if not r:
            hits = [row for (a, t), row in row_by.items() if t == track]
            r = hits[0] if len(hits) == 1 else None
        flac = None
        if r:
            fp = r.get("flac_path") or r.get("flac") or ""
            flac = Path(fp) if fp else None
        drums = find_drums(flac, cache) if flac else None
        if not drums:
            print("SKIP drums", track, "no cached drum stem")
        elif str(drums) not in analyzed:
            analyzed[str(drums)] = classify_drums(drums)

        all_onsets = analyzed.get(str(drums), []) if drums else []
        for seg in segs:
            start, end = float(seg["start"]), float(seg["end"])
            onsets = [o for o in all_onsets if start <= o["time"] < end]
            confidence = _drum_confidence(onsets)
            rec = {
                "album": album,
                "track": track,
                "role": seg.get("role"),
                "start": start,
                "end": end,
                "split": split_for(album, track, holdout),
                **confidence,
                "onsets": onsets,
            }
            out_rows.append(rec)
            n_sections += 1
            if not drums:
                no_stem += 1
                empty += 1
            elif onsets:
                with_onsets += 1
            else:
                empty += 1
            if confidence["low_confidence"]:
                low_confidence += 1
            print(
                "DRUMS", track, seg.get("role"), len(onsets),
                "LOW-CONF" if confidence["low_confidence"] else "",
            )

    from .schema import write_jsonl_atomic

    write_jsonl_atomic(out_path, out_rows)
    return {
        "sections": n_sections,
        "with_onsets": with_onsets,
        "empty": empty,
        "no_stem": no_stem,
        "low_confidence": low_confidence,
        "out": str(out_path),
    }
