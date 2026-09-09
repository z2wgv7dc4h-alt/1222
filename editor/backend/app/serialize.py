"""JSON-safe summaries of real engine data for the editor frontend.

The engine's own `song.compose_song`/`presets.load_all_presets` return
Python objects (Motif, Fretboard, Preset dataclasses) that aren't directly
JSON-serializable, and the timeline UI only needs a small, real subset of
each section's data (role, length, effective tempo, a few real quality
stats) -- never the full per-cell rhythm/pitch data. These functions
extract exactly that subset, reading only fields that genuinely exist on
the real `song`/`preset` objects, never fabricating a UI-convenience field
the engine doesn't actually produce.
"""
from __future__ import annotations


def summarize_preset(preset_id: str, preset) -> dict:
    """Real, JSON-safe metadata for one preset -- every field read
    directly off the real `presets.Preset` dataclass, nothing invented."""
    return {
        "id": preset_id,
        "description": preset.description,
        "tuning_key": preset.tuning_key,
        "scale": preset.scale,
        "bpm": preset.bpm,
        "bars": preset.bars,
        "feel": preset.feel,
        "kick": preset.kick,
        "group": preset.group,
        "pedal": preset.pedal,
        "dissonance": preset.dissonance,
        "octave_stab": preset.octave_stab,
    }


def _section_hit_stats(section: dict) -> dict:
    """Real per-section hit/articulation stats, computed the same way
    `song.judge`/this session's own diagnostic scripts already read them
    off a real section's `guitar_take_a`/`kick` cells -- not a new metric."""
    guitar = section["guitar_take_a"]
    kick = section["kick"]
    hits = [c for c in guitar if not c["is_rest"]]
    muted = sum(1 for c in hits if c.get("velocity", 100) < 110)
    kick_hits = sum(1 for c in kick if not c["is_rest"])
    return {
        "guitar_hits": len(hits),
        "muted_hits": muted,
        "open_hits": len(hits) - muted,
        "kick_hits": kick_hits,
    }


def summarize_section(section: dict, bpm: float, bars: int) -> dict:
    """Real, JSON-safe summary of one composed section -- role, real
    length/tempo, real hit stats, and the real optional per-role fields
    (chord_progression for verse/chorus, lead_mode) when present."""
    return {
        "role": section["role"],
        "bars": bars,
        "bpm": bpm,
        "lead_mode": section["lead_mode"],
        "lead_note_count": len(section["lead"]),
        "chord_progression": section.get("chord_progression"),
        "chord_quality": section.get("chord_quality"),
        **_section_hit_stats(section),
    }


def summarize_song(song: dict, preset) -> dict:
    """Real, JSON-safe summary of a full `compose_song` result: one entry
    per real section (in the real generated order) plus the song-level
    real `judge` result. `preset.bars` is the real per-section bar count
    (every section is `preset.bars` bars of 4/4, per song.py's own law)."""
    sections = [
        summarize_section(section, bpm, preset.bars)
        for section, bpm in zip(song["sections"], song["tempo_map"])
    ]
    return {
        "preset_id": song["preset_id"],
        "sequence": song["sequence"],
        "sections": sections,
        "judge": song["judge"],
    }
