import json
from pathlib import Path

import pytest

from presets import (
    PRESETS_DIR,
    TUNINGS_PATH,
    blend_presets,
    get_tuning,
    load_all_presets,
    load_preset,
    load_tunings,
    resolve_preset_id,
    validate_preset,
)

BASE_VALID_PRESET = {
    "id": "bogus",
    "description": "a valid base preset for mutation in tests",
    "tuning_key": "drop_g_7",
    "scale": "minor",
    "dissonance": 0.5,
    "bpm": 140,
    "bars": 4,
    "feel": "bounce",
    "open_chance": 0.5,
    "octave_stab": True,
    "kick": "bounce",
    "vocab": {"weights": {"0": 10, "7": 4}, "motion": 0.2},
}

EXPECTED_TUNINGS = {
    "drop_b_7": (["B", "F#", "B", "E", "G#", "C#", "F#"], [35, 42, 47, 52, 56, 61, 66]),
    "drop_g_7": (["G", "D", "G", "C", "F", "A", "D"], [31, 38, 43, 48, 53, 57, 62]),
    "drop_ab_7": (["Ab", "Eb", "Ab", "Db", "Gb", "Bb", "Eb"], [32, 39, 44, 49, 54, 58, 63]),
    "drop_a_7": (["A", "E", "A", "D", "F#", "B", "E"], [33, 40, 45, 50, 54, 59, 64]),
    "drop_e_8": (["E", "B", "E", "A", "D", "G", "B", "E"], [28, 35, 40, 45, 50, 55, 59, 64]),
    "drop_c_6": (["C", "G", "C", "F", "A", "D"], [36, 43, 48, 53, 57, 62]),
    "standard_6": (["E", "A", "D", "G", "B", "E"], [40, 45, 50, 55, 59, 64]),
}

EXPECTED_PRESET_IDS = {"groovy", "djent", "chill", "tech", "melodic", "metalcore", "deathcore", "progressive"}


# -- P1.6: tunings -----------------------------------------------------------

def test_all_seven_tunings_load_with_exact_values():
    tunings = load_tunings()
    assert set(tunings) == set(EXPECTED_TUNINGS)
    for key, (names, open_notes) in EXPECTED_TUNINGS.items():
        assert tunings[key].names == names
        assert tunings[key].open == open_notes


def test_get_tuning_returns_known_tuning():
    tuning = get_tuning("drop_g_7")
    assert tuning.open == [31, 38, 43, 48, 53, 57, 62]


def test_get_tuning_rejects_unknown_key():
    with pytest.raises(ValueError):
        get_tuning("not_a_real_tuning")


# -- P1.7: preset ids ---------------------------------------------------------

def test_preset_ids_are_moods_not_band_names():
    presets = load_all_presets()
    assert set(presets) == EXPECTED_PRESET_IDS
    band_words = ("osiris", "infant", "annihilator", "periphery", "veil", "signs of the swarm")
    for preset in presets.values():
        assert preset.id.lower() not in band_words
        # band names may appear only in free-text description, never the id
        assert all(word not in preset.id.lower() for word in band_words)


def test_every_preset_tuning_key_and_scale_resolve():
    tunings = load_tunings()
    presets = load_all_presets()
    for preset in presets.values():
        assert preset.tuning_key in tunings
        assert 0.0 <= preset.dissonance <= 1.0


# -- P1.8: schema validator wired into the loader ----------------------------

def test_load_preset_rejects_missing_field(tmp_path):
    tunings = load_tunings()
    bad = {
        "id": "bogus",
        "description": "missing dissonance",
        "tuning_key": "drop_g_7",
        "scale": "minor",
    }
    path = tmp_path / "bogus.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_preset(path, tunings)


def test_load_preset_rejects_unknown_tuning_key(tmp_path):
    tunings = load_tunings()
    bad = {
        "id": "bogus",
        "description": "bad tuning key",
        "tuning_key": "drop_zzz_99",
        "scale": "minor",
        "dissonance": 0.5,
    }
    path = tmp_path / "bogus.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_preset(path, tunings)


def test_load_preset_rejects_unknown_scale(tmp_path):
    tunings = load_tunings()
    bad = {
        "id": "bogus",
        "description": "bad scale",
        "tuning_key": "drop_g_7",
        "scale": "not-a-real-scale",
        "dissonance": 0.5,
    }
    path = tmp_path / "bogus.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_preset(path, tunings)


def test_load_preset_rejects_dissonance_out_of_range(tmp_path):
    tunings = load_tunings()
    bad = {
        "id": "bogus",
        "description": "dissonance out of range",
        "tuning_key": "drop_g_7",
        "scale": "minor",
        "dissonance": 1.5,
    }
    path = tmp_path / "bogus.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_preset(path, tunings)


def test_load_preset_rejects_id_mismatch_with_filename(tmp_path):
    tunings = load_tunings()
    bad = {
        "id": "not_the_filename",
        "description": "id/filename mismatch",
        "tuning_key": "drop_g_7",
        "scale": "minor",
        "dissonance": 0.5,
    }
    path = tmp_path / "groovy.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_preset(path, tunings)


def test_validate_preset_standalone_also_rejects_bad_data():
    tunings = load_tunings()
    with pytest.raises(ValueError):
        validate_preset({"id": "x"}, tunings)


def test_load_preset_rejects_bad_vocab_interval(tmp_path):
    tunings = load_tunings()
    bad = dict(BASE_VALID_PRESET, vocab={"weights": {"15": 5}, "motion": 0.2})
    path = tmp_path / "bogus.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_preset(path, tunings)


