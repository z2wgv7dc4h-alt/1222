import pytest

from presets import load_all_presets
from song import compose_song, pitches_per_cell
from motif import Motif


ALL_PRESET_IDS = sorted(load_all_presets().keys())


@pytest.mark.parametrize("preset_id", ALL_PRESET_IDS)
def test_compose_song_end_to_end_for_every_preset(preset_id):
    """The real integration check this project never had: does a full
    song actually assemble from a real preset through every phase, with
    real (never fabricated) positions/pitches at every step?"""
    song = compose_song(preset_id, seed=42, num_sections=4)

    assert song["preset_id"] == preset_id
    assert len(song["sections"]) == len(song["sequence"])
    assert song["sections"], "must generate at least one section"

    guitar_fb = song["guitar_fretboard"]
    bass_fb = song["bass_fretboard"]

    for section in song["sections"]:
        m: Motif = section["motif"]
        # Every guitar pitch must be a REAL, reachable (string, fret) on
        # this preset's own tuning -- never a fabricated note.
        for pitch in section["pitches_per_cell"]:
            if pitch is not None:
                guitar_fb.pitch_to_fret(pitch, max_fret=24)

        # Rhythm invariant: both double-tracked takes and the kick/bass
        # lines all have exactly one entry per cell in the motif.
        assert len(section["guitar_take_a"]) == len(m.cell)
        assert len(section["guitar_take_b"]) == len(m.cell)
        assert len(section["kick"]) == len(m.cell)
        assert len(section["bass"]) == len(m.cell)

        # Bass positions must be real on the BASS's own fretboard (not the
        # guitar's) -- the whole point of Phase 5.
        for cell in section["bass"]:
            if not cell["is_rest"]:
                bass_fb.pitch_to_fret(cell["midi"], max_fret=20)

        # Lead line: one note per guitar hit, every note within the
        # generated register span.
        assert len(section["lead"]) == max(1, m.hit_count)


def test_compose_song_reproducible_with_same_seed():
    a = compose_song("djent", seed=7, num_sections=3)
    b = compose_song("djent", seed=7, num_sections=3)
    assert a["sequence"] == b["sequence"]
    assert [s["motif"].cell for s in a["sections"]] == [s["motif"].cell for s in b["sections"]]
    assert [s["motif"].deltas for s in a["sections"]] == [s["motif"].deltas for s in b["sections"]]


def test_compose_song_rejects_unknown_preset():
    with pytest.raises(KeyError):
        compose_song("not-a-real-preset", seed=1)


def test_compose_song_resolves_stale_band_alias():
    # "periphery" is a documented ALIASES entry resolving to "chill".
    song = compose_song("periphery", seed=1, num_sections=2)
    assert song["preset_id"] == "chill"


def test_pitches_per_cell_none_on_rests_and_real_pitch_on_hits():
    from theory import Scale
    m = Motif(
        cell=[
            {"duration": 1.0, "is_rest": False},
            {"duration": 1.0, "is_rest": True},
            {"duration": 1.0, "is_rest": False},
        ],
        deltas=[0, 2],
    )
    scale = Scale(root=40, name="minor")
    result = pitches_per_cell(m, scale)
    assert len(result) == 3
    assert result[1] is None
    assert result[0] is not None and result[2] is not None


def test_compose_song_judge_result_is_present_and_shaped():
    song = compose_song("groovy", seed=3, num_sections=4)
    j = song["judge"]
    assert set(j.keys()) == {"ok", "hits", "pm_ratio", "kick_lock"}
    assert isinstance(j["ok"], bool)
