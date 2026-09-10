import random

import pytest

from theory import ARC, DISSONANT, Scale, VoiceLeader, _weighted_choice, arc, pick_pitch_interval_markov, shade


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


def test_walk_explicit_direction_is_always_honored_regardless_of_momentum():
    # An explicit, non-zero `direction` must win every time -- the real
    # momentum heuristic only applies to the default `direction=0` case.
    scale = Scale(60, "minor")
    vl = VoiceLeader(scale, low=40, high=80, anchor=60, rng=random.Random(0))
    vl.last = 60
    vl._walk_direction = -1  # deliberately opposite to what we'll request
    pitch = vl.walk(direction=1)
    assert pitch > 60


def test_walk_default_direction_has_real_momentum_not_a_coin_flip_every_step():
    """Regression test for a real, measured bug: without momentum, every
    `walk()` call independently re-rolled direction, producing a real
    71% direction-reversal rate in an actual generated solo (confirmed
    via direct user listening feedback -- "no nice melody"). With real
    momentum, consecutive same-direction steps must be measurably more
    common than a fair coin flip would produce."""
    scale = Scale(60, "minor")
    vl = VoiceLeader(scale, low=30, high=90, anchor=60, rng=random.Random(11))
    vl.last = 60
    directions = []
    for _ in range(300):
        before = vl.last
        after = vl.walk()
        directions.append(1 if after > before else (-1 if after < before else 0))
    pairs = [(a, b) for a, b in zip(directions, directions[1:]) if a != 0 and b != 0]
    same = sum(1 for a, b in pairs if a == b)
    same_fraction = same / len(pairs)
    assert same_fraction > 0.65, (
        f"expected real directional momentum to keep consecutive steps going the "
        f"same way well above chance (0.5), got {same_fraction:.2f}"
    )


def test_walk_momentum_updates_after_a_register_edge_reflection():
    # A reflection off the register edge must update the real persisted
    # direction to the NEW (reflected) direction, not silently keep the
    # old one -- otherwise the very next call would immediately try to
    # walk back off the same edge.
    scale = Scale(60, "minor")
    vl = VoiceLeader(scale, low=58, high=62, anchor=60, rng=random.Random(0))
    vl.last = vl.high
    vl._walk_direction = 1  # already heading toward the edge
    vl.walk()
    assert vl._walk_direction == -1


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


# -- real, corpus-derived markov sequence-awareness --------------------------


def test_weighted_choice_matches_original_inline_behavior():
    # Regression: `_weighted_choice` replaced two independent inline
    # accumulate-and-compare loops (VoiceLeader._weighted_interval's own,
    # and motif.pick_pitch_interval's own) -- same seed must still pick
    # the same real interval as the original inline math.
    items = [(0, 5.0), (7, 3.0), (3, 2.0)]
    rng = random.Random(7)
    r = rng.random() * sum(w for _iv, w in items)
    acc = 0.0
    expected = items[-1][0]
    for iv, w in items:
        acc += w
        if r <= acc:
            expected = iv
            break
    assert _weighted_choice(items, random.Random(7)) == expected


def test_weighted_choice_rejects_empty_or_non_positive_total():
    with pytest.raises(ValueError):
        _weighted_choice([], random.Random(0))
    with pytest.raises(ValueError):
        _weighted_choice([(0, 0.0), (7, 0.0)], random.Random(0))


def test_pick_pitch_interval_markov_falls_back_without_markov():
    weights = {0: 5.0, 7: 3.0}
    assert pick_pitch_interval_markov(weights, random.Random(1), None, None) in weights
    assert pick_pitch_interval_markov(weights, random.Random(1), {0: {7: 100.0}}, None) in weights


def test_pick_pitch_interval_markov_falls_back_on_unseen_context():
    weights = {0: 5.0, 7: 3.0}
    markov = {0: {7: 100.0}}  # no real data for prev_interval=3
    # Deterministic RNG check: with markov=None the pick would be drawn
    # from `weights`; an unseen prev_interval (3) must fall through to
    # the exact same real draw.
    expected = _weighted_choice(list(weights.items()), random.Random(9))
    assert pick_pitch_interval_markov(weights, random.Random(9), markov, 3) == expected


def test_pick_pitch_interval_markov_uses_real_context_when_available():
    weights = {0: 1.0, 7: 1.0, 3: 1.0}
    markov = {0: {7: 100.0}}  # after interval 0, ALWAYS interval 7
    rng = random.Random(123)
    picks = [pick_pitch_interval_markov(weights, rng, markov, 0) for _ in range(50)]
    assert all(p == 7 for p in picks)


def test_voiceleader_markov_none_is_byte_identical_to_before():
    scale = Scale(60, "minor")
    weights = {0: 5, 7: 3, 3: 2}
    vl_a = VoiceLeader(scale, weights=weights, rng=random.Random(42))
    vl_b = VoiceLeader(scale, weights=weights, rng=random.Random(42), markov=None)
    picks_a = [vl_a.pick() for _ in range(30)]
    picks_b = [vl_b.pick() for _ in range(30)]
    assert picks_a == picks_b


def test_voiceleader_markov_measurably_changes_real_picks():
    scale = Scale(60, "minor")
    weights = {0: 1.0, 7: 1.0, 3: 1.0}
    # After interval 0 (from anchor), ALWAYS interval 7 -- a real,
    # extreme, unmistakable synthetic transition table.
    markov = {0: {7: 100.0}}
    vl = VoiceLeader(scale, weights=weights, rng=random.Random(5), anchor=60, low=48, high=84, markov=markov)
    # Force a real interval-0 context (as if the previous pick had been
    # interval 0), then confirm the real internal weighted-interval
    # mechanism reflects the markov row: every draw comes out as 7, not
    # the marginal 1/3-1/3-1/3 split `weights` alone would produce.
    picks = []
    for _ in range(30):
        vl.last_interval = 0  # re-force the same real context every draw
        picks.append(vl._weighted_interval())
    assert all(p == 7 for p in picks)


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
