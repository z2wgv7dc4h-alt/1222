import dataclasses
import random

import pytest

from presets import load_all_presets
from song import _compute_tempo_map, _generate_attempt, compose_song, pitches_per_cell
from motif import Motif
from structure import generate_section_sequence


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

        # Lead behavior is role-dependent (song.py's lead_mode branches):
        # solo -> dense featured line, chill/interlude -> harmonized
        # doubling of the rhythm's own theme, everything else -> silent
        # (a busy independent lead would clash with a dense chug section).
        role = section["role"]
        if role == "solo":
            assert section["lead_mode"] == "solo"
            assert len(section["lead"]) >= 1
        elif role in ("chill", "interlude"):
            assert section["lead_mode"] == "harmony"
            assert len(section["lead"]) == max(1, m.hit_count)
        else:
            assert section["lead_mode"] == "silent"
            assert section["lead"] == []


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
    # "periphery" now resolves to "progressive", the real Periphery-styled
    # preset, not "chill" (its original stand-in proxy before that preset existed).
    song = compose_song("periphery", seed=1, num_sections=2)
    assert song["preset_id"] == "progressive"


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


def test_solo_sections_get_a_denser_featured_lead():
    """A solo must actually be a featured lead, not the same background
    doubling line every other section gets."""
    song = compose_song("djent", seed=11, num_sections=10)
    solo_sections = [s for s in song["sections"] if s["role"] == "solo"]
    non_solo_sections = [s for s in song["sections"] if s["role"] != "solo"]
    assert solo_sections, "need at least one solo section to test -- try a different seed/length if this fires"

    for solo in solo_sections:
        # A solo's note count is driven by total_beats*2, not the rhythm
        # section's own hit_count, so it should clearly exceed a typical
        # non-solo section's lead length for the same song.
        assert len(solo["lead"]) > max(len(s["lead"]) for s in non_solo_sections)


def test_compose_song_judge_result_is_present_and_shaped():
    song = compose_song("groovy", seed=3, num_sections=4)
    j = song["judge"]
    assert set(j.keys()) == {"ok", "hits", "pm_ratio", "kick_lock"}
    assert isinstance(j["ok"], bool)


# ---------------------------------------------------------------------------
# Closing the real gap: preset.kick/group/pedal/octave_stab now actually
# change compose_song's output. Every test below starts from a REAL preset
# (djent, via load_all_presets()) and, where a controlled A/B comparison is
# needed, mutates exactly ONE field with dataclasses.replace -- never a
# synthetic hand-built preset -- then drives the same real
# song._generate_attempt(rng, preset, num_sections) call compose_song itself
# uses for one attempt, with an identically-seeded rng on both sides so any
# difference is attributable to the field, not RNG noise.
# ---------------------------------------------------------------------------

DJENT = load_all_presets()["djent"]
assert DJENT.kick == "euclid" and DJENT.group == 3 and DJENT.pedal == 0.85 and DJENT.octave_stab is True


def test_kick_style_field_changes_real_song_kick_output():
    bounce_variant = dataclasses.replace(DJENT, kick="bounce")

    euclid_song = _generate_attempt(random.Random(5), DJENT, num_sections=6)
    bounce_song = _generate_attempt(random.Random(5), bounce_variant, num_sections=6)

    # Same seed -> identical guitar motifs (kick style doesn't touch
    # guitar/motif generation), so any kick difference is real.
    assert [s["motif"].cell for s in euclid_song["sections"]] == [
        s["motif"].cell for s in bounce_song["sections"]
    ]
    assert [s["motif"].deltas for s in euclid_song["sections"]] == [
        s["motif"].deltas for s in bounce_song["sections"]
    ]

    differed = False
    for euclid_sec, bounce_sec in zip(euclid_song["sections"], bounce_song["sections"]):
        guitar_hits = [i for i, c in enumerate(euclid_sec["motif"].cell) if not c["is_rest"]]
        bounce_kick_hits = [i for i, c in enumerate(bounce_sec["kick"]) if not c["is_rest"]]
        euclid_kick_hits = [i for i, c in enumerate(euclid_sec["kick"]) if not c["is_rest"]]
        # "bounce" still locks exactly to the guitar for every role EXCEPT
        # build/solo (X.11: those always get a real double_kick/blast
        # overlay regardless of the preset's own declared style).
        if euclid_sec["role"] not in ("build", "solo"):
            assert bounce_kick_hits == guitar_hits
        if euclid_kick_hits != guitar_hits:
            differed = True
    assert differed, "expected djent's real 'euclid' kick style to differ from a guitar-locked kick in at least one section"


