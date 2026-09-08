import pytest

from metric_modulation import apply_metric_modulation, modulation_ratio


# ---------------------------------------------------------------------------
# modulation_ratio -- correctness against the module's own verified worked
# examples (see metric_modulation.py's docstring for the full derivation).
# ---------------------------------------------------------------------------


def test_dotted_quarter_becomes_quarter_is_1_5():
    # The hard-required real-world reference case: "dotted quarter = new
    # quarter" is a standard modulation, and must compute to EXACTLY 1.5.
    assert modulation_ratio((3, 2), (1, 1)) == 1.5


def test_straight_eighth_becomes_quarter_is_0_5():
    # The classic djent/deathcore half-time breakdown treatment (also
    # song.py's real trigger condition): the eighth notes of the old pulse
    # become the new quarter-note beat.
    assert modulation_ratio((1, 2), (1, 1)) == 0.5


def test_eighth_triplet_becomes_quarter_is_one_third():
    assert modulation_ratio((1, 3), (1, 1)) == pytest.approx(1 / 3)


def test_dotted_eighth_becomes_quarter_is_0_75():
    assert modulation_ratio((3, 4), (1, 1)) == 0.75


def test_identical_subdivisions_give_ratio_one():
    # A degenerate but real case: the "old" and "new" beat unit are the
    # same note value -- no actual tempo change.
    assert modulation_ratio((1, 1), (1, 1)) == 1.0
    assert modulation_ratio((1, 2), (1, 2)) == 1.0


def test_modulation_ratio_is_reciprocal_when_subdivisions_swap():
    # value(old)/value(new) and value(new)/value(old) must be exact
    # reciprocals -- a real consistency check on the ratio formula, not
    # just isolated point checks.
    forward = modulation_ratio((3, 2), (1, 1))
    backward = modulation_ratio((1, 1), (3, 2))
    assert forward * backward == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# apply_metric_modulation -- trivial multiply, but real.
# ---------------------------------------------------------------------------


def test_apply_metric_modulation_scales_bpm():
    assert apply_metric_modulation(120.0, 1.5) == pytest.approx(180.0)
    assert apply_metric_modulation(120.0, 0.5) == pytest.approx(60.0)


def test_apply_metric_modulation_ratio_one_is_identity():
    assert apply_metric_modulation(140.0, 1.0) == pytest.approx(140.0)


# ---------------------------------------------------------------------------
# Bad-input rejection -- every documented failure case fails closed.
# ---------------------------------------------------------------------------


def test_modulation_ratio_rejects_zero_or_negative_numerator():
    with pytest.raises(ValueError):
        modulation_ratio((0, 2), (1, 1))
    with pytest.raises(ValueError):
        modulation_ratio((-1, 2), (1, 1))
    with pytest.raises(ValueError):
        modulation_ratio((1, 1), (0, 2))
    with pytest.raises(ValueError):
        modulation_ratio((1, 1), (-3, 2))


def test_modulation_ratio_rejects_zero_or_negative_denominator():
    with pytest.raises(ValueError):
        modulation_ratio((1, 0), (1, 1))
    with pytest.raises(ValueError):
        modulation_ratio((1, -2), (1, 1))
    with pytest.raises(ValueError):
        modulation_ratio((1, 1), (1, 0))
    with pytest.raises(ValueError):
        modulation_ratio((1, 1), (1, -2))


def test_modulation_ratio_rejects_malformed_subdivision_shape():
    with pytest.raises(ValueError):
        modulation_ratio((1,), (1, 1))
    with pytest.raises(ValueError):
        modulation_ratio((1, 2, 3), (1, 1))
    with pytest.raises(ValueError):
        modulation_ratio(1, (1, 1))


def test_apply_metric_modulation_rejects_non_positive_ratio():
    with pytest.raises(ValueError):
        apply_metric_modulation(120.0, 0)
    with pytest.raises(ValueError):
        apply_metric_modulation(120.0, -1.5)


def test_apply_metric_modulation_rejects_non_positive_base_bpm():
    with pytest.raises(ValueError):
        apply_metric_modulation(0.0, 1.5)
    with pytest.raises(ValueError):
        apply_metric_modulation(-140.0, 1.5)
