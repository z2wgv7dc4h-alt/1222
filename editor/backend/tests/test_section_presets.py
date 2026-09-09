import pytest

from app import section_presets


@pytest.fixture(autouse=True)
def _isolated_data_file(tmp_path, monkeypatch):
    """Real file-backed persistence, but pointed at a throwaway path per
    test so tests never touch (or depend on) the real local data file."""
    monkeypatch.setattr(section_presets, "_DATA_PATH", tmp_path / "section_presets.json")


def test_list_is_empty_before_anything_saved():
    assert section_presets.list_section_presets() == {}


def test_save_then_list_round_trips_the_real_edit():
    edit = {"mode": "full", "role": "breakdown", "hit_chance_bias": 0.2, "regen_seed": 42}
    section_presets.save_section_preset("heavy breakdown", edit)
    assert section_presets.list_section_presets() == {"heavy breakdown": edit}


def test_save_persists_across_a_fresh_read_from_disk():
    edit = {"mode": "rhythm", "role": None, "hit_chance_bias": -0.15, "regen_seed": 7}
    section_presets.save_section_preset("thin verse", edit)
    # A real second read from disk, not a cached in-memory value.
    assert section_presets.list_section_presets()["thin verse"] == edit


def test_save_overwrites_an_existing_name():
    section_presets.save_section_preset("x", {"mode": "full", "role": None, "hit_chance_bias": 0, "regen_seed": 1})
    section_presets.save_section_preset("x", {"mode": "pitch", "role": None, "hit_chance_bias": 0, "regen_seed": 2})
    assert section_presets.list_section_presets()["x"]["mode"] == "pitch"


def test_delete_removes_a_real_saved_preset():
    section_presets.save_section_preset("temp", {"mode": "full", "role": None, "hit_chance_bias": 0, "regen_seed": 1})
    section_presets.delete_section_preset("temp")
    assert section_presets.list_section_presets() == {}


def test_delete_rejects_unknown_name():
    with pytest.raises(KeyError):
        section_presets.delete_section_preset("does-not-exist")


def test_save_rejects_empty_name():
    with pytest.raises(ValueError):
        section_presets.save_section_preset("   ", {"mode": "full", "role": None, "hit_chance_bias": 0, "regen_seed": 1})