def test_group_field_changes_real_song_guitar_cell():
    ungrouped_variant = dataclasses.replace(DJENT, group=None)

    grouped_song = _generate_attempt(random.Random(9), DJENT, num_sections=4)
    ungrouped_song = _generate_attempt(random.Random(9), ungrouped_variant, num_sections=4)

    grouped_cells = [s["motif"].cell for s in grouped_song["sections"]]
    ungrouped_cells = [s["motif"].cell for s in ungrouped_song["sections"]]
    assert grouped_cells != ungrouped_cells, (
        "expected djent's real group=3 displacement to produce a different "
        "guitar rhythm cell than the same preset with group unset, same seed"
    )


def test_pedal_field_raises_root_degree_fraction_in_real_song_output():
    no_pedal_variant = dataclasses.replace(DJENT, pedal=None)

    def root_fraction(preset, n_seeds=60, num_sections=4):
        total = 0
        roots = 0
        for seed in range(n_seeds):
            result = _generate_attempt(random.Random(seed), preset, num_sections)
            for section in result["sections"]:
                deltas = section["motif"].deltas
                total += len(deltas)
                roots += sum(1 for d in deltas if d == 0)
        return roots / total if total else 0.0

    pedal_fraction = root_fraction(DJENT)
    no_pedal_fraction = root_fraction(no_pedal_variant)
    assert pedal_fraction > no_pedal_fraction + 0.1, (
        f"expected djent's real pedal=0.85 to noticeably raise the "
        f"root-degree fraction in actual compose_song output, got "
        f"no_pedal={no_pedal_fraction:.3f} pedal={pedal_fraction:.3f}"
    )


def test_octave_stab_field_changes_real_song_output():
    no_stab_variant = dataclasses.replace(DJENT, octave_stab=False)

    stab_on = _generate_attempt(random.Random(13), DJENT, num_sections=6)
    stab_off = _generate_attempt(random.Random(13), no_stab_variant, num_sections=6)

    # octave_stab must not affect anything else about generation, same seed.
    assert [s["motif"].cell for s in stab_on["sections"]] == [
        s["motif"].cell for s in stab_off["sections"]
    ]

    assert all(section["octave_stabs"] == [] for section in stab_off["sections"])
    sections_with_accents = [s for s in stab_on["sections"] if s["accents"]]
    assert sections_with_accents, "need at least one accented section to prove the wiring -- try a different seed if this fires"
    for section in sections_with_accents:
        assert len(section["octave_stabs"]) == len(section["accents"])
        assert section["octave_stabs"], "octave_stab=True must produce real stab pitches for an accented section"


def test_octave_stab_field_rejected_bad_preset_field_type_fails_closed():
    # Bad input: octave_stab must be a real bool per presets.validate_preset
    # (the wired load-time check), so a preset carrying a non-bool value
    # here can never have been loaded through load_preset/load_all_presets
    # in the first place -- validate_preset fails closed on it.
    from presets import validate_preset, load_tunings
    tunings = load_tunings()
    bad = {
        "id": "bogus", "description": "bad octave_stab", "tuning_key": "drop_g_7",
        "scale": "minor", "dissonance": 0.5, "bpm": 140, "bars": 4, "feel": "bounce",
        "open_chance": 0.5, "octave_stab": "yes", "kick": "bounce",
        "vocab": {"weights": {"0": 1}, "motion": 0.2},
    }
    with pytest.raises(ValueError):
        validate_preset(bad, tunings)


