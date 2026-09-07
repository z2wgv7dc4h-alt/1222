import json
import random

from rhythm import generate_rhythm, pick_blast_type, tile_cell


def _run_pipeline(seed: int) -> str:
    """A nontrivial multi-step generation pipeline, all fed from ONE
    `random.Random(seed)` instance -- never the global `random` module --
    so that running it twice with the same seed must be byte-for-byte
    identical, and two different seeds should (almost certainly) diverge."""
    rng = random.Random(seed)
    cell = generate_rhythm(7.0, [0.5, 1.0, 1.5], hit_chance=0.65, rng=rng)
    tiled = tile_cell(cell, 16.0)
    blast_weights = {"traditional": 3, "gravity": 2, "hammer": 1}
    blasts = [pick_blast_type(blast_weights, rng) for _ in range(10)]
    return json.dumps({"cell": cell, "tiled": tiled, "blasts": blasts}, sort_keys=True)


def test_same_seed_produces_byte_identical_output():
    seed = 12345
    first = _run_pipeline(seed)
    second = _run_pipeline(seed)
    assert first == second


def test_different_seeds_overwhelmingly_likely_to_diverge():
    # Sanity check only, not load-bearing: pick several seed pairs so a
    # single unlucky collision can't make this flaky.
    results = {seed: _run_pipeline(seed) for seed in range(20)}
    unique_outputs = set(results.values())
    assert len(unique_outputs) > 1
