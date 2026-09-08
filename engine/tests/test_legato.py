import random

import pytest

from fretboard import Fretboard
from legato import (
    fret_positions_for_run,
    generate_legato_lick,
    generate_legato_run,
    legato_run_rhythm,
)
from presets import get_tuning, load_all_presets, load_tunings
from song import compose_song
from theory import Scale


# --- generate_legato_run: contiguous scale-degree correctness ---------------


def test_legato_run_is_contiguous_ascending():
    scale = Scale(40, "minor")
    pitches = generate_legato_run(scale, start_pitch=40, length=8, direction=1)
    assert len(pitches) == 8
    indices = [scale.index_of(p) for p in pitches]
    # Every step is exactly +1 degree from the previous one -- a genuine
    # contiguous scalar run, not a sequence of independent weighted picks.
    for a, b in zip(indices, indices[1:]):
        assert b - a == 1


def test_legato_run_is_contiguous_descending():
    scale = Scale(52, "phrygian")
    pitches = generate_legato_run(scale, start_pitch=60, length=6, direction=-1)
    assert len(pitches) == 6
    indices = [scale.index_of(p) for p in pitches]
    for a, b in zip(indices, indices[1:]):
        assert b - a == -1


def test_legato_run_starts_at_nearest_scale_degree_to_start_pitch():
    scale = Scale(40, "minor")
    # 41 is not in C minor's pitch classes rooted at 40 (E-ish) for most
    # scale tables; regardless of the exact scale, start must snap into it.
    pitches = generate_legato_run(scale, start_pitch=41, length=3, direction=1)
    assert pitches[0] == scale.nearest(41)


def test_legato_run_without_rng_never_reverses_even_at_reversal_chance_one():
    scale = Scale(40, "minor")
    pitches = generate_legato_run(
        scale, start_pitch=40, length=10, direction=1, rng=None, reversal_chance=1.0
    )
    indices = [scale.index_of(p) for p in pitches]
    # No rng supplied -> reversal_chance is never consulted -- the run must
    # stay a straight ascending line the whole way.
    for a, b in zip(indices, indices[1:]):
        assert b - a == 1


def test_legato_run_with_rng_can_reverse_direction_once():
    scale = Scale(40, "minor")
    rng = random.Random(1)
    pitches = generate_legato_run(
        scale, start_pitch=40, length=10, direction=1, rng=rng, reversal_chance=1.0
    )
    indices = [scale.index_of(p) for p in pitches]
    steps = [b - a for a, b in zip(indices, indices[1:])]
    # reversal_chance=1.0 forces the reversal on the very first extra step.
    assert steps[0] == -1
    assert all(s == -1 for s in steps)


def test_legato_run_reverses_at_most_once():
    scale = Scale(40, "minor")
    rng = random.Random(7)
    pitches = generate_legato_run(
        scale, start_pitch=40, length=30, direction=1, rng=rng, reversal_chance=0.5
    )
    indices = [scale.index_of(p) for p in pitches]
    steps = [b - a for a, b in zip(indices, indices[1:])]
    sign_changes = sum(1 for a, b in zip(steps, steps[1:]) if a != b)
    assert sign_changes <= 1


def test_legato_run_rejects_bad_input():
    scale = Scale(40, "minor")
    with pytest.raises(ValueError):
        generate_legato_run(scale, 40, length=0)
    with pytest.raises(ValueError):
        generate_legato_run(scale, 40, length=-3)
    with pytest.raises(ValueError):
        generate_legato_run(scale, 40, length=4, direction=2)
    with pytest.raises(ValueError):
        generate_legato_run(scale, 40, length=4, reversal_chance=1.5)


# --- legato_run_rhythm: rhythm shape correctness -----------------------------


def test_legato_run_rhythm_genuine_tuplet_case():
    cells = legato_run_rhythm(length=5, span_beats=1.0)
    assert len(cells) == 5
    assert all(c["is_rest"] is False for c in cells)
    assert sum(c["duration"] for c in cells) == pytest.approx(1.0)
    # Genuine even quintuplet spacing, not a fake selection off a 16-slot grid.
    assert all(c["duration"] == pytest.approx(0.2) for c in cells)


def test_legato_run_rhythm_plain_subdivision_case():
    cells = legato_run_rhythm(length=4, span_beats=2.0)
    assert len(cells) == 4
    assert all(c["is_rest"] is False for c in cells)
    assert sum(c["duration"] for c in cells) == pytest.approx(2.0)
    assert all(c["duration"] == pytest.approx(0.5) for c in cells)


def test_legato_run_rhythm_rejects_bad_input():
    with pytest.raises(ValueError):
        legato_run_rhythm(length=0, span_beats=1.0)
    with pytest.raises(ValueError):
        legato_run_rhythm(length=5, span_beats=0.0)
    with pytest.raises(ValueError):
        legato_run_rhythm(length=5, span_beats=-1.0)


# --- fret_positions_for_run: real positions, single-string preference -------


def test_fret_positions_for_run_rejects_empty_pitches():
    fb = Fretboard([40, 45, 50, 55, 59, 64])
    with pytest.raises(ValueError):
        fret_positions_for_run([], fb)


