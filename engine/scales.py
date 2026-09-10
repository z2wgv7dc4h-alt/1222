SCALES: dict[str, tuple[int, ...]] = {
    "chromatic": (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11),
    "melodic_minor": (0, 2, 3, 5, 7, 9, 11),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
    "whole_tone": (0, 2, 4, 6, 8, 10),
    "cluster": (0, 1, 3, 6, 7, 8, 11),
    "power": (0, 5, 7),
    # Major-family modes (added for modal interchange -- see
    # god-tier-metal-scope.md ## 2: "borrowing chords/notes from parallel
    # major/minor... a big part of what makes Born of Osiris sound
    # 'smarter' than straight minor-scale riffing." Confirmed as a real,
    # not just theoretical, gap: analyzing a real reference track
    # (engine/audio_vocab.py's estimate_key) came back A major, and no
    # preset/scale in this project could represent that until now.
    "major": (0, 2, 4, 5, 7, 9, 11),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "harmonic_major": (0, 2, 4, 5, 7, 8, 11),
    # A real, previously-flagged, never-fixed gap: theory.py's own module
    # docstring has documented since this project's earliest sessions
    # that the reference implementation's `phrygian_dominant` "has no
    # equivalent scale here and is intentionally not carried over as a
    # second table entry -- it would need to be added to scales.py
    # first." Ported directly from the reference's own real interval
    # tuple (`reference/ww-forge-prior-attempt/engine/theory.py`), not
    # derived -- the 5th mode of harmonic minor, the real "Spanish
    # Phrygian"/exotic scale genuinely common in this project's own
    # genre bar (djent/deathcore/metalcore), distinct from the plain
    # phrygian already in use by two shipped presets (major 3rd instead
    # of minor 3rd is the whole real character difference).
    "phrygian_dominant": (0, 1, 4, 5, 7, 8, 10),
}

# Aliases: same interval set as a canonical entry above, kept as a documented
# alternate name rather than a second scale definition (avoids two names for
# one interval set drifting apart over time).
ALIASES: dict[str, str] = {
    "aeolian": "minor",
    "ionian": "major",
}


def get_scale(name: str) -> tuple[int, ...]:
    canonical = ALIASES.get(name, name)
    if canonical not in SCALES:
        raise ValueError(f"unknown scale: {name}")
    return SCALES[canonical]
