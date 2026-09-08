"""Metric modulation -- the pulse itself reinterprets at a transition point.

This is a genuinely different device from `rhythm.tile_cell` (polymeter: a
short cell phase-drifting against a longer FIXED span) and
`rhythm.metric_polyrhythm` (independent simultaneous grids): both of those
stay inside one constant underlying tempo the whole time. A metric
modulation instead says "a note value that used to be a SUBDIVISION of the
old beat now IS the new beat" -- the classic Meshuggah/Tool/Periphery move
where a dotted-eighth or a triplet grouping of the old pulse becomes the new
quarter-note pulse, and the perceived tempo genuinely shifts by a defined
ratio.

Per scope sec.17.5 (see structure.py's P6.7 section), this stays
INTERNAL song-planning data -- the actual Reaper export is one constant
tempo. This module only computes the ratio/BPM math; `structure.tempo_at`
wires it into the real per-section tempo dispatch, and `song.compose_song`
wires THAT into a real trigger condition (see that module's docstring for
the chosen build->breakdown trigger).

Subdivision convention
-----------------------
A subdivision is a `(numerator, denominator)` pair. Its VALUE -- the
fraction of one quarter note it lasts -- is simply `numerator / denominator`.
This is deliberately the plainest possible encoding (no nested "N/D of some
OTHER named note" indirection): the tuple's own fraction IS the answer, in
units of quarter notes.

Worked, verified examples (each is `numerator/denominator` and matches real
rhythmic theory for that note value's duration relative to a quarter note):

  - plain quarter note      : (1, 1) -> 1/1   = 1.0    quarters
  - dotted quarter note     : (3, 2) -> 3/2   = 1.5    quarters
      (a dot adds half the note's own value: 1 + 0.5 = 1.5)
  - straight eighth note    : (1, 2) -> 1/2   = 0.5    quarters
  - dotted eighth note      : (3, 4) -> 3/4   = 0.75   quarters
      (an eighth is 0.5 quarters; its dot adds half of THAT: 0.5+0.25=0.75)
  - eighth-note triplet     : (1, 3) -> 1/3   = 0.3333 quarters
      (3 of them fill exactly one quarter, by definition of a triplet)
  - straight sixteenth note : (1, 4) -> 1/4   = 0.25   quarters

`modulation_ratio(old_subdivision, new_subdivision)` is
`value(old_subdivision) / value(new_subdivision)` -- the factor
`apply_metric_modulation` multiplies `base_bpm` by to land on the new
tempo. Worked, verified examples of the RATIO itself:

  - "dotted quarter = new quarter" (a very standard, textbook modulation):
    modulation_ratio((3, 2), (1, 1)) == 1.5 / 1.0 == 1.5  (hard requirement)
  - "straight eighth = new quarter" (a half-time feel -- the classic
    djent/deathcore breakdown treatment, see song.py's trigger):
    modulation_ratio((1, 2), (1, 1)) == 0.5 / 1.0 == 0.5
  - "eighth-note triplet = new quarter":
    modulation_ratio((1, 3), (1, 1)) == (1/3) / 1.0 == 0.3333...
"""
from __future__ import annotations

__all__ = ["modulation_ratio", "apply_metric_modulation"]


def _subdivision_value(subdivision: tuple[int, int]) -> float:
    """Fraction-of-a-quarter-note value of one `(numerator, denominator)`
    subdivision -- see this module's docstring for the convention and
    worked examples. Both numerator and denominator must be strictly
    positive (a subdivision is a real, positive note-value fraction; there
    is no such thing as a zero-length or negative note)."""
    if not isinstance(subdivision, (tuple, list)) or len(subdivision) != 2:
        raise ValueError(f"subdivision must be a (numerator, denominator) pair, got {subdivision!r}")
    numerator, denominator = subdivision
    if numerator <= 0:
        raise ValueError(f"subdivision numerator must be > 0, got {numerator!r}")
    if denominator <= 0:
        raise ValueError(f"subdivision denominator must be > 0, got {denominator!r}")
    return numerator / denominator


def modulation_ratio(old_subdivision: tuple[int, int], new_subdivision: tuple[int, int]) -> float:
    """Tempo-scaling ratio for a metric modulation where a note value from
    the OLD pulse (`old_subdivision`) becomes the new beat unit
    (`new_subdivision`).

    `ratio = value(old_subdivision) / value(new_subdivision)` where
    `value(n, d) = n / d` is the subdivision's duration as a fraction of
    one quarter note (see module docstring). Feed the result to
    `apply_metric_modulation(base_bpm, ratio)` to get the new tempo.

    Verified worked examples (see module docstring for the full set):
      >>> modulation_ratio((3, 2), (1, 1))  # dotted quarter = new quarter
      1.5
      >>> modulation_ratio((1, 2), (1, 1))  # straight eighth = new quarter
      0.5

    Raises `ValueError` if either subdivision has a non-positive numerator
    or denominator, or isn't a real 2-tuple -- fails closed rather than
    silently dividing by zero or returning a nonsense negative ratio.
    """
    old_value = _subdivision_value(old_subdivision)
    new_value = _subdivision_value(new_subdivision)
    return old_value / new_value


def apply_metric_modulation(base_bpm: float, ratio: float) -> float:
    """New tempo after a metric modulation: `base_bpm * ratio`.

    Trivial arithmetic, but real -- `ratio` should come from
    `modulation_ratio` (or be a caller-verified positive scalar); this
    function's only job is to fail closed on nonsense inputs rather than
    silently producing a zero, negative, or NaN-adjacent tempo:
      - `base_bpm` must be > 0 (a tempo of zero or negative BPM isn't real).
      - `ratio` must be > 0 (a zero/negative scaling would produce a
        zero/negative or sign-flipped tempo, never a real modulation).
    """
    if base_bpm <= 0:
        raise ValueError(f"base_bpm must be > 0, got {base_bpm!r}")
    if ratio <= 0:
        raise ValueError(f"ratio must be > 0, got {ratio!r}")
    return base_bpm * ratio