def test_load_preset_rejects_negative_vocab_weight(tmp_path):
    tunings = load_tunings()
    bad = dict(BASE_VALID_PRESET, vocab={"weights": {"0": -1}, "motion": 0.2})
    path = tmp_path / "bogus.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_preset(path, tunings)


def test_load_preset_rejects_bpm_out_of_range(tmp_path):
    tunings = load_tunings()
    bad = dict(BASE_VALID_PRESET, bpm=0)
    path = tmp_path / "bogus.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_preset(path, tunings)


def test_load_preset_accepts_valid_full_preset(tmp_path):
    tunings = load_tunings()
    path = tmp_path / "bogus.json"
    path.write_text(json.dumps(BASE_VALID_PRESET))
    preset = load_preset(path, tunings)
    assert preset.bpm == 140
    assert preset.vocab.weights == {0: 10, 7: 4}
    assert preset.group is None
    assert preset.pedal is None


# -- preset id aliases: old band-linked ids resolve, never a second preset --

def test_resolve_preset_id_maps_old_band_ids():
    # "periphery" now points at the real Periphery-styled preset
    # ("progressive", added once X.6d's lydian scale had a real reason to
    # be adopted) rather than "chill", its original stand-in proxy.
    assert resolve_preset_id("periphery") == "progressive"
    assert resolve_preset_id("psycho") == "tech"
    assert resolve_preset_id("boo") == "djent"


def test_resolve_preset_id_passes_through_real_ids():
    for real_id in EXPECTED_PRESET_IDS:
        assert resolve_preset_id(real_id) == real_id


def test_resolve_preset_id_aliases_never_shadow_a_real_preset_file():
    # every alias target must be a real, loadable preset id
    from presets import ALIASES
    real_ids = set(load_all_presets())
    for target in ALIASES.values():
        assert target in real_ids


# -- P1.9: glob discovery, never a hardcoded filename list -------------------

def test_all_preset_json_files_load_via_glob():
    json_files = sorted(Path(PRESETS_DIR).glob("*.json"))
    assert json_files, "no JSON files found under engine/presets"

    tunings = load_tunings()
    loaded_ids = set()
    saw_tunings_file = False
    for file_path in json_files:
        if file_path.name == "tunings.json":
            # the tunings table has its own shape/loader -- also exercised
            # directly below, but every discovered file must load somehow.
            saw_tunings_file = True
            reloaded = load_tunings(file_path)
            assert reloaded == tunings
            continue
        preset = load_preset(file_path, tunings)
        loaded_ids.add(preset.id)

    assert saw_tunings_file
    assert loaded_ids == EXPECTED_PRESET_IDS


def test_tunings_file_discovered_by_glob_loads():
    tuning_files = [p for p in Path(PRESETS_DIR).glob("*.json") if p.name == "tunings.json"]
    assert tuning_files == [TUNINGS_PATH]
    assert load_tunings(tuning_files[0])


# ---------------------------------------------------------------------------
# P9.2/P9.3 -- real preset character blending
# ---------------------------------------------------------------------------


def test_blend_presets_t0_and_t1_are_exact_endpoints():
    presets = load_all_presets()
    a, b = presets["djent"], presets["deathcore"]
    at_zero = blend_presets(a, b, 0.0)
    assert at_zero.dissonance == pytest.approx(a.dissonance)
    assert at_zero.vocab.motion == pytest.approx(a.vocab.motion)
    at_one = blend_presets(a, b, 1.0)
    assert at_one.dissonance == pytest.approx(b.dissonance)
    assert at_one.vocab.motion == pytest.approx(b.vocab.motion)


def test_blend_presets_midpoint_is_real_average():
    presets = load_all_presets()
    a, b = presets["djent"], presets["deathcore"]
    mid = blend_presets(a, b, 0.5)
    assert mid.dissonance == pytest.approx((a.dissonance + b.dissonance) / 2)
    for key in set(a.vocab.weights) | set(b.vocab.weights):
        expected = (a.vocab.weights.get(key, 0) + b.vocab.weights.get(key, 0)) / 2
        assert mid.vocab.weights[key] == pytest.approx(expected)


def test_blend_presets_structural_fields_come_from_preset_a():
    presets = load_all_presets()
    a, b = presets["djent"], presets["chill"]
    blended = blend_presets(a, b, 0.7)
    assert blended.tuning_key == a.tuning_key
    assert blended.scale == a.scale
    assert blended.bpm == a.bpm
    assert blended.bars == a.bars
    assert blended.feel == a.feel
    assert blended.kick == a.kick
    assert blended.group == a.group
    assert blended.id == a.id


def test_blend_presets_none_pedal_treated_as_zero():
    presets = load_all_presets()
    a = presets["djent"]  # real pedal declared
    b = presets["metalcore"]  # pedal is None
    assert a.pedal is not None and b.pedal is None
    blended = blend_presets(a, b, 1.0)
    assert blended.pedal == pytest.approx(0.0)


def test_blend_presets_rejects_out_of_range_t():
    presets = load_all_presets()
    a, b = presets["djent"], presets["metalcore"]
    with pytest.raises(ValueError):
        blend_presets(a, b, -0.1)
    with pytest.raises(ValueError):
        blend_presets(a, b, 1.1)


def test_blend_presets_output_is_usable_by_the_real_generation_pipeline():
    from song import _generate_attempt
    import random

    presets = load_all_presets()
    blended = blend_presets(presets["djent"], presets["deathcore"], 0.4)
    song = _generate_attempt(random.Random(3), blended, num_sections=4)
    assert song["sections"]
    assert song["judge"]["hits"] > 0