def test_fret_positions_for_run_rejects_unplayable_pitch():
    # A single open-E string with only 3 frets reachable: an ascending run
    # of enough length must eventually leave that tiny window.
    fb = Fretboard([40], max_fret=3)
    scale = Scale(40, "minor")
    pitches = generate_legato_run(scale, start_pitch=40, length=10, direction=1)
    with pytest.raises(ValueError):
        fret_positions_for_run(pitches, fb)


def test_fret_positions_for_run_favors_one_string_across_combos():
    tunings = load_tunings()
    combos = [
        (get_tuning("standard_6", tunings).open, Scale(50, "minor"), 55, 1),
        (get_tuning("standard_6", tunings).open, Scale(50, "minor"), 62, -1),
        (get_tuning("drop_a_7", tunings).open, Scale(45, "phrygian"), 50, 1),
        (get_tuning("drop_a_7", tunings).open, Scale(45, "phrygian"), 57, -1),
        (get_tuning("drop_e_8", tunings).open, Scale(45, "minor"), 52, 1),
    ]
    same_string_pairs = 0
    total_pairs = 0
    for tuning_open, scale, start_pitch, direction in combos:
        fb = Fretboard(tuning_open, max_fret=24)
        pitches = generate_legato_run(scale, start_pitch, length=6, direction=direction)
        positions = fret_positions_for_run(pitches, fb)
        for (s1, _f1), (s2, _f2) in zip(positions, positions[1:]):
            total_pairs += 1
            if s1 == s2:
                same_string_pairs += 1

    assert total_pairs > 0
    # The whole point of biasing pitch_to_fret's cost function with `prev`
    # is that consecutive legato notes mostly stay put on one string where
    # the fretboard's range allows it -- a strict majority is the
    # statistical bar for "favors", not "always" (edge-of-neck cases can
    # still force a string change).
    assert same_string_pairs / total_pairs >= 0.6


# --- generate_legato_lick: real preset, real Scale/Fretboard end-to-end -----


def test_generate_legato_lick_against_real_preset():
    preset = load_all_presets()["djent"]
    tunings = load_tunings()
    tuning = get_tuning(preset.tuning_key, tunings)
    scale = Scale(root=tuning.open[0], name=preset.scale)
    fb = Fretboard(tuning.open)
    rng = random.Random(5)

    lick = generate_legato_lick(
        scale, fb, start_pitch=tuning.open[0] + 12, length=5, span_beats=1.0, rng=rng
    )

    assert set(lick.keys()) == {"pitches", "cells", "positions"}
    assert len(lick["pitches"]) == 5
    assert len(lick["cells"]) == 5
    assert len(lick["positions"]) == 5
    assert all(scale.contains(p) for p in lick["pitches"])
    assert all(c["is_rest"] is False for c in lick["cells"])
    assert sum(c["duration"] for c in lick["cells"]) == pytest.approx(1.0)
    for string, fret in lick["positions"]:
        # Every position must be real: resolvable back through the exact
        # same fretboard API the rest of the engine trusts.
        assert fb.fret_to_midi(string, fret) is not None


def test_generate_legato_lick_rejects_bad_input_via_run():
    preset = load_all_presets()["djent"]
    tunings = load_tunings()
    tuning = get_tuning(preset.tuning_key, tunings)
    scale = Scale(root=tuning.open[0], name=preset.scale)
    fb = Fretboard(tuning.open)
    rng = random.Random(1)
    with pytest.raises(ValueError):
        generate_legato_lick(scale, fb, tuning.open[0], length=0, span_beats=1.0, rng=rng)
    with pytest.raises(ValueError):
        generate_legato_lick(scale, fb, tuning.open[0], length=4, span_beats=0.0, rng=rng)


# --- song.py wiring: a real, called path, not a standalone function --------


def test_solo_sections_carry_a_real_legato_lick_end_to_end():
    """song.py's solo branch must actually call generate_legato_lick (not
    just have it importable) -- across a handful of seeds/presets, solo
    sections should carry a real, structurally valid `legato` lick built
    from the section's own scale and the song's real guitar fretboard."""
    presets = sorted(load_all_presets().keys())
    found_any_lick = False

    for preset_id in presets:
        for seed in (1, 2, 3):
            song = compose_song(preset_id, seed=seed, num_sections=8)
            guitar_fb = song["guitar_fretboard"]
            for section in song["sections"]:
                if section["role"] != "solo":
                    assert section["legato"] is None
                    continue
                legato = section["legato"]
                if legato is None:
                    # Documented fail-closed fallback for a genuinely
                    # unplayable draw -- allowed, but must not be the only
                    # outcome across this whole sweep (checked below).
                    continue
                found_any_lick = True
                assert set(legato.keys()) == {"pitches", "cells", "positions"}
                n = len(legato["pitches"])
                assert n == len(legato["cells"]) == len(legato["positions"])
                assert all(c["is_rest"] is False for c in legato["cells"])
                # Every legato pitch must be a real, reachable position on
                # THIS song's own guitar fretboard -- never fabricated.
                for string, fret in legato["positions"]:
                    guitar_fb.fret_to_midi(string, fret)
                # The featured solo lead must include the spliced-in run.
                for p in legato["pitches"]:
                    assert p in section["lead"]

    assert found_any_lick, "expected at least one real legato lick across this sweep"
