"""Metric modulation -- the pulse itself reinterprets at a transition point."""
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
