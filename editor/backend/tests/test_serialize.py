import json

from app.serialize import summarize_preset, summarize_song, summarize_tab
from fretboard import Fretboard
from presets import get_tuning, load_all_presets, load_tunings
from song import compose_song


def test_summarize_preset_is_json_safe_and_matches_real_fields():
    presets = load_all_presets()
    preset = presets["metalcore"]
    summary = summarize_preset("metalcore", preset)
    assert summary["id"] == "metalcore"
    assert summary["bpm"] == preset.bpm
    assert summary["feel"] == preset.feel
    json.dumps(summary)  # real JSON-serializability check, not assumed


def test_summarize_song_matches_real_compose_song_output():
    presets = load_all_presets()
    preset = presets["djent"]
    song = compose_song("djent", seed=3, num_sections=6)

    summary = summarize_song(song, preset)
    json.dumps(summary)  # every field must be real JSON-safe data

    assert summary["preset_id"] == "djent"
    assert summary["sequence"] == song["sequence"]
    assert len(summary["sections"]) == len(song["sections"])
    for real_section, summarized in zip(song["sections"], summary["sections"]):
        assert summarized["role"] == real_section["role"]
        assert summarized["bars"] == preset.bars
        assert summarized["lead_mode"] == real_section["lead_mode"]
        real_hits = sum(1 for c in real_section["guitar_take_a"] if not c["is_rest"])
        assert summarized["guitar_hits"] == real_hits


def test_summarize_song_includes_real_judge_result():
    presets = load_all_presets()
    preset = presets["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=4)
    summary = summarize_song(song, preset)
    assert summary["judge"] == song["judge"]


def _guitar_fb(preset):
    tunings = load_tunings()
    tuning = get_tuning(preset.tuning_key, tunings)
    return Fretboard(tuning.open)


def test_summarize_tab_is_json_safe_and_cell_aligned():
    presets = load_all_presets()
    preset = presets["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=4)
    section = song["sections"][0]
    guitar_fb = _guitar_fb(preset)

    tab = summarize_tab(section, guitar_fb)
    json.dumps(tab)
    assert len(tab) == len(section["guitar_take_a"])
    for cell, entry in zip(section["guitar_take_a"], tab):
        assert entry["is_rest"] == cell["is_rest"]
        assert entry["duration"] == cell["duration"]


def test_summarize_tab_produces_real_playable_positions():
    presets = load_all_presets()
    preset = presets["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=4)
    guitar_fb = _guitar_fb(preset)

    for section in song["sections"]:
        tab = summarize_tab(section, guitar_fb)
        for entry in tab:
            if entry["is_rest"]:
                assert entry["string"] is None
                assert entry["fret"] is None
                continue
            # A real, reachable (string, fret) -- exactly what
            # guitar_fb.fret_to_midi would produce for this position.
            assert 0 <= entry["string"] < len(guitar_fb.tuning)
            assert 0 <= entry["fret"] <= guitar_fb.max_fret
