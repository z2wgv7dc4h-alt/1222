import pytest

from app.arrange import apply_order
from song import compose_song


def test_apply_order_reorders_real_sections():
    song = compose_song("djent", seed=3, num_sections=6)
    n = len(song["sections"])
    reversed_order = list(range(n - 1, -1, -1))

    rearranged = apply_order(song, reversed_order)

    assert rearranged["sections"] == [song["sections"][i] for i in reversed_order]
    assert rearranged["sequence"] == [song["sequence"][i] for i in reversed_order]
    assert rearranged["tempo_map"] == [song["tempo_map"][i] for i in reversed_order]
    # Untouched real data carried through unchanged.
    assert rearranged["preset_id"] == song["preset_id"]
    assert rearranged["guitar_fretboard"] is song["guitar_fretboard"]


def test_apply_order_duplicate_repeats_a_real_section():
    song = compose_song("metalcore", seed=1, num_sections=4)
    rearranged = apply_order(song, [0, 0, 1])
    assert len(rearranged["sections"]) == 3
    assert rearranged["sections"][0] == rearranged["sections"][1] == song["sections"][0]
    assert rearranged["sections"][2] == song["sections"][1]


def test_apply_order_solo_keeps_only_one_real_section():
    song = compose_song("metalcore", seed=1, num_sections=4)
    rearranged = apply_order(song, [2])
    assert rearranged["sections"] == [song["sections"][2]]
    assert rearranged["sequence"] == [song["sequence"][2]]


def test_apply_order_rejects_empty_order():
    song = compose_song("metalcore", seed=1, num_sections=4)
    with pytest.raises(ValueError):
        apply_order(song, [])


def test_apply_order_rejects_out_of_range_index():
    song = compose_song("metalcore", seed=1, num_sections=4)
    with pytest.raises(ValueError):
        apply_order(song, [0, 99])
    with pytest.raises(ValueError):
        apply_order(song, [-1])
