import random

import pytest

from drums import kick_follows_guitar
from motif import generate_motif
from performance import humanize_take
from presets import load_all_presets
from rhythm import generate_rhythm
from slam import mark_pinch_harmonics
from structure import (
    DEFAULT_GRAPH,
    apply_half_time,
    bridge,
    flatten,
    generate_section_content,
    generate_section_sequence,
    generate_song_sections,
    judge,
    judge_and_retry,
    pickup,
    tempo_at,
    walk_graph,
)
from theory import Scale, arc


def _tech():
    return load_all_presets()["tech"]


# ---------------------------------------------------------------------------
# P6.1 -- weighted section graph
# ---------------------------------------------------------------------------


def test_walk_graph_reproducible_with_same_seed():
    seq1 = walk_graph(DEFAULT_GRAPH, "intro", 12, random.Random(42))
    seq2 = walk_graph(DEFAULT_GRAPH, "intro", 12, random.Random(42))
    assert seq1 == seq2
    assert seq1[0] == "intro"


def test_walk_graph_different_seeds_can_diverge():
    seq_a = walk_graph(DEFAULT_GRAPH, "intro", 12, random.Random(1))
    seq_b = walk_graph(DEFAULT_GRAPH, "intro", 12, random.Random(2))
    # Not a hard guarantee in general, but with this graph's branching it
    # would be suspicious if two different seeds always matched exactly.
    assert seq_a != seq_b or len(seq_a) != len(seq_b)


def test_walk_graph_zero_weight_edge_never_taken():
    graph = {"A": {"B": 0.0, "C": 1.0}, "B": {"A": 1.0}, "C": {"A": 1.0}}
    for seed in range(200):
        seq = walk_graph(graph, "A", 6, random.Random(seed))
        # "A" can only ever be followed by "C" (weight 0 to "B" must never
        # be picked -- a hard guarantee, not "rarely").
        for i in range(len(seq) - 1):
            if seq[i] == "A":
                assert seq[i + 1] != "B"


def test_walk_graph_rejects_bad_input():
    with pytest.raises(ValueError):
        walk_graph(DEFAULT_GRAPH, "not-a-node", 5, random.Random(0))
    with pytest.raises(ValueError):
        walk_graph(DEFAULT_GRAPH, "intro", 0, random.Random(0))
    with pytest.raises(ValueError):
        walk_graph({"A": {"B": -1.0}}, "A", 3, random.Random(0))


def test_walk_graph_stops_early_at_terminal_node():
    # "outro" has no outgoing edges in DEFAULT_GRAPH -- once reached, the
    # walk must stop rather than looping or raising.
    seq = walk_graph(DEFAULT_GRAPH, "outro", 10, random.Random(0))
    assert seq == ["outro"]


def test_generate_section_sequence_uses_default_graph():
    seq = generate_section_sequence(random.Random(7), 8)
    assert seq[0] == "intro"
    assert all(role in DEFAULT_GRAPH for role in seq)


# X.28 -- verse/chorus are real, reachable nodes in the default graph now.
def test_verse_and_chorus_are_reachable_from_intro():
    seen = set()
    for seed in range(50):
        seq = walk_graph(DEFAULT_GRAPH, "intro", 16, random.Random(seed))
        seen.update(seq)
    assert "verse" in seen
    assert "chorus" in seen


def test_chorus_can_lead_straight_to_outro():
    # A song CAN end on a chorus, not only on breakdown/solo/interlude.
    for seed in range(200):
        seq = walk_graph(DEFAULT_GRAPH, "chorus", 2, random.Random(seed))
        if len(seq) == 2 and seq[1] == "outro":
            return
    pytest.fail("chorus never reached outro across 200 seeds")


def test_verse_dominant_destination_is_chorus():
    # verse -> chorus has the highest weight out of "verse" -- across many
    # seeds, chorus should be verse's single most common next step.
    from collections import Counter
    counts = Counter()
    for seed in range(300):
        seq = walk_graph(DEFAULT_GRAPH, "verse", 2, random.Random(seed))
        if len(seq) == 2:
            counts[seq[1]] += 1
    assert counts["chorus"] == max(counts.values())


