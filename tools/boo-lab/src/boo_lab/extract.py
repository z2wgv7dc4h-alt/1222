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
                from .schema import is_keeper

                if not is_keeper(rec.get("source")):
                    continue
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


def bars_for_times(gp_path: Path, start: float, end: float) -> tuple[int | None, int | None]:
    """Real 1-based GP measure numbers covering `[start, end]` seconds, via
    the same tempo-map walk as `_measure_start_times`. Returns
    `(None, None)` whenever the tab cannot be opened or has no measures --
    never invents a bar from seconds, and never raises (Save must not be
    blocked by a GP error)."""
    try:
        import guitarpro

        start = float(start)
        end = float(end)
    except Exception:
        return None, None
    try:
        song = guitarpro.parse(str(gp_path))
    except Exception:
        return None, None
    track = _rhythm_track(song) or (song.tracks[0] if song.tracks else None)
    if track is None:
        return None, None
    times = _measure_start_times(track)
    if not times:
        return None, None

    def _bar_at(t: float) -> int:
        idx = 0
        for i, ts in enumerate(times):
            if ts <= t + 1e-9:
                idx = i
            else:
                break
        return idx + 1

    n = len(times)
    return min(max(_bar_at(start), 1), n), min(max(_bar_at(end), 1), n)


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




def _playback_duration(track, song_bpm: float) -> float:
    """Real tab LENGTH in seconds with repeats expanded (`sync._playback_order`),
    applying each measure's own tempo/time-signature. The once-through sum a
    naive walk produces is short for any tab with repeat signs, which made the
    last marker section (and Guess's coverage) stop early."""
    from .sync import _playback_order

    t = 0.0
    bpm = float(song_bpm or 120.0)
    for idx in _playback_order(track.measures):
        measure = track.measures[idx]
        header = getattr(measure, "header", None)
        tempo = getattr(header, "tempo", None)
        val = getattr(tempo, "value", None) if tempo is not None else None
        if val:
            bpm = float(val)
        ts = getattr(measure, "timeSignature", None) or getattr(header, "timeSignature", None)
        num = getattr(ts, "numerator", 4) if ts else 4
        den_obj = getattr(ts, "denominator", 4) if ts else 4
        den = getattr(den_obj, "value", den_obj) or 4
        t += (float(num) * 4.0 / float(den)) * 60.0 / max(bpm, 1.0)
    return t


def _section_letter(marker_text: str) -> tuple[str | None, str | None]:
    """Structural-letter token for a marker: `'A (0:00)' → ('A','A')`,
    `'C1 - Solo' → ('C','C1')`; `(None, None)` for a semantic marker like
    `'Pre-Chorus'` (that carries a role, not a section letter). Lets Guess
    carry the tab's own section identity so repeat letters are visible."""
    import re

    head = re.split(r"\s*[-(]", (marker_text or "").strip(), maxsplit=1)[0].strip()
    m = re.fullmatch(r"([A-Z])([0-9]*)", head)
    if not m:
        return None, None
    return m.group(1), head


def estimate_from_gp(gp_path: Path) -> dict:
    """Turn GP measure markers + tempo map into second-based sections.

    Walks the tab in **playback order** (repeats expanded via
    `sync._playback_order`), so a repeated section appears at each play; and
    carries the marker's own section identity (`form` = the letter, `figure_id`
    = `role-token`, `unique` when the token occurs once). A repeated letter is
    therefore the *same returning section*, not a fresh riff."""
    import guitarpro as gp

    from .sync import _playback_order

    song = gp.parse(str(gp_path))
    bpm = float(getattr(getattr(song, "tempo", None), "value", None) or getattr(song, "tempo", 120) or 120)
    song_bpm = bpm
    track = _rhythm_track(song) or (song.tracks[0] if song.tracks else None)
    if track is None:
        return {"bpm": bpm, "sections": [], "reason": "no track"}
    t = 0.0
    bpm = song_bpm
    cuts = []  # (start, role, raw, form, token)
    for idx in _playback_order(track.measures):
        measure = track.measures[idx]
        header = getattr(measure, "header", None)
        tempo = getattr(header, "tempo", None)
        val = getattr(tempo, "value", None) if tempo is not None else None
        if val:
            bpm = float(val)
        marker = _marker_text(measure)
        if marker:
            role = infer_role(marker) or "riff"
            form, token = _section_letter(marker)
            cuts.append((round(t, 3), role, marker, form, token))
        ts = getattr(measure, "timeSignature", None) or getattr(header, "timeSignature", None)
        num = getattr(ts, "numerator", 4) if ts else 4
        den_obj = getattr(ts, "denominator", 4) if ts else 4
        den = getattr(den_obj, "value", den_obj) or 4
        t += (float(num) * 4.0 / float(den)) * 60.0 / max(bpm, 1.0)
    # Repeat-aware length (same walk), so the last section reaches the tab end.
    duration = _playback_duration(track, song_bpm)
    if not cuts:
        return {"bpm": bpm, "sections": [], "reason": "no markers in tab", "duration": duration}

    from collections import Counter

    token_counts = Counter(c[4] for c in cuts if c[4])
    sections = []
    for i, (start, role, raw, form, token) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else duration
        if end <= start:
            end = start + 0.5
        sections.append({
            "role": role,
            "start": start,
            "end": round(end, 3),
            "source": "gp-marker",
            "raw": raw,
            "form": form or "A",
            "figure_id": "%s-%s" % (role, token or "A"),
            "unique": bool(token) and token_counts[token] == 1,
        })
    return {"bpm": bpm, "sections": sections, "duration": duration}


def estimate_from_gpif(gp_path: Path) -> dict:
    """GP7/GP6 twin of `estimate_from_gp` for a parsed GPIF score.

    Walks the masterbars in **playback order** (`gpif.playback_bar_order`,
    repeats expanded), turning each masterbar section into a second-based
    section on the same tempo clock `gpif.duration_sec` uses. Returns the
    identical dict shape (`role/start/end/source=gp-marker/raw/form/
    figure_id/unique` + `bpm` + `duration`), so Guess can pick the reader on
    suffix alone. Malformed/non-GPIF input raises, same as `estimate_from_gp`
    fails closed."""
    from . import gpif

    score = gpif.load_score(gp_path)
    song_bpm = float(score.tempo or 120.0)
    bpm = song_bpm
    duration = gpif.duration_sec(score)
    t = 0.0
    cuts = []  # (start, role, raw, form, token)
    for idx in gpif.playback_bar_order(score):
        mb = score.masterbars[idx]
        if mb.tempo:
            bpm = float(mb.tempo)
        if (mb.section or "").strip():
            marker = mb.section.strip()
            role = infer_role(marker) or "riff"
            form, token = _section_letter(marker)
            cuts.append((round(t, 3), role, marker, form, token))
        t += (mb.time_n * 4.0 / mb.time_d) * 60.0 / max(bpm, 1.0)
    if not cuts:
        return {"bpm": bpm, "sections": [], "reason": "no markers in tab", "duration": duration}

    from collections import Counter

    token_counts = Counter(c[4] for c in cuts if c[4])
    sections = []
    for i, (start, role, raw, form, token) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else duration
        if end <= start:
            end = start + 0.5
        sections.append({
            "role": role,
            "start": start,
            "end": round(end, 3),
            "source": "gp-marker",
            "raw": raw,
            "form": form or "A",
            "figure_id": "%s-%s" % (role, token or "A"),
            "unique": bool(token) and token_counts[token] == 1,
        })
    return {"bpm": bpm, "sections": sections, "duration": duration}
