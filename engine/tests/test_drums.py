import random

import pytest

from drums import (
    FALLBACKS,
    ROLE_TO_NOTE,
    generate_blast_fill,
    kick_follows_guitar,
    note_for_role,
)
from rhythm import RhythmRegistry, generate_rhythm

# --- P4.1: role -> note + wired fallback ------------------------------------


def test_note_for_role_resolves_every_mapped_role():
    for role, note in ROLE_TO_NOTE.items():
        assert note_for_role(role) == note


def test_note_for_role_china_falls_back_to_crash_2():
    # This kit has no china sample at all (god-tier-metal-scope.md 11.7).
    # It must resolve through the wired fallback to CRASH_2's real note,
    # not raise and not fabricate some other note.
    assert "CHINA" not in ROLE_TO_NOTE
    assert FALLBACKS["CHINA"] == "CRASH_2"
    assert note_for_role("CHINA") == ROLE_TO_NOTE["CRASH_2"]


def test_note_for_role_rejects_unknown_role():
    with pytest.raises(KeyError):
        note_for_role("NOT_A_REAL_ROLE")


def test_note_for_role_custom_mapping_and_fallback_are_wired_not_hardcoded():
    # note_for_role must actually use the mapping/fallback args passed in,
    # not silently fall back to the module-level defaults -- otherwise a
    # different kit's tables could never take effect.
    custom_mapping = {"SNARE": 100}
    custom_fallback = {"CHINA": "SNARE"}
    assert note_for_role("SNARE", custom_mapping, custom_fallback) == 100
    assert note_for_role("CHINA", custom_mapping, custom_fallback) == 100
    with pytest.raises(KeyError):
        note_for_role("KICK", custom_mapping, custom_fallback)


# --- P4.2: kick follows guitar accents ---------------------------------------


def test_kick_follows_guitar_hit_positions_match_exactly():
    rng = random.Random(11)
    guitar_cells = generate_rhythm(8.0, [0.25, 0.5], hit_chance=0.55, rng=rng)

    kick_cells = kick_follows_guitar(guitar_cells)

    assert len(kick_cells) == len(guitar_cells)
    for guitar_cell, kick_cell in zip(guitar_cells, kick_cells):
        assert kick_cell["duration"] == guitar_cell["duration"]
        assert kick_cell["is_rest"] == guitar_cell["is_rest"]
        if guitar_cell["is_rest"]:
            assert kick_cell["role"] is None
        else:
            assert kick_cell["role"] == "KICK"

    guitar_hit_positions = [i for i, c in enumerate(guitar_cells) if not c["is_rest"]]
    kick_hit_positions = [i for i, c in enumerate(kick_cells) if not c["is_rest"]]
    assert kick_hit_positions == guitar_hit_positions


def test_kick_follows_guitar_all_rests_and_all_hits():
    rng = random.Random(1)
    all_rests = generate_rhythm(4.0, [0.5], hit_chance=0.0, rng=rng)
    all_hits = generate_rhythm(4.0, [0.5], hit_chance=1.0, rng=random.Random(1))

    assert all(c["role"] is None for c in kick_follows_guitar(all_rests))
    assert all(c["role"] == "KICK" for c in kick_follows_guitar(all_hits))


def test_kick_follows_guitar_rejects_empty_input():
    with pytest.raises(ValueError):
        kick_follows_guitar([])


# --- P4.3: fills/blasts, shared-sequence + rendering ------------------------


def test_blast_fill_shares_exact_timing_via_rhythm_id():
    registry = RhythmRegistry()
    rng_a = random.Random(5)
    rng_b = random.Random(999)  # deliberately different seed/state

    first = generate_blast_fill(
        "fill-A", registry, 4.0, [0.25, 0.5], 0.6, {"traditional": 1.0}, rng_a
    )
    second = generate_blast_fill(
        "fill-A", registry, 4.0, [0.25, 0.5], 0.6, {"traditional": 1.0}, rng_b
    )

    first_durations = [c["duration"] for c in first["cells"]]
    second_durations = [c["duration"] for c in second["cells"]]
    first_rests = [c["is_rest"] for c in first["cells"]]
    second_rests = [c["is_rest"] for c in second["cells"]]

    # Same rhythm_id -> identical underlying skeleton (same offsets/timing)
    # even though the second call's rng is completely different.
    assert first_durations == second_durations
    assert first_rests == second_rests

    # Independent confirmation straight from the registry itself.
    assert "fill-A" in registry


def test_blast_fill_different_rhythm_id_is_independent():
    registry = RhythmRegistry()
    a = generate_blast_fill(
        "fill-X", registry, 4.0, [0.25, 0.5], 0.6, {"traditional": 1.0}, random.Random(2)
    )
    b = generate_blast_fill(
        "fill-Y", registry, 4.0, [0.25, 0.5], 0.6, {"traditional": 1.0}, random.Random(3)
    )
    # Not asserting they differ (they could coincidentally match) -- just
    # that both ids are tracked independently in the shared registry.
    assert "fill-X" in registry and "fill-Y" in registry


def test_blast_traditional_vs_gravity_role_sequences_differ_meaningfully():
    registry = RhythmRegistry()
    rng = random.Random(42)
    # Same rhythm_id -> identical skeleton for both renderings, so any
    # difference in role sequence comes purely from the blast type.
    traditional = generate_blast_fill(
        "shared-span", registry, 6.0, [0.5, 1.0], 0.75, {"traditional": 1.0}, rng
    )
    gravity = generate_blast_fill(
        "shared-span", registry, 6.0, [0.5, 1.0], 0.75, {"gravity": 1.0}, rng
    )

    assert traditional["blast_type"] == "traditional"
    assert gravity["blast_type"] == "gravity"

    traditional_roles = [c["roles"] for c in traditional["cells"]]
    gravity_roles = [c["roles"] for c in gravity["cells"]]

    # Same skeleton (shared rhythm_id) means same hit/rest layout...
    assert [c["is_rest"] for c in traditional["cells"]] == [
        c["is_rest"] for c in gravity["cells"]
    ]
    # ...but the actual KICK/SNARE assignment must differ somewhere, since
    # gravity resets its alternation every beat while traditional runs one
    # continuous toggle across the whole span.
    assert traditional_roles != gravity_roles


def test_blast_hammer_hits_kick_and_snare_in_unison():
    registry = RhythmRegistry()
    rng = random.Random(3)
    result = generate_blast_fill(
        "hammer-span", registry, 4.0, [0.5], 1.0, {"hammer": 1.0}, rng
    )
    assert result["blast_type"] == "hammer"
    for cell in result["cells"]:
        assert cell["roles"] == ["KICK", "SNARE"]


def test_blast_zero_weight_type_never_picked():
    registry = RhythmRegistry()
    for seed in range(20):
        result = generate_blast_fill(
            "zero-weight-check",
            registry,
            4.0,
            [0.5],
            0.6,
            {"traditional": 1.0, "gravity": 0.0, "hammer": 0.0},
            random.Random(seed),
        )
        assert result["blast_type"] == "traditional"


def test_blast_fill_rejects_unsupported_blast_type():
    registry = RhythmRegistry()
    with pytest.raises(ValueError):
        generate_blast_fill(
            "bogus-type", registry, 4.0, [0.5], 0.6, {"not_a_real_blast": 1.0}, random.Random(1)
        )