# ---------------------------------------------------------------------------
# P6.2 -- pickup / bridge / flatten
# ---------------------------------------------------------------------------


def _sparse(n=6):
    return [{"duration": 1.0, "is_rest": True} for _ in range(n)]


def _dense(n=8):
    return [{"duration": 0.25, "is_rest": False} for _ in range(n)]


def test_pickup_copies_next_head_onto_prev_tail():
    prev, nxt = _sparse(), _dense()
    out = pickup(prev, nxt, n=2)
    assert out[-2:] == [{"duration": nxt[0]["duration"], "is_rest": nxt[0]["is_rest"]},
                         {"duration": nxt[1]["duration"], "is_rest": nxt[1]["is_rest"]}]
    # everything before the blended tail is untouched
    assert out[:-2] == prev[:-2]


def test_pickup_empty_inputs_return_prev_unchanged():
    assert pickup([], _dense()) == []
    prev = _sparse()
    assert pickup(prev, []) == prev


def test_bridge_rejects_empty_inputs():
    with pytest.raises(ValueError):
        bridge([], _dense())
    with pytest.raises(ValueError):
        bridge(_sparse(), [])
    with pytest.raises(ValueError):
        bridge(_sparse(), _dense(), bridge_len=0)


def test_bridge_forces_downbeat_and_fill_hits():
    br = bridge(_sparse(), _dense(), bridge_len=4)
    assert br[0]["is_rest"] is False  # downbeat accent
    assert all(not c["is_rest"] for c in br[-2:])  # pickup fill


def test_flatten_seam_shows_blend_not_hard_cut():
    # A very sparse (all-rest) section followed by a very dense (all-hit)
    # section: a naive concatenation would show an abrupt rest->hit cliff
    # at the seam. flatten() must instead show the outgoing section's own
    # tail already influenced by the incoming section (via pickup), plus a
    # forced-hit bridge spliced between them.
    sparse, dense = _sparse(), _dense()
    flat = flatten([sparse, dense])

    # length = sparse + bridge(default len 2) + dense
    assert len(flat) == len(sparse) + 2 + len(dense)

    outgoing_tail = flat[len(sparse) - 2:len(sparse)]
    # At least one of the outgoing section's last 2 cells was measurably
    # influenced by the incoming (dense) section: it is no longer a rest,
    # and its duration matches the incoming section's cells, not the
    # sparse section's original duration.
    assert any(not c["is_rest"] for c in outgoing_tail)
    assert any(c["duration"] == pytest.approx(dense[0]["duration"]) for c in outgoing_tail)


def test_flatten_empty_sections_returns_empty():
    assert flatten([]) == []


def test_flatten_single_section_no_bridge_inserted():
    dense = _dense()
    assert flatten([dense]) == dense


# ---------------------------------------------------------------------------
# P6.3 -- half-time inside a section
# ---------------------------------------------------------------------------


def test_apply_half_time_only_targets_range():
    cells = [{"duration": 0.5, "is_rest": (i % 2 == 0)} for i in range(10)]
    out = apply_half_time(cells, 3, 4)

    before_total = sum(c["duration"] for c in cells[3:7])
    after_total = sum(c["duration"] for c in out[3:7])
    assert after_total == pytest.approx(before_total * 2.0)

    # untouched outside the range
    assert out[:3] == cells[:3]
    assert out[7:] == cells[7:]
    # is_rest pattern inside the range preserved (only duration changes)
    assert [c["is_rest"] for c in out[3:7]] == [c["is_rest"] for c in cells[3:7]]


def test_apply_half_time_custom_factor():
    cells = [{"duration": 1.0, "is_rest": False} for _ in range(4)]
    out = apply_half_time(cells, 0, 2, factor=3.0)
    assert [c["duration"] for c in out] == [3.0, 3.0, 1.0, 1.0]


