"""Named chord-quality vocabulary, wired into the real fretboard solver."""
from __future__ import annotations

from fretboard import Fretboard
from riff import voice_chord_section

__all__ = [
    "CHORD_QUALITIES",
    "get_chord_quality",
    "voice_named_chord",
    "DISSONANCE_ORDER",
    "quality_for_dissonance",
]

# Standard, well-known jazz-influenced extended-chord interval formulas
# (semitones from root) -- generic music-theory facts, not derived from any
# copyrighted composition. Matches the shape/convention of scales.py's
# SCALES dict.
CHORD_QUALITIES: dict[str, tuple[int, ...]] = {
    # Triad-plus-7th qualities.
    "maj7": (0, 4, 7, 11),   # major triad + major 7th
    "min7": (0, 3, 7, 10),   # minor triad + minor 7th
    "dom7": (0, 4, 7, 10),   # major triad + minor 7th (dominant)
    # Suspended triads (no 3rd -- open, ambiguous, ambient).
    "sus2": (0, 2, 7),       # root, major 2nd, 5th
    "sus4": (0, 5, 7),       # root, perfect 4th, 5th
    # Added/extended-tone qualities (9th = 14, an octave-up major 2nd).
    "add9": (0, 4, 7, 14),        # major triad + 9th, no 7th
    "maj9": (0, 4, 7, 11, 14),    # maj7 + 9th
    "min9": (0, 3, 7, 10, 14),    # min7 + 9th
    "six9": (0, 4, 7, 9, 14),     # major triad + 6th + 9th ("6/9")
}

# Ordered least-dissonant -> most-dissonant, used only by
# `quality_for_dissonance` below. Documented judgment call, not a music-
# theory law: suspended/added-9th qualities (no clashing 3rd-vs-7th
# tension) read as the most open/consonant for a clean ambient section;
# dominant/minor-7th/minor-9th qualities (containing a tritone or a minor
# 3rd against an extended tone) read as progressively more tense. See
# `quality_for_dissonance`'s docstring for how this feeds song.py.
DISSONANCE_ORDER: tuple[str, ...] = (
    "maj9", "add9", "sus2", "maj7", "six9", "sus4", "dom7", "min7", "min9",
)


def get_chord_quality(name: str) -> tuple[int, ...]:
    """Interval tuple for a named chord quality. Raises `ValueError` on an
    unknown name -- never returns a fabricated/default interval set, same
    contract as `scales.get_scale`."""
    if name not in CHORD_QUALITIES:
        raise ValueError(f"unknown chord quality: {name!r}")
    return CHORD_QUALITIES[name]


def voice_named_chord(
    root: int,
    quality: str,
    fretboard: Fretboard,
    max_span: int = 4,
) -> list[tuple[int, int]]:
    """Real fingering for a named chord quality at `root` on `fretboard`.

    Looks up `quality` via `get_chord_quality` (raises `ValueError` on an
    unknown name), then reuses `riff.voice_chord_section` -- NOT a
    reimplementation of fingering selection -- to pick the real, lowest-
    on-the-neck fingering `chords.solve_chord` finds. Propagates
    `voice_chord_section`'s own `ValueError` when the chord is unreachable
    on this fretboard/tuning (e.g. `max_span` too small, or a tone that
    doesn't exist on any string) -- never fabricates a partial or
    approximate shape either way.
    """
    intervals = get_chord_quality(quality)
    return voice_chord_section(root, intervals, fretboard, max_span=max_span)


def quality_for_dissonance(dissonance: float) -> str:
    """Map a section's dissonance value (0.0-1.0) onto a chord quality name
    from `DISSONANCE_ORDER`, for use on ambient/melodic (`chill`/
    `interlude`) sections in song.py.

    Documented mapping: `DISSONANCE_ORDER` is bucketed into
    `len(DISSONANCE_ORDER)` equal-width bins across [0, 1] -- low
    dissonance lands on the open/consonant end (`sus2`/`add9`/`maj9`/
    `maj7`), high dissonance lands on the darker end (`min7`/`min9`), per
    the task brief's own framing. Values outside [0, 1] are clamped rather
    than raising, since `theory.arc()`'s dissonance rows and
    `presets.Preset.dissonance` are both already validated to that range
    upstream -- this is a plain bucketing function, not a second validator.
    """
    d = max(0.0, min(1.0, float(dissonance)))
    n = len(DISSONANCE_ORDER)
    idx = min(n - 1, int(d * n))
    return DISSONANCE_ORDER[idx]
