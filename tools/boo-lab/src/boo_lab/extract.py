from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path


def _engine_riff_bank():
    """Real cross-package import of engine/riff_bank.py — same repo,
    sibling package (this file: tools/boo-lab/src/boo_lab/extract.py).
    CLAUDE.md: 'Do not invent a second parser if riff_bank.py already
    extracts.' — extract_riffs calls the real thing instead of keeping
    its own copy of cell/delta/track-selection logic."""
    engine_root = Path(__file__).resolve().parents[4] / "engine"
    if str(engine_root) not in sys.path:
        sys.path.insert(0, str(engine_root))
    import riff_bank

    return riff_bank


# Real, explicit translation from boo-lab's own role vocabulary (CURRENT.
# md's "## Roles": intro/build/riff/hook/breakdown/solo/chill/pulse/outro)
# to the engine's (riff_bank.py's _MARKER_ROLE_KEYWORDS: intro/verse/
# build/chorus/breakdown/interlude/solo/chill/outro) -- these are NOT the
# same vocabulary, they only happen to share 6 of 9 spellings. Found via
# a real corpus-health report showing "riff"/"hook"/"chill" at zero real
# entries: the override below was silently passing boo-lab's raw role
# string straight into RiffFragment.role, which the engine's own role-
# filtered lookups (_candidate_riff_runs, called with roles like "verse")
# would never match against an unmapped "riff"/"hook" string. Hadn't bit
# yet only because the one track with real human labels (Rebirth) has no
# matched GP file, so this path never ran against real data.
# "pulse" (a named synth/keyboard loop) has NO real engine equivalent --
# mapped to `None` deliberately, same "never guess a role" discipline
# riff_bank.py's own `_resolve_role` already uses for its own unmapped
# markers, rather than silently forcing it onto the nearest-sounding
# engine role.
_BOO_LAB_TO_ENGINE_ROLE: dict[str, str | None] = {
    "intro": "intro",
    "build": "build",
    "riff": "verse",
    "hook": "chorus",
    "breakdown": "breakdown",
    "solo": "solo",
    "chill": "chill",
    "pulse": None,
    "outro": "outro",
}