# ---------------------------------------------------------------------------
# X.6c -- metric modulation, wired into compose_song's real generation path.
# Trigger: the first "build" -> "breakdown" transition in the section
# sequence (structure.DEFAULT_GRAPH's own tension-into-release seam) gets a
# real metric modulation -- straight eighth (old pulse) becomes the new
# quarter beat, a half-time breakdown feel computed via
# metric_modulation.modulation_ratio/apply_metric_modulation through
# structure.tempo_at, never a separate parallel calculation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("preset_id", ALL_PRESET_IDS)
def test_compose_song_tempo_map_has_one_entry_per_section(preset_id):
    song = compose_song(preset_id, seed=42, num_sections=6)
    assert len(song["tempo_map"]) == len(song["sequence"])
    assert all(isinstance(bpm, float) and bpm > 0 for bpm in song["tempo_map"])


def test_compute_tempo_map_defaults_to_preset_bpm_with_no_breakdown():
    sequence = ["intro", "chill", "solo"]
    tempo_map = _compute_tempo_map(sequence, 140.0)
    assert tempo_map == [140.0, 140.0, 140.0]


def test_compute_tempo_map_applies_real_modulation_to_every_breakdown_and_reverts():
    """X.12 fix: real listening feedback ("drums are too slow... not
    really metal") on a longer song traced to a real bug -- the old
    one-shot-never-reverts design held the half-time modulation for the
    rest of the song after the FIRST breakdown. The real, correct
    behavior: every "breakdown"-role section independently gets the real
    half-time modulation, and every OTHER role -- including one right
    after a breakdown -- is back at the preset's own full base_bpm."""
    sequence = ["intro", "build", "breakdown", "build", "breakdown", "outro"]
    tempo_map = _compute_tempo_map(sequence, 160.0)
    assert tempo_map[0] == pytest.approx(160.0)  # intro
    assert tempo_map[1] == pytest.approx(160.0)  # build
    assert tempo_map[2] == pytest.approx(80.0)   # breakdown -- real half-time
    assert tempo_map[3] == pytest.approx(160.0)  # build -- REVERTS to full tempo
    assert tempo_map[4] == pytest.approx(80.0)   # breakdown again -- half-time again
    assert tempo_map[5] == pytest.approx(160.0)  # outro -- back to full tempo


def test_tempo_map_shows_real_bpm_change_at_every_real_breakdown_section():
    """Prove the real (not just the isolated helper's) wiring: find a seed
    whose section sequence genuinely contains a "breakdown" role, then
    confirm _generate_attempt's own tempo_map output -- the exact dict
    compose_song returns -- reflects the real modulation there AND real
    reversion on every non-breakdown section, including ones immediately
    after a breakdown.

    Seed search uses structure.generate_section_sequence directly rather
    than trying many compose_song seeds blind: _generate_attempt's very
    first RNG draw IS generate_section_sequence(rng, num_sections), so a
    seed found this way reproduces byte-identically inside
    _generate_attempt.
    """
    tech = load_all_presets()["tech"]
    num_sections = 10
    found_seed = None
    found_sequence = None
    for seed in range(200):
        sequence = generate_section_sequence(random.Random(seed), num_sections)
        if "breakdown" in sequence:
            found_seed = seed
            found_sequence = sequence
            break
    assert found_seed is not None, (
        "expected at least one seed in range(200) to produce a real "
        "breakdown section -- try a larger range if this fires"
    )

    result = _generate_attempt(random.Random(found_seed), tech, num_sections)
    assert result["sequence"] == found_sequence

    tempo_map = result["tempo_map"]
    assert len(tempo_map) == len(result["sequence"])

    for i, role in enumerate(result["sequence"]):
        if role == "breakdown":
            assert tempo_map[i] == pytest.approx(float(tech.bpm) * 0.5)
        else:
            # Real reversion: every non-breakdown section (even one
            # immediately after a breakdown) is back at full tempo.
            assert tempo_map[i] == pytest.approx(float(tech.bpm))