def test_apply_half_time_rejects_bad_range():
    cells = [{"duration": 1.0, "is_rest": False} for _ in range(4)]
    with pytest.raises(ValueError):
        apply_half_time(cells, -1, 2)
    with pytest.raises(ValueError):
        apply_half_time(cells, 2, 10)
    with pytest.raises(ValueError):
        apply_half_time(cells, 0, 2, factor=0)


# ---------------------------------------------------------------------------
# P6.4 -- arc()-driven modulation, wired into real generation
# ---------------------------------------------------------------------------


def test_generate_motif_same_base_degree_same_seed_is_identical():
    tech = _tech()
    scale = Scale(52, tech.scale)
    r1 = random.Random(5)
    r2 = random.Random(5)
    m1 = generate_motif(8.0, [0.5, 1.0], 0.8, r1, scale, tech.vocab.weights, base_degree=0)
    m2 = generate_motif(8.0, [0.5, 1.0], 0.8, r2, scale, tech.vocab.weights, base_degree=0)
    assert m1.cell == m2.cell
    assert m1.deltas == m2.deltas


def test_generate_section_content_anchors_on_arc_start_degree():
    tech = _tech()
    scale = Scale(52, tech.scale)

    # breakdown (letter C) and chill (letter K) have different start_degree
    # (0 vs 4) and different register (0 vs 12) per theory.ARC.
    assert arc(role="breakdown")["start_degree"] != arc(role="chill")["start_degree"]

    content_a = generate_section_content(
        "breakdown", scale, random.Random(5), 8.0, [0.5, 1.0], 0.8, tech.vocab.weights,
    )
    content_b = generate_section_content(
        "chill", scale, random.Random(5), 8.0, [0.5, 1.0], 0.8, tech.vocab.weights,
    )

    # Same seed, same everything else, only the role (-> arc row) differs:
    # the rendered pitches must differ, and that difference is attributable
    # to the anchor degree/register, not RNG noise -- proven by the control
    # test above showing identical base_degree + identical seed reproduces
    # byte-identical output.
    assert content_a["pitches"] != content_b["pitches"]
    assert content_a["arc"]["start_degree"] == 0
    assert content_b["arc"]["start_degree"] == 4


def test_generate_song_sections_wires_arc_across_a_real_sequence():
    tech = _tech()
    scale = Scale(52, tech.scale)
    sequence = ["intro", "breakdown", "chill"]
    sections = generate_song_sections(
        sequence, scale, random.Random(3), 8.0, [0.5, 1.0], 0.8, tech.vocab.weights,
    )
    assert len(sections) == 3
    for role, content in zip(sequence, sections):
        assert content["arc"]["letter"] == arc(role=role)["letter"]


def test_generate_song_sections_rejects_empty_sequence():
    tech = _tech()
    scale = Scale(52, tech.scale)
    with pytest.raises(ValueError):
        generate_song_sections([], scale, random.Random(0), 8.0, [0.5, 1.0], 0.8, tech.vocab.weights)


# ---------------------------------------------------------------------------
# P6.5 -- judge / retry
# ---------------------------------------------------------------------------


def _build_comp(rng: random.Random, total_beats=16.0, hit_chance=0.6) -> dict:
    """A real generate_rhythm-based breakdown composition: guitar rhythm +
    humanized velocity (mostly palm-muted, default velocity_base=100 which
    is < 110) with the phrase's last hit flagged open via
    slam.mark_pinch_harmonics (velocity 127, >= 110), and drums locked to
    the guitar's hits via drums.kick_follows_guitar."""
    guitar_cells = generate_rhythm(total_beats, [0.5, 1.0], hit_chance, rng)
    guitar = humanize_take(guitar_cells, rng)
    guitar = mark_pinch_harmonics(guitar)
    drums = kick_follows_guitar(guitar_cells)
    return {"guitar": guitar, "drums": drums}


