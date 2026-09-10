import pytest

from scales import ALIASES, SCALES, get_scale


def test_cluster_and_power_present():
    assert SCALES["cluster"] == (0, 1, 3, 6, 7, 8, 11)
    assert SCALES["power"] == (0, 5, 7)


def test_phrygian_dominant_present_and_matches_the_real_reference():
    # Ported directly from reference/ww-forge-prior-attempt/engine/
    # theory.py's own real interval tuple -- the 5th mode of harmonic
    # minor (real music-theory identity, cross-checked, not just copied
    # blind): harmonic_minor's degree index 4 (pitch 7) becomes the new
    # root, and every other degree's real interval-from-7 comes out to
    # this exact tuple.
    assert SCALES["phrygian_dominant"] == (0, 1, 4, 5, 7, 8, 10)
    harmonic_minor = SCALES["harmonic_minor"]
    fifth_mode_root = harmonic_minor[4]
    recomputed = tuple(sorted((iv - fifth_mode_root) % 12 for iv in harmonic_minor))
    assert recomputed == SCALES["phrygian_dominant"]


def test_no_duplicate_non_alias_scales():
    seen: dict[tuple[int, ...], str] = {}
    for name, intervals in SCALES.items():
        assert intervals not in seen, (
            f"scale '{name}' duplicates the interval set of '{seen.get(intervals)}' "
            "-- add it to ALIASES instead of a second canonical entry"
        )
        seen[intervals] = name


def test_aliases_match_their_canonical_intervals():
    for alias, canonical in ALIASES.items():
        assert canonical in SCALES
        assert get_scale(alias) == SCALES[canonical]


def test_get_scale_rejects_unknown_name():
    with pytest.raises(ValueError):
        get_scale("not-a-real-scale")