def load_human_sections(data_dir: Path) -> dict[tuple[str, str], list[tuple[float, float, str]]]:
    """Real human-verified `(start, end, role)` ranges per `(album,
    track)`, read from `data/sections.jsonl` — the studio UI's own real
    output, with boo-lab's own role vocabulary translated to the engine's
    (see `_BOO_LAB_TO_ENGINE_ROLE`). A real boo-lab role with no engine
    equivalent (currently only "pulse") is DROPPED here, not kept
    untranslated — the same honest "no fabricated role" contract
    `riff_bank._resolve_role` already holds for GP markers. Empty dict,
    not an error, when the file doesn't exist yet (no labeling done, or a
    fresh checkout)."""
    path = data_dir / "sections.jsonl"
    out: dict[tuple[str, str], list[tuple[float, float, str]]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Fail closed per line: a malformed JSON line, a missing/
            # unknown role, or a record missing start/end is skipped,
            # never allowed to abort the whole read.
            try:
                rec = json.loads(line)
                engine_role = _BOO_LAB_TO_ENGINE_ROLE.get(rec["role"])
                if engine_role is None:
                    continue
                start = float(rec["start"])
                end = float(rec["end"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            key = (rec.get("album"), rec.get("track"))
            out.setdefault(key, []).append((start, end, engine_role))
    return out


def _human_role_at(sections: list[tuple[float, float, str]], t: float) -> str | None:
    """Real role whose human-labeled range covers time `t`, else `None`
    (an honest gap — e.g. Rebirth's own intentionally-empty stretches
    between labeled ranges, per tools/boo-lab/CURRENT.md)."""
    for start, end, role in sections:
        if start <= t < end:
            return role
    return None


def _measure_start_times(track) -> list[float]:
    """Real per-measure elapsed-time walk (tempo-map driven), one entry
    per measure. Deliberately a SEPARATE real implementation from
    `estimate_from_gp`'s own tempo walk below, not a refactor of it —
    that function has no test coverage and is actively relied on by the
    Guess pipeline (see CURRENT.md's own fragility notes), so this stays
    duplicated on purpose until real tests exist to refactor safely
    against."""
    t = 0.0
    bpm = 120.0
    times: list[float] = []
    for measure in track.measures:
        header = getattr(measure, "header", None)
        if header is not None:
            tempo = getattr(header, "tempo", None)
            val = getattr(tempo, "value", None) if tempo is not None else None
            if val:
                bpm = float(val)
        times.append(t)
        ts = getattr(measure, "timeSignature", None) or getattr(header, "timeSignature", None)
        num = getattr(ts, "numerator", 4) if ts else 4
        den_obj = getattr(ts, "denominator", 4) if ts else 4
        den = getattr(den_obj, "value", den_obj) or 4
        beats = float(num) * 4.0 / float(den)
        t += beats * 60.0 / max(bpm, 1.0)
    return times


# Marker words copied from 1222 riff_bank intent — keep in sync later.
ROLE_WORDS = {
    "intro": "intro",
    "verse": "verse",
    "riff": "verse",
    "hook": "chorus",
    "chorus": "chorus",
    "break": "breakdown",
    "breakdown": "breakdown",
    "solo": "solo",
    "lead": "solo",
    "bridge": "chill",
    "outro": "outro",
    "build": "build",
    "pre": "build",
    "chill": "chill",
    "clean": "chill",
    "ambient": "chill",
    "interlude": "chill",
    "pulse": "pulse",
    "synth": "pulse",
    "techno": "pulse",
    "electronic": "pulse",
    "vibe": "pulse",
}


def gp_track_names(gp_path: Path) -> list[str]:
    try:
        import guitarpro as gp

        song = gp.parse(str(gp_path))
        return [t.name or f"track{i}" for i, t in enumerate(song.tracks)]
    except Exception:
        return []


def infer_role(marker: str | None) -> str | None:
    if not marker:
        return None
    t = marker.lower()
    for word, role in ROLE_WORDS.items():
        if word in t:
            return role
    return None


def extract_riffs(
    gp_path: Path,
    source_song: str,
    human_sections: list[tuple[float, float, str]] | None = None,
) -> list[dict]:
    """Real per-measure fragments from `gp_path`, via `engine/riff_bank.
    py`'s own already-proven extraction (cell/delta/track-selection) —
    not a second, independent parser.

    Each real fragment's `role` is OVERRIDDEN by a real, ear-verified
    `sections.jsonl` label (`human_sections`, from `load_human_sections`)
    when a label covers that measure's own real tempo-mapped start time —
    falling back to riff_bank's own GP-marker-based role where no human
    label exists yet for this track (an honest degrade: most BoO tabs
    carry no real markers at all, per tools/boo-lab/CURRENT.md).

    Returns real `dataclasses.asdict(RiffFragment)` dicts — same shape
    `riff_bank.save_riff_bank`/`load_riff_bank` round-trip, so this
    tool's own `riffs.jsonl` can be merged straight into the engine's
    real `engine/data/riff_bank.json` bank, not a separate schema that
    needs its own adapter.
    """
    riff_bank = _engine_riff_bank()
    fragments = riff_bank.extract_fragments_from_file(gp_path, song_title=source_song)
    if not fragments:
        return []

    if human_sections:
        import guitarpro as gp

        song = gp.parse(str(gp_path))
        track = _rhythm_track(song)
        times = _measure_start_times(track) if track is not None else []
        aligned = []
        for f in fragments:
            t = times[f.measure_index] if f.measure_index < len(times) else None
            human_role = _human_role_at(human_sections, t) if t is not None else None
            if human_role is not None:
                f = dataclasses.replace(f, role=human_role, raw_marker=f.raw_marker or "human:sections.jsonl")
            aligned.append(f)
        fragments = aligned

    return [dataclasses.asdict(f) for f in fragments]


def _rhythm_track(song):
    named = []
    for t in song.tracks:
        n = (t.name or "").lower()
        if t.isPercussionTrack:
            continue
        if "lead" in n or "solo" in n or "vocal" in n:
            continue
        if "bass" in n:
            continue
        named.append(t)
        if "rhythm" in n or "gtr" in n or "guitar" in n:
            return t
    return named[0] if named else None


def _marker_text(measure) -> str | None:
    marker = getattr(measure, "marker", None)
    if marker is None:
        return None
    title = getattr(marker, "title", None) or getattr(marker, "text", None)
    return str(title) if title else None




def estimate_from_gp(gp_path: Path) -> dict:
    """Turn GP measure markers + tempo map into second-based sections."""
    import guitarpro as gp

    song = gp.parse(str(gp_path))
    bpm = float(getattr(getattr(song, "tempo", None), "value", None) or getattr(song, "tempo", 120) or 120)
    track = _rhythm_track(song) or (song.tracks[0] if song.tracks else None)
    if track is None:
        return {"bpm": bpm, "sections": [], "reason": "no track"}
    t = 0.0
    cuts = []  # (time, role, raw)
    for measure in track.measures:
        header = getattr(measure, "header", None)
        if header is not None:
            tempo = getattr(header, "tempo", None)
            val = getattr(tempo, "value", None) if tempo is not None else None
            if val:
                bpm = float(val)
        marker = _marker_text(measure)
        role = infer_role(marker)
        if marker:
            cuts.append((t, role or "verse", marker))
        ts = getattr(measure, "timeSignature", None) or getattr(header, "timeSignature", None)
        num = getattr(ts, "numerator", 4) if ts else 4
        den_obj = getattr(ts, "denominator", 4) if ts else 4
        den = getattr(den_obj, "value", den_obj) or 4
        beats = float(num) * 4.0 / float(den)
        t += beats * 60.0 / max(bpm, 1.0)
    duration = t
    if not cuts:
        return {"bpm": bpm, "sections": [], "reason": "no markers in tab", "duration": duration}
    sections = []
    for i, (start, role, raw) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else duration
        if end <= start:
            end = start + 0.5
        sections.append({"role": role, "start": round(start, 3), "end": round(end, 3), "source": "gp-marker", "raw": raw})
    return {"bpm": bpm, "sections": sections, "duration": duration}
