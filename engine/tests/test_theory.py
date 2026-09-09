import random

import pytest

from theory import ARC, DISSONANT, Scale, VoiceLeader, arc, shade


# -- Scale --------------------------------------------------------------------

def test_scale_uses_scales_py_as_the_source_of_truth():
    s = Scale(60, "minor")
    assert s.intervals == (0, 2, 3, 5, 7, 8, 10)


def test_scale_rejects_unknown_name():
    with pytest.raises(ValueError):
        Scale(60, "not-a-real-scale")


def test_scale_nearest_and_step():
    s = Scale(60, "minor")  # C minor: C D Eb F G Ab Bb
    assert s.contains(s.nearest(61))  # 61 (C#) isn't in the scale; its snap must be
    assert s.step(60, 1) == 62  # root -> 2nd degree


# -- shade() ------------------------------------------------------------------

def test_shade_never_zeroes_a_nonzero_weight():
    weights = {0: 10, 1: 5, 7: 3, 6: 2}
    for dissonance in (0.0, 0.25, 0.5, 0.75, 1.0):
        shaded = shade(weights, dissonance)
        for iv in weights:
            assert shaded[iv] > 0, f"interval {iv} was zeroed at dissonance={dissonance}"


def test_shade_never_introduces_an_interval_that_was_absent():
    weights = {0: 10, 7: 3}  # no m2/M2/tritone/M7 present at all
    for dissonance in (0.0, 0.5, 1.0):
        shaded = shade(weights, dissonance)
        assert set(shaded) == set(weights)
        for iv in DISSONANT:
            assert iv not in shaded


def test_shade_pushes_dissonant_intervals_up_as_dissonance_rises():
    weights = {0: 10, 1: 10}
    low = shade(weights, 0.0)
    high = shade(weights, 1.0)
    assert high[1] > low[1]
    assert high[0] < low[0]


# -- VoiceLeader ----------------------------------------------------------------

def test_pick_stays_in_scale_and_in_range():
    scale = Scale(60, "minor")
    vl = VoiceLeader(scale, weights={0: 5, 3: 3, 7: 3, 8: 2}, rng=random.Random(42))
    for _ in range(50):
        pitch = vl.pick()
        assert vl.low <= pitch <= vl.high
        assert scale.contains(pitch)


def test_walk_reflects_off_register_edges_instead_of_leaving():
    scale = Scale(60, "minor")
    vl = VoiceLeader(scale, low=60, high=62, anchor=60, rng=random.Random(0))
    vl.last = vl.high
    for _ in range(30):
        pitch = vl.walk(direction=1)  # always push "up" -- must reflect down
        assert vl.low <= pitch <= vl.high


def test_move_blends_pick_and_walk_by_motion():
    scale = Scale(60, "minor")

    # motion=0 -> always pick (never a pure diatonic step away from last)
    vl_anchored = VoiceLeader(scale, weights={0: 1, 7: 1}, motion=0.0, rng=random.Random(1))
    vl_anchored.last = 60
    for _ in range(20):
        vl_anchored.move()  # should never raise / should stay in range
        assert vl_anchored.low <= vl_anchored.last <= vl_anchored.high

    # motion=1 -> always walk
    vl_active = VoiceLeader(scale, weights={0: 1, 7: 1}, motion=1.0, rng=random.Random(1))
    vl_active.last = 60
    seen = set()
    for _ in range(20):
        seen.add(vl_active.move())
    # pure stepwise motion from a fixed start should visit more than one
    # neighbouring degree, not just re-pick a single interval repeatedly.
    assert len(seen) > 1


def test_stab_is_exempt_from_register_smoothing():
    scale = Scale(60, "minor")
    vl = VoiceLeader(scale, low=55, high=70, anchor=60, rng=random.Random(0))
    leapt = vl.stab(prev=60, interval=12)
    assert leapt == 72  # a full octave leap, not pulled back toward `prev`


def test_voiceleader_ignores_non_positive_weights():
    scale = Scale(60, "minor")
    vl = VoiceLeader(scale, weights={0: 1, 7: 0, 3: -1})
    assert 7 not in vl.weights
    assert 3 not in vl.weights


# -- ARC ------------------------------------------------------------------------

def test_density_is_derived_not_settable():
    row = arc("C")
    assert row["density"] == round(0.28 + 0.62 * row["energy"], 4)
    # ARC's own stored rows carry no "density" key -- it cannot be set
    # independently of energy, only computed from it.
    assert "density" not in ARC["C"]


def test_changing_energy_changes_density_in_lockstep():
    low_energy = arc("K")   # energy 0.20
    high_energy = arc("C")  # energy 1.00
    assert low_energy["energy"] < high_energy["energy"]
    assert low_energy["density"] < high_energy["density"]
    assert low_energy["density"] == round(0.28 + 0.62 * low_energy["energy"], 4)
    assert high_energy["density"] == round(0.28 + 0.62 * high_energy["energy"], 4)


def test_arc_density_cannot_be_overridden_independently():
    row = arc("A")
    row["density"] = 999.0  # mutate the returned copy
    fresh = arc("A")  # a fresh call recomputes it -- proves it's not stored state
    assert fresh["density"] != 999.0
    assert fresh["density"] == round(0.28 + 0.62 * fresh["energy"], 4)


def test_arc_unknown_letter_falls_back_to_default():
    row = arc("nonexistent-letter")
    assert row["letter"] == "A"


# X.28 -- verse/chorus now resolve to the real, previously-unmapped "A"/"B"
# ARC rows (real verse-vs-chorus energy contrast: 0.60 vs 0.70).
def test_arc_verse_resolves_to_the_real_a_row():
    row = arc(role="verse")
    assert row["letter"] == "A"
    assert row == arc("A")


def test_arc_chorus_resolves_to_the_real_b_row():
    row = arc(role="chorus")
    assert row["letter"] == "B"
    assert row == arc("B")


def test_arc_chorus_has_higher_energy_than_verse():
    assert arc(role="chorus")["energy"] > arc(role="verse")["energy"]