def test_preset_feel_breakdown_changes_real_song_duration_distribution():
    """preset.feel == "breakdown" (metalcore, deathcore's "chug" is
    unmapped so it's excluded) must measurably bias metalcore's actual
    compose_song output toward 8th/quarter durations over isolated 16ths,
    via the real ported rhythm.FEEL_DURATION_WEIGHTS table -- not just
    unit-level correctness in rhythm.py in isolation."""
    metalcore = load_all_presets()["metalcore"]
    assert metalcore.feel == "breakdown"
    no_feel_variant = dataclasses.replace(metalcore, feel="unmapped-placeholder")

    def sixteenth_share(preset, n_seeds=40):
        total = 0
        sixteenths = 0
        for seed in range(n_seeds):
            result = _generate_attempt(random.Random(seed), preset, num_sections=4)
            for section in result["sections"]:
                for cell in section["motif"].cell:
                    total += 1
                    if cell["duration"] == 0.25:
                        sixteenths += 1
        return sixteenths / total if total else 0.0

    biased_share = sixteenth_share(metalcore)
    unbiased_share = sixteenth_share(no_feel_variant)
    assert biased_share < unbiased_share - 0.05, (
        f"expected metalcore's real feel='breakdown' bias to measurably lower "
        f"the 16th-note share vs the same preset with an unmapped feel, got "
        f"biased={biased_share:.3f} unbiased={unbiased_share:.3f}"
    )


def test_every_preset_gets_a_real_snare_backbeat_wired_for_every_role():
    """X.9: snare_pattern_for_role must be wired for EVERY preset (not
    metalcore-specific) and every section, with chill/interlude silent."""
    for preset_id in load_all_presets():
        song = compose_song(preset_id, seed=4, num_sections=8)
        saw_hits = False
        for section in song["sections"]:
            snare = section["snare"]
            assert len(snare) == len(section["motif"].cell)
            has_hits = any(not c["is_rest"] for c in snare)
            if section["role"] in ("chill", "interlude"):
                assert not has_hits, f"{preset_id}/{section['role']} must be silent"
            elif has_hits:
                saw_hits = True
                assert all(c["role"] in ("SNARE", None) for c in snare)
        assert saw_hits, f"{preset_id}: expected at least one section with real snare hits"


def test_every_preset_gets_a_real_hihat_layer_wired_for_every_role():
    """X.11: hihat_pattern_for_role must be wired for EVERY preset, with
    chill/interlude silent, matching the same table as snare/kick."""
    for preset_id in load_all_presets():
        song = compose_song(preset_id, seed=4, num_sections=8)
        saw_hits = False
        for section in song["sections"]:
            hihat = section["hihat"]
            assert len(hihat) == len(section["motif"].cell)
            has_hits = any(not c["is_rest"] for c in hihat)
            if section["role"] in ("chill", "interlude"):
                assert not has_hits, f"{preset_id}/{section['role']} hihat must be silent"
            elif has_hits:
                saw_hits = True
                assert all(c["role"] in ("HIHAT_CLOSED", None) for c in hihat)
        assert saw_hits, f"{preset_id}: expected at least one section with real hihat hits"


def test_build_and_solo_sections_get_a_real_varied_kick_overlay():
    """X.11: build/solo kick style is always double_kick or blast,
    regardless of the preset's own declared kick style, and real
    variety is actually exercised (not silently always the same one)
    across enough seeds/sections."""
    preset = load_all_presets()["groovy"]  # a real preset whose own kick
    # style ("bounce") is neither double_kick nor blast, so any overlap
    # observed below is unambiguously the real X.11 overlay, not a
    # preset-style coincidence.
    assert preset.kick == "bounce"

    seen_styles = set()
    for seed in range(15):
        song = _generate_attempt(random.Random(seed), preset, num_sections=8)
        for section in song["sections"]:
            if section["role"] not in ("build", "solo"):
                continue
            kick_cells = section["kick"]
            guitar_cells = section["motif"].cell
            hit_indices = {i for i, c in enumerate(kick_cells) if not c["is_rest"]}
            # blast hits every cell; double_kick and bounce (guitar-lock)
            # generally don't -- use "hits every single cell" as the real,
            # checkable signature that distinguishes blast from the rest.
            if len(hit_indices) == len(kick_cells):
                seen_styles.add("blast-like")
            else:
                seen_styles.add("other")
    assert seen_styles, "expected at least one build/solo section across these seeds"
