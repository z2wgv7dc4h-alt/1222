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
}

# Aliases: same interval set as a canonical entry above, kept as a documented
# alternate name rather than a second scale definition (avoids two names for
# one interval set drifting apart over time).
ALIASES: dict[str, str] = {
    "aeolian": "minor",
}


def get_scale(name: str) -> tuple[int, ...]:
    canonical = ALIASES.get(name, name)
    if canonical not in SCALES:
        raise ValueError(f"unknown scale: {name}")
    return SCALES[canonical]
