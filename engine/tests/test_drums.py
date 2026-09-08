import random

import pytest

from drums import (
    FALLBACKS,
    ROLE_TO_NOTE,
    generate_blast_fill,
    kick_follows_guitar,
    kick_pattern_for_style,
    note_for_role,
)
from presets import load_all_presets
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


# --- kick-style dispatch: closes the "preset.kick declared, never read" gap -


def test_kick_pattern_for_style_rejects_unknown_style():
    rng = random.Random(1)
    cells = generate_rhythm(4.0, [0.5], hit_chance=0.5, rng=rng)
    with pytest.raises(ValueError):
        kick_pattern_for_style(cells, "not_a_real_style")


def test_kick_pattern_for_style_rejects_empty_guitar_cells():
    with pytest.raises(ValueError):
        kick_pattern_for_style([], "bounce")


@pytest.mark.parametrize("style", ["bounce", "lock"])
def test_kick_pattern_for_style_bounce_and_lock_match_kick_follows_guitar(style):
    rng = random.Random(21)
    guitar_cells = generate_rhythm(8.0, [0.25, 0.5], hit_chance=0.55, rng=rng)
    expected = kick_follows_guitar(guitar_cells)
    actual = kick_pattern_for_style(guitar_cells, style)
    assert actual == expected


def test_kick_pattern_for_style_sparse_is_a_reduced_subset_of_guitar_hits():
    rng = random.Random(3)
    guitar_cells = generate_rhythm(8.0, [0.25, 0.5], hit_chance=0.8, rng=rng)
    sparse = kick_pattern_for_style(guitar_cells, "sparse")

    guitar_hit_positions = {i for i, c in enumerate(guitar_cells) if not c["is_rest"]}
    sparse_hit_positions = {i for i, c in enumerate(sparse) if not c["is_rest"]}

    assert len(sparse) == len(guitar_cells)
    # Every sparse hit is a REAL guitar hit position -- never a fabricated
    # position the guitar itself rests on.
    assert sparse_hit_positions <= guitar_hit_positions
    # And it is genuinely thinner than a 1:1 lock, not accidentally the
    # same density (there must be enough guitar hits for this to be
    # meaningful, which hit_chance=0.8 over 8 beats guarantees).
    assert len(guitar_hit_positions) >= 4
    assert len(sparse_hit_positions) < len(guitar_hit_positions)


def test_kick_pattern_for_style_euclid_matches_guitar_hit_count_but_not_positions():
    rng = random.Random(9)
    guitar_cells = generate_rhythm(16.0, [0.25, 0.5, 1.0], hit_chance=0.5, rng=rng)
    euclid = kick_pattern_for_style(guitar_cells, "euclid")

    guitar_hit_count = sum(1 for c in guitar_cells if not c["is_rest"])
    euclid_hit_count = sum(1 for c in euclid if not c["is_rest"])
    assert euclid_hit_count == guitar_hit_count
    assert len(euclid) == len(guitar_cells)

    guitar_hit_positions = [i for i, c in enumerate(guitar_cells) if not c["is_rest"]]
    euclid_hit_positions = [i for i, c in enumerate(euclid) if not c["is_rest"]]
    # The whole point of "euclid" as a distinct style: it must NOT just be
    # a copy of the guitar's own hit positions.
    assert euclid_hit_positions != guitar_hit_positions


def test_kick_pattern_for_style_euclid_is_maximally_even():
    # A hand-checkable case: E(3, 8) is the canonical "tresillo" pattern
    # X..X..X. -- hits at indices 0, 3, 6.
    guitar_cells = [{"duration": 0.5, "is_rest": (i not in (0, 1, 2))} for i in range(8)]
    euclid = kick_pattern_for_style(guitar_cells, "euclid")
    hit_positions = [i for i, c in enumerate(euclid) if not c["is_rest"]]
    assert hit_positions == [0, 3, 6]
    for c in euclid:
        assert c["role"] == ("KICK" if not c["is_rest"] else None)


def test_kick_pattern_for_style_two_step_hits_downbeat_and_and_of_two():
    # 8 quarter-note cells = two 2-beat "two-step" cycles. This project's
    # documented interpretation hits beat offset 0.0 and 1.5 in each
    # 2-beat cycle -- i.e. cell indices 0, 3, 4, 7 on a steady quarter grid
    # (0.0, 1.5, 2.0, 3.5 beats -> cell indices 0, 3, 4, 7).
    guitar_cells = [{"duration": 0.5, "is_rest": False} for _ in range(8)]
    two_step = kick_pattern_for_style(guitar_cells, "two_step")
    hit_positions = [i for i, c in enumerate(two_step) if not c["is_rest"]]
    assert hit_positions == [0, 3, 4, 7]


def test_kick_pattern_for_style_two_step_is_independent_of_guitar_rests():
    # Per this project's documented interpretation, two_step is a fixed
    # metric overlay (like blast), not a copy of the guitar's own hit/rest
    # layout -- an all-rest guitar part still gets the same kick pattern.
    all_rest_cells = [{"duration": 0.5, "is_rest": True} for _ in range(8)]
    all_hit_cells = [{"duration": 0.5, "is_rest": False} for _ in range(8)]
    assert kick_pattern_for_style(all_rest_cells, "two_step") == kick_pattern_for_style(
        all_hit_cells, "two_step"
    )


def test_kick_pattern_for_style_blast_hits_every_cell_regardless_of_rests():
    rng = random.Random(4)
    guitar_cells = generate_rhythm(4.0, [0.5], hit_chance=0.2, rng=rng)
    assert any(c["is_rest"] for c in guitar_cells), "fixture should include guitar rests"
    blast = kick_pattern_for_style(guitar_cells, "blast")
    assert all(not c["is_rest"] and c["role"] == "KICK" for c in blast)
    assert len(blast) == len(guitar_cells)


@pytest.mark.parametrize("preset_id", sorted(load_all_presets().keys()))
def test_kick_pattern_for_style_handles_every_real_preset_kick_style(preset_id):
    """Closes the actual gap this task targets: every REAL preset's `.kick`
    string must resolve through the dispatcher, never raise."""
    preset = load_all_presets()[preset_id]
    rng = random.Random(5)
    guitar_cells = generate_rhythm(8.0, [0.25, 0.5, 1.0], hit_chance=0.5, rng=rng)
    result = kick_pattern_for_style(guitar_cells, preset.kick, rng=random.Random(1))
    assert len(result) == len(guitar_cells)
    for cell in result:
        assert cell["role"] in ("KICK", None)
        assert cell["is_rest"] == (cell["role"] is None)
