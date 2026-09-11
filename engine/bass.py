"""Phase 5 ("Bass")."""
from __future__ import annotations

from fretboard import Fretboard

_VALID_BASS_STRING_COUNTS = (4, 5)


def derive_bass_tuning(guitar_open: list[int], strings: int = 4) -> list[int]:
    """Derive a bass tuning (open MIDI notes, low string to high string)
    from a guitar tuning's open notes, per the convention documented at the
    top of this module.

    `guitar_open` is the guitar's open-string MIDI notes (any order --
    `min()` is used, so this does not depend on the caller's string
    ordering convention). Raises ValueError on a bad `strings` count or an
    empty guitar tuning, rather than silently defaulting.
    """
    if strings not in _VALID_BASS_STRING_COUNTS:
        raise ValueError(f"bass strings must be one of {_VALID_BASS_STRING_COUNTS}, got {strings}")
    if not guitar_open:
        raise ValueError("guitar_open must be non-empty")

    top = min(guitar_open) - 12
    # Descend from the top string in perfect 4ths (5 semitones), then put
    # back in ascending (low-to-high) order to match this project's tuning
    # convention (see presets/tunings.json: index 0 is the lowest string).
    descending = [top - 5 * i for i in range(strings)]
    return list(reversed(descending))


def build_bass_fretboard(guitar_open: list[int], strings: int = 4, max_fret: int = 20) -> Fretboard:
    """Convenience wrapper: derive a bass tuning from a guitar tuning and
    wrap it directly in a `Fretboard`. `max_fret` defaults to 20 (a common
    real bass neck length) rather than `Fretboard`'s own 24-fret default --
    still an ordinary `Fretboard`, so it carries the exact same
    never-fabricate playability guarantees as the guitar's."""
    tuning = derive_bass_tuning(guitar_open, strings=strings)
    return Fretboard(tuning, max_fret=max_fret)


def _nearest_playable_octave(
    fretboard: Fretboard,
    pitch_class: int,
    reference_pitch: int,
    max_fret: int,
) -> tuple[int, tuple[int, int]]:
    """Search every octave of `pitch_class` the fretboard can reach, and
    return the (midi_pitch, (string, fret)) whose midi_pitch is closest to
    `reference_pitch`, restricted to positions that are ACTUALLY playable
    (round-trip through `fretboard.pitch_to_fret`, never fabricated).

    Raises ValueError only if truly no octave of this pitch class is
    reachable anywhere on the instrument within `max_fret` -- e.g. an
    unusually narrow `max_fret` combined with a tuning whose open strings
    never land on this pitch class within reach.
    """
    effective_max_fret = min(max_fret, fretboard.max_fret)
    lowest_open = min(fretboard.tuning)
    highest_reachable = max(fretboard.tuning) + effective_max_fret

    playable: list[tuple[int, tuple[int, int]]] = []
    # Start at or below the lowest open string, then step up by octaves so
    # every occurrence of pitch_class in the reachable span gets checked.
    candidate = lowest_open - ((lowest_open - pitch_class) % 12)
    while candidate <= highest_reachable:
        if candidate >= lowest_open:
            try:
                position = fretboard.pitch_to_fret(candidate, max_fret=effective_max_fret)
            except ValueError:
                pass
            else:
                playable.append((candidate, position))
        candidate += 12

    if not playable:
        raise ValueError(
            f"pitch class {pitch_class} is not reachable on this bass fretboard "
            f"within max_fret={effective_max_fret} at any octave"
        )
    return min(playable, key=lambda item: abs(item[0] - reference_pitch))


def follow_guitar_rhythm(
    guitar_cells: list[dict],
    guitar_pitches: list[int | None],
    bass_fretboard: Fretboard,
    max_fret: int = 12,
) -> list[dict]:
    """Produce a bass line rhythmically locked to `guitar_cells` (same
    duration/is_rest per cell, in order -- the bass never invents its own
    rhythm), but with every hit resolved onto `bass_fretboard`'s OWN real
    positions.

    `guitar_pitches` is a parallel list (same length as `guitar_cells`): the
    guitar's chosen MIDI pitch for each hit cell (any value for rest cells
    is ignored; `None` is fine there). For each hit, the guitar pitch's
    pitch class is resolved to the nearest ACTUALLY PLAYABLE octave on the
    bass fretboard (nominally an octave below the guitar's note, since that
    is the idiomatic bass register -- but if that exact octave is not
    reachable within `max_fret`, the nearest reachable octave of the same
    pitch class is used instead; see `_nearest_playable_octave`).

    Returns a list of cells shaped like the input's, plus "string", "fret"
    and "midi" (all `None` on rest cells).
    """
    if len(guitar_cells) != len(guitar_pitches):
        raise ValueError("guitar_cells and guitar_pitches must be the same length")

    out: list[dict] = []
    for cell, guitar_pitch in zip(guitar_cells, guitar_pitches):
        if cell["is_rest"]:
            out.append({
                "duration": cell["duration"],
                "is_rest": True,
                "string": None,
                "fret": None,
                "midi": None,
            })
            continue

        if guitar_pitch is None:
            raise ValueError("a hit cell must have a guitar pitch, got None")

        pitch_class = guitar_pitch % 12
        # Idiomatic bass register: aim an octave below the guitar's note,
        # then let _nearest_playable_octave correct to whatever octave of
        # this pitch class the bass can actually reach.
        reference_pitch = guitar_pitch - 12
        midi, (string, fret) = _nearest_playable_octave(
            bass_fretboard, pitch_class, reference_pitch, max_fret
        )
        out.append({
            "duration": cell["duration"],
            "is_rest": False,
            "string": string,
            "fret": fret,
            "midi": midi,
        })

    return out
