import pytest

from scales import ALIASES, SCALES, get_scale


def test_cluster_and_power_present():
    assert SCALES["cluster"] == (0, 1, 3, 6, 7, 8, 11)
    assert SCALES["power"] == (0, 5, 7)


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
