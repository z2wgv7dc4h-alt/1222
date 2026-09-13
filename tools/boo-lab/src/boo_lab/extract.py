from __future__ import annotations

from pathlib import Path

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


def extract_riffs(gp_path: Path, source_song: str) -> list[dict]:
    """Group adjacent measures on the first guitar-like track into 2–4 bar riffs."""
    import guitarpro as gp

    song = gp.parse(str(gp_path))
    track = _rhythm_track(song)
    if track is None:
        return []
    measures = list(track.measures)
    chunks: list[dict] = []
    i = 0
    while i < len(measures):
        m0 = measures[i]
        marker = _marker_text(m0)
        role = infer_role(marker)
        width = 2
        while i + width < len(measures) and width < 4:
            nxt = measures[i + width]
            if _marker_text(nxt):
                break
            if _is_empty(nxt):
                break
            width += 1
        bars = measures[i : i + width]
        cells, deltas = _bars_to_cells(bars)
        if any(not c["is_rest"] for c in cells):
            chunks.append(
                {
                    "source_song": source_song,
                    "source_file": str(gp_path),
                    "track": track.name,
                    "measure_start": i,
                    "bars": width,
                    "role": role,
                    "raw_marker": marker,
                    "cell": cells,
                    "deltas": deltas,
                }
            )
        i += width
    return chunks


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


def _is_empty(measure) -> bool:
    for voice in measure.voices:
        for beat in voice.beats:
            if beat.notes:
                return False
    return True


def _bars_to_cells(measures) -> tuple[list[dict], list[int]]:
    cells: list[dict] = []
    pitches: list[int] = []
    for measure in measures:
        voice = measure.voices[0]
        for beat in voice.beats:
            dur = float(beat.duration.value) if beat.duration else 4.0
            # guitarpro duration.value is denominator (4=quarter). Convert to beats.
            beats = 4.0 / dur if dur else 1.0
            notes = [n for n in beat.notes if getattr(n, "type", None) and n.type.name != "rest"]
            if not notes:
                cells.append({"duration": beats, "is_rest": True})
                continue
            cells.append({"duration": beats, "is_rest": False})
            midi = getattr(notes[0], "realValue", None)
            if midi is None:
                midi = 40 + int(getattr(notes[0], "value", 0) or 0)
            pitches.append(int(midi))
    deltas = [0]
    for a, b in zip(pitches, pitches[1:]):
        deltas.append(int(b - a))
    if len(deltas) < sum(1 for c in cells if not c["is_rest"]):
        # keep lengths honest
        pass
    return cells, deltas


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
