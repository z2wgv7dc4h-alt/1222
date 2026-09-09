from types import SimpleNamespace

from app.edits import apply_edits
from presets import load_all_presets
from song import compose_song


def _edit(**kwargs):
    defaults = dict(section_position=0, mode="full", role=None, hit_chance_bias=0.0, regen_seed=0)
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_apply_edits_empty_list_returns_song_unchanged():
    song = compose_song("metalcore", seed=1, num_sections=6)
    preset = load_all_presets()["metalcore"]
    result = apply_edits(song, [], preset)
    assert result is song


def test_apply_edits_applies_one_real_regen():
    song = compose_song("metalcore", seed=1, num_sections=6)
    preset = load_all_presets()["metalcore"]
    original_cell = list(song["sections"][2]["motif"].cell)

    result = apply_edits(song, [_edit(section_position=2, mode="full", regen_seed=42)], preset)
    assert len(result["sections"]) == len(song["sections"])
    edited = result["sections"][2]
    assert len(edited["kick"]) == len(edited["guitar_take_a"])
    # The original song object must be untouched (regenerate_section's own
    # no-mutation guarantee, exercised end-to-end through this real path).
    assert song["sections"][2]["motif"].cell == original_cell


def test_apply_edits_applies_multiple_edits_in_order():
    song = compose_song("metalcore", seed=1, num_sections=6)
    preset = load_all_presets()["metalcore"]

    result = apply_edits(
        song,
        [_edit(section_position=1, regen_seed=1), _edit(section_position=3, regen_seed=2, mode="rhythm")],
        preset,
    )
    assert len(result["sections"]) == len(song["sections"])
    for section in result["sections"]:
        # Real invariant preserved across every real edit.
        assert len(section["kick"]) == len(section["guitar_take_a"])


def test_apply_edits_is_reproducible():
    song = compose_song("metalcore", seed=1, num_sections=6)
    preset = load_all_presets()["metalcore"]
    edits = [_edit(section_position=2, regen_seed=7)]
    a = apply_edits(song, edits, preset)
    b = apply_edits(song, edits, preset)
    assert a["sections"][2]["motif"].deltas == b["sections"][2]["motif"].deltas