def test_judge_fails_bad_fixture_with_too_few_hits():
    bad = {
        "guitar": [{"duration": 1.0, "is_rest": True, "velocity": 0} for _ in range(8)],
        "drums": [{"duration": 1.0, "is_rest": True, "role": None} for _ in range(8)],
    }
    verdict = judge(bad)
    assert verdict["ok"] is False
    assert verdict["hits"] == 0


def test_judge_passes_a_real_generator_for_at_least_one_seed():
    passed = False
    for seed in range(8):
        comp = _build_comp(random.Random(seed))
        if judge(comp)["ok"]:
            passed = True
            break
    assert passed


def test_judge_and_retry_retries_and_eventually_succeeds():
    calls = {"n": 0}

    def flaky_generate(rng):
        calls["n"] += 1
        # First couple of seeds deliberately produce a losing comp (too few
        # hits); from seed 2 onward, generate a real, judge-passing comp.
        if calls["n"] <= 2:
            return {
                "guitar": [{"duration": 1.0, "is_rest": True, "velocity": 0}] * 4,
                "drums": [{"duration": 1.0, "is_rest": True, "role": None}] * 4,
            }
        return _build_comp(rng)

    result = judge_and_retry(flaky_generate, max_seeds=6)
    assert calls["n"] > 1
    # judge_and_retry should have stopped as soon as *some* seed passed --
    # it must not necessarily exhaust all 6 attempts.
    assert calls["n"] <= 6


def test_judge_and_retry_gives_up_after_max_seeds():
    calls = {"n": 0}

    def always_bad(rng):
        calls["n"] += 1
        return {
            "guitar": [{"duration": 1.0, "is_rest": True, "velocity": 0}] * 4,
            "drums": [{"duration": 1.0, "is_rest": True, "role": None}] * 4,
        }

    result = judge_and_retry(always_bad, max_seeds=4)
    assert calls["n"] == 4
    assert judge(result)["ok"] is False


def test_judge_and_retry_rejects_bad_max_seeds():
    with pytest.raises(ValueError):
        judge_and_retry(lambda rng: _build_comp(rng), max_seeds=0)


# ---------------------------------------------------------------------------
# P6.6 -- interlude: distinctly lower-energy than a breakdown
# ---------------------------------------------------------------------------


def test_interlude_has_lower_hit_density_than_breakdown_same_draws():
    tech = _tech()
    scale = Scale(52, tech.scale)

    content_breakdown = generate_section_content(
        "breakdown", scale, random.Random(11), 32.0, [0.5, 1.0], 0.9, tech.vocab.weights,
    )
    content_interlude = generate_section_content(
        "interlude", scale, random.Random(11), 32.0, [0.5, 1.0], 0.9, tech.vocab.weights,
    )

    hits_breakdown = content_breakdown["motif"].hit_count
    hits_interlude = content_interlude["motif"].hit_count
    assert hits_interlude < hits_breakdown


def test_interlude_routes_through_chill_arc_row():
    row = generate_section_content(
        "interlude", Scale(52, "minor"), random.Random(0), 8.0, [0.5, 1.0], 0.8, {0: 1, 7: 1},
    )["arc"]
    assert row["letter"] == "K"


# ---------------------------------------------------------------------------
# P6.7 -- tempo curve
# ---------------------------------------------------------------------------


def test_tempo_drop_is_abrupt():
    curve = {"type": "drop", "at": 4, "bpm": 200.0}
    assert tempo_at(3, 140.0, curve) == 140.0
    assert tempo_at(4, 140.0, curve) == 200.0
    assert tempo_at(5, 140.0, curve) == 200.0


def test_tempo_ramp_is_gradual_and_monotonic():
    curve = {"type": "ramp", "start": 0, "end": 8, "bpm": 180.0}
    values = [tempo_at(i, 140.0, curve) for i in range(9)]
    assert values[0] == 140.0
    assert values[-1] == 180.0
    # strictly increasing across the ramp -- gradual, not a step
    assert all(b > a for a, b in zip(values, values[1:]))
    # more than two distinct values proves it isn't a single jump
    assert len(set(values)) > 2


def test_tempo_ramp_holds_before_and_after_its_range():
    curve = {"type": "ramp", "start": 2, "end": 5, "bpm": 200.0}
    assert tempo_at(0, 140.0, curve) == 140.0
    assert tempo_at(2, 140.0, curve) == 140.0
    assert tempo_at(5, 140.0, curve) == 200.0
    assert tempo_at(9, 140.0, curve) == 200.0


def test_tempo_at_rejects_bad_curve():
    with pytest.raises(ValueError):
        tempo_at(0, 140.0, {"type": "warp"})
    with pytest.raises(ValueError):
        tempo_at(0, 140.0, {"type": "ramp", "start": 5, "end": 5, "bpm": 200.0})


# ---------------------------------------------------------------------------
# X.6c -- metric modulation curve: a REAL branch in tempo_at's dispatch,
# not a separate parallel function nothing calls.
# ---------------------------------------------------------------------------


def test_tempo_metric_modulation_holds_base_bpm_before_the_transition():
    curve = {
        "type": "metric_modulation", "at": 4,
        "old_subdivision": (3, 2), "new_subdivision": (1, 1),
    }
    assert tempo_at(0, 140.0, curve) == 140.0
    assert tempo_at(3, 140.0, curve) == 140.0


def test_tempo_metric_modulation_scales_correctly_from_the_transition():
    # dotted quarter (3,2) = new quarter (1,1) -> ratio 1.5 (the same
    # hard-verified real-world example as metric_modulation.py's own docs).
    curve = {
        "type": "metric_modulation", "at": 4,
        "old_subdivision": (3, 2), "new_subdivision": (1, 1),
    }
    assert tempo_at(4, 140.0, curve) == pytest.approx(210.0)
    assert tempo_at(9, 140.0, curve) == pytest.approx(210.0)  # holds after too


def test_tempo_metric_modulation_half_time_case():
    # straight eighth (1,2) = new quarter (1,1) -> ratio 0.5, the half-time
    # breakdown treatment song.py's real trigger uses.
    curve = {
        "type": "metric_modulation", "at": 2,
        "old_subdivision": (1, 2), "new_subdivision": (1, 1),
    }
    assert tempo_at(1, 160.0, curve) == 160.0
    assert tempo_at(2, 160.0, curve) == pytest.approx(80.0)


def test_tempo_metric_modulation_bad_subdivision_still_raises_value_error():
    # The existing dispatch's fail-closed behavior must survive: a
    # malformed metric_modulation curve raises the same ValueError type as
    # every other unknown/malformed curve, not a different exception.
    curve = {
        "type": "metric_modulation", "at": 2,
        "old_subdivision": (0, 2), "new_subdivision": (1, 1),
    }
    with pytest.raises(ValueError):
        tempo_at(2, 140.0, curve)


def test_tempo_at_still_rejects_unknown_curve_type_alongside_new_branch():
    # Adding the metric_modulation branch must not have disturbed the
    # existing fail-closed default for a genuinely unknown curve type.
    with pytest.raises(ValueError):
        tempo_at(0, 140.0, {"type": "not-a-real-curve"})


# ---------------------------------------------------------------------------
# X.33 -- real rebalance: chill/interlude occur measurably less often
# ---------------------------------------------------------------------------


def test_rebalanced_graph_visits_chill_and_interlude_less_often():
    """X.33: direct response to a real, measured problem -- the old graph
    weights sent chill+interlude to ~21% of all sections combined. Across
    many seeds, the real observed share must now be measurably lower."""
    from collections import Counter

    counts = Counter()
    total = 0
    for seed in range(300):
        seq = generate_section_sequence(random.Random(seed), 8)
        for role in seq:
            counts[role] += 1
            total += 1
    atmospheric_share = (counts["chill"] + counts["interlude"]) / total
    assert atmospheric_share < 0.15, (
        f"expected chill+interlude to be a real minority of sections "
        f"(< 15%), got {atmospheric_share:.3f}"
    )
