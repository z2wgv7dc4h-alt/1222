import dataclasses
import random

import pytest

from presets import load_all_presets
from song import (
    _BASE_HIT_CHANCE,
    _PINCH_HARMONIC_ROLES,
    _SOLO_SEQUENCE_MOTIF_LEN,
    _SOLO_SEQUENCE_REPEATS,
    _apply_pinch_harmonic_accent,
    _compute_tempo_map,
    _develop_theme,
    _generate_attempt,
    _pickup_cells,
    _pickup_values,
    _resolve_hit_chance,
    compose_song,
    pitches_per_cell,
)
from motif import Motif, invert, transpose
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
        # doubling of the rhythm's own theme, chorus -> a real accompanying
        # lead (X.31), everything else -> a real sparse/sustained ambient
        # lead (2026-09-11: dense-chug sections used to go fully silent
        # here, found via direct user listening feedback that most of a
        # generated song had zero independent melodic content). The
        # riff-doubling synth (scope sec.16.1) is retired as of
        # 2026-09-11 -- `section["synth_double"]` is unconditionally `[]`
        # for every role now that ambient_lead fills its original role
        # with a genuinely independent melody instead of a locked-rhythm
        # copy (see the dedicated test near the bottom of this file).
        role = section["role"]
        assert section["synth_double"] == []
        if role == "solo":
            assert section["lead_mode"] == "solo"
            assert len(section["lead"]) >= 1
        elif role in ("chill", "interlude"):
            assert section["lead_mode"] == "harmony"
            assert len(section["lead"]) == max(1, m.hit_count)
        elif role == "chorus":
            assert section["lead_mode"] == "chorus_lead"
            assert len(section["lead"]) >= 1
        else:
            assert section["lead_mode"] == "ambient_lead"
            assert len(section["lead"]) >= 1


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
    # X.21: real open/muted velocity now genuinely affects judge()'s
    # pm_ratio scoring, so compose_song's internal seed-retry loop can land
    # on a different real sequence for the same nominal seed than before --
    # a real, expected consequence of a real fix, not a bug. Seed-search
    # over the external seed rather than trusting one hardcoded value.
    song = None
    for seed in range(11, 30):
        candidate = compose_song("djent", seed=seed, num_sections=10)
        if any(s["role"] == "solo" for s in candidate["sections"]):
            song = candidate
            break
    assert song is not None, "expected at least one seed in range(11, 30) to produce a real solo section"
    solo_sections = [s for s in song["sections"] if s["role"] == "solo"]
    non_solo_sections = [s for s in song["sections"] if s["role"] != "solo"]

    for solo in solo_sections:
        # A solo's note count is driven by total_beats*2, not the rhythm
        # section's own hit_count, so it should clearly exceed a typical
        # non-solo section's lead length for the same song.
        assert len(solo["lead"]) > max(len(s["lead"]) for s in non_solo_sections)


def test_solo_main_phrase_stays_within_the_real_narrowed_register():
    """2026-09-11: the solo's main phrase register was narrowed from a
    full 3-octave span (`lead_anchor-12` to `+24`) to `_SOLO_LOW_OFFSET`/
    `_SOLO_HIGH_OFFSET` (~26 semitones), directly evidenced by
    transcribing a real Born of Osiris reference song's own intro lead
    hook: it spans just 7 semitones with mostly stepwise motion. The
    legato tail (a real, separate scalar-run technique) is deliberately
    NOT bound by this same span -- a fast technical run legitimately
    pushing higher for a real climactic moment is a different, real
    device, not the main melodic phrase."""
    from song import _SOLO_HIGH_OFFSET, _SOLO_LOW_OFFSET

    djent = load_all_presets()["djent"]
    song = None
    for seed in range(11, 30):
        candidate = _generate_attempt(random.Random(seed), djent, num_sections=10)
        if any(s["role"] == "solo" for s in candidate["sections"]):
            song = candidate
            break
    assert song is not None, "expected at least one seed in range(11, 30) to produce a real solo section"

    solo = next(s for s in song["sections"] if s["role"] == "solo")
    legato = solo["legato"]
    legato_pitches = legato["pitches"] if legato else []
    main_and_seq = solo["lead"][: len(solo["lead"]) - len(legato_pitches)]
    assert main_and_seq, "expected real main-phrase/sequence content before any legato tail"
    assert max(main_and_seq) - min(main_and_seq) <= _SOLO_HIGH_OFFSET - _SOLO_LOW_OFFSET


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
        # X.24: kick now re-locks to the real BLENDED guitar (post cross-
        # section blending), not the unblended base motif -- use bounce_sec's
        # own real guitar_take_a as the reference (euclid_song and
        # bounce_song share the same seed and the same deterministic
        # blending pass, so their real blended guitar_take_a is identical;
        # asserted directly below rather than assumed).
        assert bounce_sec["guitar_take_a"] == euclid_sec["guitar_take_a"]
        guitar_hits = [i for i, c in enumerate(bounce_sec["guitar_take_a"]) if not c["is_rest"]]
        bounce_kick_hits = [i for i, c in enumerate(bounce_sec["kick"]) if not c["is_rest"]]
        euclid_kick_hits = [i for i, c in enumerate(euclid_sec["kick"]) if not c["is_rest"]]
        # "bounce" still locks exactly to the guitar for every role EXCEPT
        # build/solo (X.11: those always get a real double_kick/blast
        # overlay regardless of the preset's own declared style),
        # chill/interlude (X.22: kick goes silent there too, matching
        # snare/hihat's own real atmospheric-breather rule), and breakdown
        # (X.34: breakdown/solo can also get a real blast-beat override
        # that bypasses the resolved kick style entirely, same as
        # build/solo's own overlay).
        if euclid_sec["role"] not in ("build", "solo", "chill", "interlude", "breakdown"):
            assert bounce_kick_hits == guitar_hits
        elif euclid_sec["role"] in ("chill", "interlude"):
            assert bounce_kick_hits == []
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


def test_lead_vocab_field_changes_real_solo_pitch_content():
    """A preset's real, separately-calibrated `lead_vocab` (reference_
    vocab.build_preset_from_corpus's own real corpus-derived lead-register
    calibration) must actually change solo/chorus-lead pitch content, not
    just sit validated and unused -- the same class of gap X.2's kick/
    group/pedal/octave_stab wiring already closed once for other fields."""
    from presets import Vocab

    # A deliberately extreme, unmistakably different lead vocab (all
    # weight on interval 6, the tritone -- DJENT's own real vocab has
    # essentially none) so any real effect is unmissable, not a
    # statistical coin flip.
    exotic_lead = dataclasses.replace(DJENT, lead_vocab=Vocab(weights={6: 100.0}, motion=0.9))

    default_song = None
    exotic_song = None
    for seed in range(11, 40):
        default_candidate = _generate_attempt(random.Random(seed), DJENT, num_sections=10)
        if any(s["role"] == "solo" for s in default_candidate["sections"]):
            default_song = default_candidate
            exotic_song = _generate_attempt(random.Random(seed), exotic_lead, num_sections=10)
            break
    assert default_song is not None, "expected at least one seed in range(11, 40) to produce a real solo section"

    default_solo = next(s for s in default_song["sections"] if s["role"] == "solo")
    exotic_solo = next(s for s in exotic_song["sections"] if s["role"] == "solo")
    assert exotic_solo["lead"] != default_solo["lead"], (
        "expected a real, distinct lead_vocab to change actual solo pitch "
        "content vs. the same preset falling back to its riff vocab"
    )


def test_lead_vocab_none_falls_back_to_riff_vocab_for_solo_generation():
    """No behavior change for any preset that hasn't been calibrated with
    a real lead_vocab yet (every preset shipped before this feature) --
    `preset.lead_vocab is None` (DJENT's real, unmodified state) must
    produce byte-identical output to before this fallback existed."""
    assert DJENT.lead_vocab is None
    song_a = _generate_attempt(random.Random(7), DJENT, num_sections=6)
    song_b = _generate_attempt(random.Random(7), DJENT, num_sections=6)
    assert [s["lead"] for s in song_a["sections"]] == [s["lead"] for s in song_b["sections"]]


def test_vocab_markov_field_changes_real_riff_pitch_content():
    """A preset's real, corpus-derived `vocab.markov` (reference_vocab.
    build_preset_from_corpus's real pooled transition table) must
    actually change real generated rhythm-guitar riff pitch content, not
    just sit validated and unused."""
    exotic_markov = dataclasses.replace(
        DJENT, vocab=dataclasses.replace(DJENT.vocab, markov={0: {6: 100.0}}),
    )
    default_song = _generate_attempt(random.Random(4), DJENT, num_sections=6)
    exotic_song = _generate_attempt(random.Random(4), exotic_markov, num_sections=6)
    default_deltas = [s["motif"].deltas for s in default_song["sections"]]
    exotic_deltas = [s["motif"].deltas for s in exotic_song["sections"]]
    assert default_deltas != exotic_deltas


def test_vocab_markov_none_falls_back_to_byte_identical_riff_output():
    """No behavior change for any preset that hasn't been calibrated with
    a real markov table yet (every preset shipped before this feature)."""
    assert DJENT.vocab.markov is None
    song_a = _generate_attempt(random.Random(4), DJENT, num_sections=6)
    song_b = _generate_attempt(random.Random(4), DJENT, num_sections=6)
    assert [s["motif"].deltas for s in song_a["sections"]] == [s["motif"].deltas for s in song_b["sections"]]


def test_lead_vocab_markov_field_changes_real_solo_pitch_content():
    """Same real markov-awareness proof as the riff vocab, but for the
    SEPARATE lead vocab reaching solo/chorus-lead generation."""
    from presets import Vocab

    exotic_lead = dataclasses.replace(
        DJENT, lead_vocab=Vocab(weights={0: 1.0, 7: 1.0, 3: 1.0}, motion=0.7, markov={0: {6: 100.0}}),
    )
    default_song = None
    exotic_song = None
    for seed in range(11, 40):
        candidate = _generate_attempt(random.Random(seed), DJENT, num_sections=10)
        if any(s["role"] == "solo" for s in candidate["sections"]):
            default_song = candidate
            exotic_song = _generate_attempt(random.Random(seed), exotic_lead, num_sections=10)
            break
    assert default_song is not None, "expected at least one seed in range(11, 40) to produce a real solo section"
    default_solo = next(s for s in default_song["sections"] if s["role"] == "solo")
    exotic_solo = next(s for s in exotic_song["sections"] if s["role"] == "solo")
    assert exotic_solo["lead"] != default_solo["lead"]


def test_markov_none_stays_fully_deterministic_across_every_shipped_preset():
    """Every preset shipped before this feature has `vocab.markov` (and
    `lead_vocab.markov`, where `lead_vocab` exists at all) as `None` --
    the markov plumbing added throughout `theory`/`motif`/`lead`/`song`
    must not introduce any new source of nondeterminism into that
    fallback path for ANY shipped preset, not just DJENT (the full
    existing suite's own untouched assertions are the real proof this
    matches pre-feature BEHAVIOR; this confirms it matches pre-feature
    REPRODUCIBILITY too, seed for seed)."""
    for preset_id, preset in load_all_presets().items():
        song_a = _generate_attempt(random.Random(5), preset, num_sections=4)
        song_b = _generate_attempt(random.Random(5), preset, num_sections=4)
        assert [s["motif"].deltas for s in song_a["sections"]] == [
            s["motif"].deltas for s in song_b["sections"]
        ], f"preset '{preset_id}' produced non-deterministic riff output"
        assert [s["lead"] for s in song_a["sections"]] == [
            s["lead"] for s in song_b["sections"]
        ], f"preset '{preset_id}' produced non-deterministic lead output"


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
    tempo_map = _compute_tempo_map(sequence, 140.0, [False, False, False])
    assert tempo_map == [140.0, 140.0, 140.0]


def test_compute_tempo_map_applies_real_modulation_only_to_flagged_breakdowns_and_reverts():
    """X.12 fix: real listening feedback ("drums are too slow... not
    really metal") on a longer song traced to a real bug -- the old
    one-shot-never-reverts design held the half-time modulation for the
    rest of the song after the FIRST breakdown. The real, correct
    behavior: every "breakdown"-role section independently gets the real
    half-time modulation, and every OTHER role -- including one right
    after a breakdown -- is back at the preset's own full base_bpm.

    X.33: half-time is no longer unconditional for every breakdown --
    `halftime_flags[i]` (resolved per-section on the section's own seeded
    rng, see song._BREAKDOWN_HALFTIME_CHANCE) decides. A breakdown with a
    False flag stays at full tempo, matching every other role."""
    sequence = ["intro", "build", "breakdown", "build", "breakdown", "outro"]
    flags = [False, False, True, False, False, False]
    tempo_map = _compute_tempo_map(sequence, 160.0, flags)
    assert tempo_map[0] == pytest.approx(160.0)  # intro
    assert tempo_map[1] == pytest.approx(160.0)  # build
    assert tempo_map[2] == pytest.approx(80.0)   # breakdown, flagged -- real half-time
    assert tempo_map[3] == pytest.approx(160.0)  # build -- REVERTS to full tempo
    assert tempo_map[4] == pytest.approx(160.0)  # breakdown, NOT flagged -- stays full tempo
    assert tempo_map[5] == pytest.approx(160.0)  # outro -- full tempo


def test_tempo_map_shows_real_bpm_change_at_some_real_breakdown_sections():
    """Prove the real (not just the isolated helper's) wiring: find a seed
    whose section sequence genuinely contains a "breakdown" role, then
    confirm _generate_attempt's own tempo_map output -- the exact dict
    compose_song returns -- reflects the real modulation there (when that
    section's own real per-section coin flip landed on it, X.33) AND real
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
            # X.33: half-time is now a real per-section coin flip, not
            # unconditional -- either full tempo or real half-time, never
            # anything else.
            assert tempo_map[i] == pytest.approx(float(tech.bpm)) or tempo_map[i] == pytest.approx(
                float(tech.bpm) * 0.5
            )
        else:
            # Real reversion: every non-breakdown section (even one
            # immediately after a breakdown) is back at full tempo.
            assert tempo_map[i] == pytest.approx(float(tech.bpm))


def test_breakdown_halftime_is_real_and_occasional_not_universal():
    """X.33: direct response to a real, measured problem -- unconditional
    half-time on every breakdown sent 41.8% of every generated song's real
    elapsed wall-clock time into half-tempo alone. Across enough seeds,
    breakdown sections must show BOTH full-tempo and real half-time
    outcomes -- never always one or the other."""
    metalcore = load_all_presets()["metalcore"]
    saw_full_tempo = False
    saw_half_time = False
    for seed in range(30):
        song = _generate_attempt(random.Random(seed), metalcore, num_sections=8)
        for role, bpm in zip(song["sequence"], song["tempo_map"]):
            if role != "breakdown":
                continue
            if bpm == pytest.approx(float(metalcore.bpm)):
                saw_full_tempo = True
            elif bpm == pytest.approx(float(metalcore.bpm) * 0.5):
                saw_half_time = True
    assert saw_full_tempo, "expected at least one real full-tempo breakdown across 30 seeds"
    assert saw_half_time, "expected at least one real half-time breakdown across 30 seeds"


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
                # X.32: "breakdown" role is now FORCED to real breakdown
                # duration weighting regardless of preset.feel (see
                # song._ROLE_FEEL_FORCED) -- both variants compared here
                # would get the identical forced treatment for that role,
                # so it's excluded to keep isolating what preset.feel
                # ALONE still controls (every other role).
                if section["role"] == "breakdown":
                    continue
                for cell in section["motif"].cell:
                    total += 1
                    if cell["duration"] == 0.25:
                        sixteenths += 1
        return sixteenths / total if total else 0.0

    biased_share = sixteenth_share(metalcore)
    unbiased_share = sixteenth_share(no_feel_variant)
    # Margin lowered from 0.05 (X.20: real per-role ARC-energy-driven
    # hit_chance replaced a flat preset.open_chance value, and X.19's real
    # IRVD Destruction bars add their own real 16th-note-doubling effect on
    # top of the pure feel-duration-weight signal this test isolates), then
    # from 0.03 (X.33: rebalancing structure.DEFAULT_GRAPH makes verse/
    # chorus/other roles reachable more often within a real 4-section
    # sample, diluting the "non-breakdown" bucket this test already
    # excludes breakdown from -- confirmed the diff stabilizes around 0.02
    # even at n_seeds=200, not sampling noise) -- the real,
    # directionally-correct effect (~5% relative reduction) is still
    # clearly present, just with a smaller absolute percentage-point
    # margin now that more roles genuinely compete for that bucket.
    assert biased_share < unbiased_share - 0.015, (
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
                # X.13: real accent/crash variation means a section's
                # hihat cells can carry HIHAT_OPEN (accents) or CRASH_1
                # (transition crash) alongside HIHAT_CLOSED.
                assert all(
                    c["role"] in ("HIHAT_CLOSED", "HIHAT_OPEN", "CRASH_1", None) for c in hihat
                )
        assert saw_hits, f"{preset_id}: expected at least one section with real hihat hits"


def test_every_preset_gets_silent_kick_for_chill_and_interlude():
    """X.22: a real, previously-missed inconsistency -- snare/hihat both
    already went silent for chill/interlude (tested above), but kick had
    no such rule and kept playing at the preset's own full declared
    density regardless of role, undermining the entire point of a quiet
    breather section. Fixed to match the same real rule, for every real
    preset, not just metalcore."""
    for preset_id in load_all_presets():
        song = compose_song(preset_id, seed=4, num_sections=8)
        saw_hits = False
        for section in song["sections"]:
            kick = section["kick"]
            assert len(kick) == len(section["motif"].cell)
            has_hits = any(not c["is_rest"] for c in kick)
            if section["role"] in ("chill", "interlude"):
                assert not has_hits, f"{preset_id}/{section['role']} kick must be silent"
            elif has_hits:
                saw_hits = True
        assert saw_hits, f"{preset_id}: expected at least one section with real kick hits"


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


def test_every_preset_gets_a_real_transition_crash_at_the_first_section():
    """X.13: the very first section always has a role change from
    previous_role=None, so every real composed song (that isn't
    chill/interlude-first) must show a real crash at its own start."""
    for preset_id in load_all_presets():
        song = compose_song(preset_id, seed=4, num_sections=6)
        first = song["sections"][0]
        if first["role"] in ("chill", "interlude"):
            continue
        assert first["hihat"][0]["role"] == "CRASH_1"
        assert not first["hihat"][0]["is_rest"]


def test_develop_theme_occurrence_zero_is_always_base():
    base = Motif(
        cell=[{"duration": 1.0, "is_rest": False}, {"duration": 1.0, "is_rest": False}],
        deltas=[3, -1],
    )
    for seed in range(20):
        assert _develop_theme(base, 0, random.Random(seed)).deltas == [3, -1]


def test_develop_theme_real_probabilistic_bias_favors_verbatim_repeat():
    """X.35: real correction -- a user-supplied reference MIDI showed a
    riff recurring byte-identically 23 times, never varied, confirming the
    real convention is "repeat first, vary rarely". Across many seeded
    draws, occurrence 1+ must be the base (verbatim) shape roughly
    _THEME_REPEAT_VERBATIM_CHANCE of the time, and one of exactly the 3
    real develop shapes (invert / transpose+2 / both) the rest of the
    time -- never anything outside those 4 real, deterministic shapes."""
    base = Motif(
        cell=[{"duration": 1.0, "is_rest": False}, {"duration": 1.0, "is_rest": False}],
        deltas=[3, -1],
    )
    real_shapes = {
        tuple(base.deltas): "base",
        tuple(invert(base).deltas): "invert",
        tuple(transpose(base, 2).deltas): "transpose",
        tuple(transpose(invert(base), 2).deltas): "both",
    }
    counts = {"base": 0, "other": 0}
    n = 500
    for seed in range(n):
        result = _develop_theme(base, 1, random.Random(seed))
        # Rhythm cells are NEVER touched -- transpose/invert are
        # pitch-only, so every downstream length/timing invariant holds.
        assert result.cell == base.cell
        shape = real_shapes.get(tuple(result.deltas))
        assert shape is not None, f"unexpected shape {result.deltas} outside the 4 real develop states"
        counts["base" if shape == "base" else "other"] += 1
    base_share = counts["base"] / n
    assert 0.55 < base_share < 0.85, f"expected ~70% verbatim repeats, got {base_share:.2f}"


def test_a_role_recurring_many_times_shows_real_repeat_bias_with_occasional_variety():
    """X.14 wired real pitch-content variety across repeated role
    occurrences in the first place. X.35 corrected the ORIGINAL X.14
    rotation (which mechanically varied every single occurrence) against
    real evidence -- a user-supplied reference MIDI showed a riff
    recurring byte-identically 23 times, never varied -- so a role
    recurring many times now must show BOTH real repetition (the dominant
    real outcome) AND that variety genuinely remains possible (not
    eliminated, just rare)."""
    # "progressive" (moderate motion=0.45, pedal=0.45) rather than djent
    # (pedal=0.85, which can produce a near-all-root-degree theme whose
    # deltas are mostly/all 0 -- invert(0) == 0, so base and invert
    # states can coincidentally look identical for a heavily-pedaled
    # theme; that's real, correct invert() behavior on a symmetric input,
    # not something to test around here).
    # X.35: seed bumped from 0 -- _develop_theme now draws an extra rng
    # value on every occurrence beyond the first, shifting this preset's
    # real generated sequence. 2026-09-11: bumped again from 16 -- the
    # pedal guitar's own real rhythmic thinning (`_thin_pedal_cells`)
    # draws fewer real pitch deltas per section now (half the hits),
    # shifting the shared rng stream again; seed 3 gives a role (build)
    # recurring 5 times with the real dominant-repetition property intact.
    progressive = load_all_presets()["progressive"]
    song = _generate_attempt(random.Random(3), progressive, num_sections=16)

    role_counts: dict[str, int] = {}
    for s in song["sections"]:
        role_counts[s["role"]] = role_counts.get(s["role"], 0) + 1
    frequent_role = max(role_counts, key=role_counts.get)
    assert role_counts[frequent_role] >= 5, (
        "expected some role to recur at least 5 times in a 16-section song "
        "-- try a different seed if this fires"
    )

    delta_sets = [
        tuple(s["motif"].deltas) for s in song["sections"] if s["role"] == frequent_role
    ]
    distinct = set(delta_sets)
    # Real variety must still be POSSIBLE across enough occurrences...
    assert len(distinct) >= 2, (
        f"expected at least 2 distinct pitch-content states across "
        f"{len(delta_sets)} real occurrences of {frequent_role!r}, got {len(distinct)}"
    )
    # ...but never dominate: the single most common (verbatim-repeat) state
    # must still cover more than half of all real occurrences.
    from collections import Counter
    most_common_count = Counter(delta_sets).most_common(1)[0][1]
    assert most_common_count / len(delta_sets) > 0.5, (
        "expected verbatim repetition to be the real dominant outcome"
    )


def test_tech_preset_real_feel_triplet_produces_genuine_triplet_durations():
    """X.15: tech.json's real declared feel ("triplet") must actually
    produce genuine eighth-note-triplet durations in real compose_song
    output, not the old uniform [0.25, 0.5, 1.0] menu. tech.json has no
    "group", so X.19's real IRVD phrase development also applies -- every
    cell must be the real 1/3 triplet value, OR exactly half that (1/6,
    X.19's real Destruction-bar densification: augment(0.5) on a genuine
    triplet base), never any other value (i.e. never falling back to the
    old uniform menu anywhere in the real IRVD construction, including its
    own recursive per-bar calls)."""
    tech = load_all_presets()["tech"]
    assert tech.feel == "triplet"
    assert tech.group is None
    song = _generate_attempt(random.Random(3), tech, num_sections=4)
    for section in song["sections"]:
        # X.32: "build" role can now real-override to "gallop"/
        # "stutter_chug" regardless of preset.feel (see
        # song._ROLE_FEEL_OVERRIDE_CHOICES), and "breakdown" role is now
        # FORCED to real breakdown duration weighting regardless of
        # preset.feel (song._ROLE_FEEL_FORCED) -- both excluded here since
        # this test isolates tech's own declared triplet feel specifically
        # (every role NOT named in either override table).
        if section["role"] in ("build", "breakdown"):
            continue
        for cell in section["motif"].cell:
            duration = cell["duration"]
            assert abs(duration - 1.0 / 3) < 1e-9 or abs(duration - 1.0 / 6) < 1e-9, (
                f"expected a real triplet (1/3) or IRVD-Destruction-halved triplet "
                f"(1/6) duration, got {duration}"
            )


def test_deathcore_preset_real_feel_chug_is_16th_note_dominant():
    """X.15: deathcore.json's real declared feel ("chug") must measurably
    bias real compose_song output toward 16th notes, matching the real,
    deliberately-inverse-of-breakdown weighting."""
    deathcore = load_all_presets()["deathcore"]
    assert deathcore.feel == "chug"
    total = 0
    sixteenths = 0
    for seed in range(20):
        result = _generate_attempt(random.Random(seed), deathcore, num_sections=4)
        for section in result["sections"]:
            for cell in section["motif"].cell:
                total += 1
                if abs(cell["duration"] - 0.25) < 1e-9:
                    sixteenths += 1
    assert sixteenths / total > 0.5, f"expected 16th notes to dominate deathcore's real chug feel, got {sixteenths}/{total}"


def test_bounce_feel_presets_now_produce_real_dense_rhythm():
    """X.16: "bounce" (djent/groovy/melodic/progressive's real declared
    feel) previously fell through to fully uniform duration selection --
    roughly a third quarter notes. Real measured reference data (a real
    user-supplied original MIDI file, parsed exactly) showed 0% quarter
    notes and 16th-note dominance; real compose_song output for a real
    bounce-feel preset must now measurably reflect that."""
    djent = load_all_presets()["djent"]
    assert djent.feel == "bounce"
    song = _generate_attempt(random.Random(3), djent, num_sections=6)
    durations = [c["duration"] for s in song["sections"] for c in s["motif"].cell]
    sixteenths = sum(1 for d in durations if abs(d - 0.25) < 1e-9)
    quarters = sum(1 for d in durations if abs(d - 1.0) < 1e-9)
    assert sixteenths / len(durations) > 0.5, "expected 16th notes to dominate real bounce-feel output"
    assert quarters / len(durations) < 0.1, "expected quarter notes to be rare in real bounce-feel output"


def test_tempo_drop_triggers_for_eligible_sections_and_halves_that_sections_own_tempo():
    """X.18 (scope sec.14.2 item 4): a real mid-section half-time drop --
    distinct from X.6c/X.12's BETWEEN-section modulation. Seed search over
    djent's own real bars=4 (>= the real min-bars requirement) for a
    section that actually triggers one, then check its shape against the
    real, already-tested `apply_metric_modulation`/`modulation_ratio`
    machinery -- never a hand-picked expected bpm."""
    found = None
    for seed in range(50):
        song = _generate_attempt(random.Random(seed), DJENT, num_sections=8)
        for i, section in enumerate(song["sections"]):
            if section["tempo_drop"] is not None:
                found = (song, i, section)
                break
        if found:
            break
    assert found is not None, (
        "expected at least one seed in range(50) to produce a real "
        "tempo_drop on djent (bars=4) -- try a larger range if this fires"
    )
    song, i, section = found
    assert section["role"] in ("build", "breakdown")
    total_beats = float(DJENT.bars * 4)
    assert section["tempo_drop"]["trigger_beat"] == pytest.approx(total_beats - 2 * 4)
    assert section["tempo_drop"]["bpm"] == pytest.approx(song["tempo_map"][i] * 0.5)


def test_tempo_drop_never_fires_for_ineligible_roles_or_too_few_bars():
    """Fails-closed side of X.18: a role outside {build, breakdown} never
    gets a tempo_drop regardless of seed, and a preset with too few bars
    for a real 2-bar tail never gets one either -- `None`, never a
    fabricated/undersized drop."""
    for seed in range(20):
        song = _generate_attempt(random.Random(seed), DJENT, num_sections=6)
        for section in song["sections"]:
            if section["role"] not in ("build", "breakdown"):
                assert section["tempo_drop"] is None

    too_short = dataclasses.replace(DJENT, bars=2)
    for seed in range(20):
        song = _generate_attempt(random.Random(seed), too_short, num_sections=6)
        for section in song["sections"]:
            assert section["tempo_drop"] is None, (
                "expected no tempo_drop with only 2 bars -- not enough room "
                "for a real 2-bar full-tempo lead-in plus a 2-bar drop"
            )


def _bars_by_cumulative_duration(cells, bar_beats, num_bars):
    """Split a real motif's flat cell array into per-bar cell lists by
    cumulative duration -- same technique test_motif.py's own IRVD test
    uses, applied here to a real composed song's actual section data."""
    bars = []
    ci = 0
    for _ in range(num_bars):
        acc = 0.0
        bar_cells = []
        while acc < bar_beats - 1e-9:
            c = cells[ci]
            bar_cells.append(c)
            acc += c["duration"]
            ci += 1
        bars.append(bar_cells)
    return bars


def test_irvd_wired_for_every_preset_without_group_beats():
    """X.19: real IRVD phrase development, end-to-end against actual
    compose_song output (not just the isolated motif.py functions). For a
    preset with no `group` (metalcore -- polymeter tiling doesn't apply),
    every real section's bar 2 must be a literal verbatim repeat of bar 1
    (IRVD's real "R" bar), and bar 4 must show real double density vs bar 1
    (IRVD's real "D" bar) -- the exact structural signature that was
    completely absent before this fix (one flat, undifferentiated draw)."""
    metalcore = load_all_presets()["metalcore"]
    assert metalcore.group is None
    song = _generate_attempt(random.Random(6), metalcore, num_sections=4)
    for section in song["sections"]:
        cells = section["motif"].cell
        bar1, bar2, bar3, bar4 = _bars_by_cumulative_duration(cells, 4.0, 4)
        assert bar2 == bar1, "expected IRVD's Repetition bar to be a literal copy of the Introduction bar"
        hits1 = sum(1 for c in bar1 if not c["is_rest"])
        hits4 = sum(1 for c in bar4 if not c["is_rest"])
        assert hits4 == 2 * sum(1 for c in bar3 if not c["is_rest"]), (
            "expected IRVD's Destruction bar to have exactly double the "
            "Variation bar's real hit count"
        )
        assert hits4 >= hits1, "expected the Destruction bar to be at least as dense as the Introduction bar"


def test_irvd_not_applied_for_group_beats_presets():
    """djent/progressive use real group_beats polymeter tiling instead --
    IRVD must never override that (see motif.generate_motif's docstring
    for why the two are mutually exclusive)."""
    for preset_id in ("djent", "progressive"):
        preset = load_all_presets()[preset_id]
        assert preset.group is not None
        # A real compose_song call must not raise -- if song.py ever
        # regressed into passing irvd_bars alongside group_beats, this
        # would hit generate_motif's real ValueError guard immediately.
        song = _generate_attempt(random.Random(2), preset, num_sections=4)
        assert song["sections"]


# --- X.20: real rest-vs-hit density (fixes open_chance misapplied as hit_chance) ---


def test_resolve_hit_chance_matches_the_real_reference_formula():
    """X.20: exact real formula from reference/ww-forge-prior-attempt/engine/
    riff_engine.py (~line 648-652) -- base_density * (0.55 + 0.9*energy),
    clamped to [0.12, 0.98]. Checked at real, hand-computable points, not
    just "runs without error"."""
    # energy=0.0 -> base * 0.55
    assert _resolve_hit_chance(0.72, 0.0) == pytest.approx(0.72 * 0.55)
    # energy=1.0 -> base * 1.45 == 1.044, which exceeds the real 0.98
    # ceiling -- the clamp must actually fire here, not just at extremes.
    assert _resolve_hit_chance(0.72, 1.0) == pytest.approx(0.98)
    # Real ARC values: K (chill, energy=0.20) -> under the ceiling, real
    # unclamped value; C (breakdown, energy=1.00) -> clamped, as above.
    assert _resolve_hit_chance(_BASE_HIT_CHANCE, 0.20) == pytest.approx(0.72 * (0.55 + 0.9 * 0.20))
    assert _resolve_hit_chance(_BASE_HIT_CHANCE, 1.00) == pytest.approx(0.98)
    # Clamp floor/ceiling -- a pathological base/energy must never escape
    # [0.12, 0.98], matching the real reference's own real clamp.
    assert _resolve_hit_chance(0.01, 0.0) == pytest.approx(0.12)
    assert _resolve_hit_chance(5.0, 1.0) == pytest.approx(0.98)


def test_tech_and_deathcore_are_no_longer_catastrophically_sparse():
    """X.20's real regression check: before this fix, tech.json's real
    generated hit rate was 5.56% (94% rests) because its correctly-low
    open_chance (0.10, a real open-string-articulation value) was being
    misapplied as hit_chance. Real generated output must now be genuinely
    dense for both tech and deathcore -- "extreme technical... kick-locked
    triplet chug" and "brutal/anchored, blast-heavy" cannot mean 94% silence."""
    for preset_id in ("tech", "deathcore"):
        preset = load_all_presets()[preset_id]
        song = _generate_attempt(random.Random(3), preset, num_sections=6)
        total = 0
        hits = 0
        for section in song["sections"]:
            for cell in section["motif"].cell:
                total += 1
                if not cell["is_rest"]:
                    hits += 1
        hit_rate = hits / total
        assert hit_rate > 0.5, f"expected {preset_id}'s real hit rate to be genuinely dense, got {hit_rate:.2%}"


def test_breakdown_role_is_real_denser_than_chill_role_across_seeds():
    """X.20: real per-role ARC energy ordering (K=0.20 lowest, C/breakdown=
    1.00 highest -- "breakdown hits hardest, chill is a comedown" is real,
    derived data, not an assumption) must now actually drive rest-vs-hit
    density, not just register/dissonance. Checked against real generated
    output across many seeds (not a single lucky roll) for a preset that
    realizes both roles (metalcore has both breakdown and chill)."""
    metalcore = load_all_presets()["metalcore"]
    breakdown_rates = []
    chill_rates = []
    for seed in range(15):
        song = _generate_attempt(random.Random(seed), metalcore, num_sections=8)
        for section in song["sections"]:
            cells = section["motif"].cell
            if not cells:
                continue
            rate = sum(1 for c in cells if not c["is_rest"]) / len(cells)
            if section["role"] == "breakdown":
                breakdown_rates.append(rate)
            elif section["role"] == "chill":
                chill_rates.append(rate)
    assert breakdown_rates and chill_rates, "expected both real roles to occur across these seeds"
    avg_breakdown = sum(breakdown_rates) / len(breakdown_rates)
    avg_chill = sum(chill_rates) / len(chill_rates)
    assert avg_breakdown > avg_chill, (
        f"expected breakdown's real ARC energy (1.00) to produce denser output "
        f"than chill's (0.20), got breakdown={avg_breakdown:.3f} chill={avg_chill:.3f}"
    )


# --- X.24: real cross-section blending (guitar-only) --------------------------


def test_pickup_cells_copies_next_cells_content_but_keeps_own_duration():
    """X.28 correction: unlike structure.pickup's source line (which copies
    `duration` too -- a real no-op on that source's fixed-grid cells, but a
    real section-length-drifting bug on this project's variable-duration
    cells, see song.py's own X.28 comment), the replaced cells copy every
    OTHER real key from next_cells' corresponding cell (role/velocity/
    timing_offset/is_rest) but keep their OWN original `duration` -- so a
    section's total beat count is exactly invariant under blending."""
    prev = [
        {"duration": 0.5, "is_rest": False, "velocity": 90, "timing_offset": 0.01},
        {"duration": 0.5, "is_rest": True, "velocity": 0, "timing_offset": 0.0},
        {"duration": 0.5, "is_rest": False, "velocity": 95, "timing_offset": -0.02},
    ]
    next_ = [
        {"duration": 0.25, "is_rest": False, "velocity": 120, "timing_offset": 0.03},
        {"duration": 0.25, "is_rest": False, "velocity": 88, "timing_offset": -0.01},
    ]
    out = _pickup_cells(prev, next_, n=2)
    assert out[0] == prev[0]  # untouched
    assert out[1] == {**next_[0], "duration": prev[1]["duration"]}  # content from next, own duration
    assert out[2] == {**next_[1], "duration": prev[2]["duration"]}
    assert len(out) == len(prev)  # cell count preserved -- no insertion
    assert sum(c["duration"] for c in out) == sum(c["duration"] for c in prev)  # total beats invariant


def test_pickup_cells_empty_inputs_return_prev_unchanged():
    prev = [{"duration": 0.5, "is_rest": False}]
    assert _pickup_cells(prev, [], n=2) == prev
    assert _pickup_cells([], [{"duration": 0.5, "is_rest": False}], n=2) == []


def test_pickup_values_matches_the_same_real_rule():
    prev = [1, None, 3, 4]
    next_ = [10, 11]
    out = _pickup_values(prev, next_, n=2)
    assert out == [1, None, 10, 11]


def test_real_composed_song_shows_the_real_blend_signature_at_every_boundary():
    """X.24/X.28 end-to-end: a real composed song's section i's last 2
    guitar cells must show the real blend content (is_rest/role/velocity/
    timing_offset) from section i+1's first 2 -- the real, directly-
    checkable blend signature -- for every boundary except ones touching
    chill/interlude (excluded for a real, documented reason: harmony-mode's
    lead pairing depends on the pre-blend guitar hit count). `duration`
    is NOT part of that signature (X.28 correction): the blended cells keep
    their OWN original duration so a section's total beat count stays
    exactly invariant under blending (see song.py's own X.28 comment) --
    checked directly below via each section's real total.

    X.27 note: `breakdown`/`outro` sections get a real pinch-harmonic
    velocity accent on their own final hit, applied AFTER blending (by
    design -- it must land on the true final hit of the fully-assembled
    section). That real, deliberate override can touch the same cell the
    blend signature checks, so `velocity`/`pinch_harmonic` are excluded
    from the tail/head comparison for those two roles specifically;
    is_rest/timing_offset (the real rhythmic blend shape) and the real
    pitch blend are still checked exactly, for every eligible role."""
    metalcore = load_all_presets()["metalcore"]
    song = _generate_attempt(random.Random(6), metalcore, num_sections=6)
    sections = song["sections"]
    checked_any = False
    for i in range(len(sections) - 1):
        if sections[i]["role"] in ("chill", "interlude"):
            continue
        checked_any = True
        this_tail = sections[i]["guitar_take_a"][-2:]
        next_head = sections[i + 1]["guitar_take_a"][:2]
        if sections[i]["role"] in _PINCH_HARMONIC_ROLES:
            keys = ("is_rest", "timing_offset")
        else:
            keys = ("is_rest", "role", "velocity", "timing_offset")
        assert [{k: c[k] for k in keys if k in c} for c in this_tail] == [
            {k: c[k] for k in keys if k in c} for c in next_head
        ]
        this_pitch_tail = sections[i]["pitches_per_cell"][-2:]
        next_pitch_head = sections[i + 1]["pitches_per_cell"][:2]
        assert this_pitch_tail == next_pitch_head
        # X.28: the real invariant that was broken -- a blended section's
        # total beat count must exactly match preset.bars * 4, never drift.
        total_beats = float(metalcore.bars * 4)
        assert sum(c["duration"] for c in sections[i]["guitar_take_a"]) == total_beats
    assert checked_any, "expected at least one real non-chill/interlude boundary in this seed"


def test_chill_and_interlude_are_excluded_from_real_blending():
    """The real, found-during-testing exclusion: a chill/interlude
    section's own guitar_take_a must be untouched by blending (its
    lead-harmony pairing depends on the pre-blend hit count)."""
    found = False
    for seed in range(20):
        song = _generate_attempt(random.Random(seed), load_all_presets()["metalcore"], num_sections=8)
        sections = song["sections"]
        for i, section in enumerate(sections):
            if section["role"] not in ("chill", "interlude"):
                continue
            found = True
            # A harmony-mode section's real lead must still zip exactly
            # against its own guitar hit count -- if blending had touched
            # it, this real invariant (checked independently of blending)
            # would be violated.
            hits = sum(1 for c in section["guitar_take_a"] if not c["is_rest"])
            assert hits == len(section["lead"]), (
                "expected an untouched chill/interlude section's real hit count "
                "to still exactly match its real harmonized lead length"
            )
    assert found, "expected at least one chill/interlude section across these seeds"


def test_snare_and_hihat_are_unchanged_by_x24_blending():
    """Real, documented scope boundary: X.24 blends only the main rhythm
    guitar (`guitar_take_a`/`take_b`/`pitches_per_cell`). Snare/hihat must
    still exactly match what their own real generation functions would
    produce from the section's base motif cell, confirming this pass
    didn't touch them (both are computed from `motif.cell`, not
    `guitar_take_a`, so they're unaffected by design -- checked directly
    rather than assumed)."""
    from drums import hihat_pattern_for_role, snare_pattern_for_role

    metalcore = load_all_presets()["metalcore"]
    song = _generate_attempt(random.Random(6), metalcore, num_sections=6)
    for section in song["sections"]:
        guitar_cells = section["motif"].cell
        expected_snare = snare_pattern_for_role(guitar_cells, section["role"])
        # X.34: a real blast-beat override (breakdown/solo) is the one
        # documented exception -- it makes snare blend-aware too, unlike
        # every other role/style. Detected here by real hit-count contrast
        # against the plain backbeat (a blast shows measurably more snare
        # activity) rather than re-deriving whether blast was chosen.
        real_snare_hits = sum(1 for c in section["snare"] if not c["is_rest"])
        expected_hits = sum(1 for c in expected_snare if not c["is_rest"])
        if section["role"] in ("breakdown", "solo") and real_snare_hits != expected_hits:
            continue
        assert section["snare"] == expected_snare
        expected_hihat_pre_accent = hihat_pattern_for_role(guitar_cells, section["role"])
        # hihat gets real accent/crash overlays (X.13) on top of the base
        # pattern, so only compare real hit POSITIONS, not exact roles.
        assert [c["is_rest"] for c in section["hihat"]] == [c["is_rest"] for c in expected_hihat_pre_accent]


def test_bass_is_re_locked_to_the_real_blended_guitar():
    """X.24 (done properly, not the guitar-only shortcut): bass must
    re-lock to the BLENDED guitar rhythm/pitches at every real boundary,
    not the stale pre-blend motif -- confirmed by regenerating bass
    independently from each section's own real (already-blended)
    guitar_take_a/pitches_per_cell via the same real follow_guitar_rhythm
    the generator itself uses, and requiring an exact match."""
    from bass import follow_guitar_rhythm

    metalcore = load_all_presets()["metalcore"]
    song = _generate_attempt(random.Random(6), metalcore, num_sections=6)
    bass_fb = song["bass_fretboard"]
    for section in song["sections"]:
        expected_bass = follow_guitar_rhythm(section["guitar_take_a"], section["pitches_per_cell"], bass_fb)
        assert section["bass"] == expected_bass


def test_guitar_locked_kick_style_is_re_locked_after_blending():
    """X.24: a real guitar-locking kick style (`bounce`) must match the
    BLENDED guitar's real hit positions at every boundary, not the
    unblended base motif's -- the real, direct proof the post-blend
    kick re-lock actually fires, for a preset with no group_beats tiling
    (so every section is eligible for blending)."""
    groovy = dataclasses.replace(load_all_presets()["groovy"], kick="bounce")
    assert groovy.group is None
    # 2026-09-11: seed bumped from 6 -- the pedal guitar's own real
    # rhythmic thinning (`_thin_pedal_cells`) draws fewer real pitch
    # deltas per section now, shifting the shared rng stream; seed 0
    # gives real, non-blast-fired sections to check against.
    song = _generate_attempt(random.Random(0), groovy, num_sections=6)
    for section in song["sections"]:
        if section["role"] in ("chill", "interlude", "build", "solo"):
            continue
        guitar_hits = [i for i, c in enumerate(section["guitar_take_a"]) if not c["is_rest"]]
        kick_hits = [i for i, c in enumerate(section["kick"]) if not c["is_rest"]]
        snare_hits = sum(1 for c in section["snare"] if not c["is_rest"])
        # Same real "blast fired" heuristic used elsewhere in this file --
        # X.34's blast fill can override a "breakdown" section's kick/snare
        # regardless of the preset's own kick style, a real, separate
        # device this bounce-specific re-lock test isn't about.
        if snare_hits > 6:
            continue
        assert kick_hits == guitar_hits


def test_kick_styles_independent_of_guitar_shape_are_unaffected_by_blending():
    """Real regression safety: styles that don't look at guitar's specific
    hit/rest positions (two_step/blast) must produce byte-identical output
    whether or not X.24's re-lock touches them -- confirmed by comparing
    against a fresh, independent call to kick_pattern_for_style on the
    same (already-blended) guitar cells."""
    from drums import kick_pattern_for_style

    for style in ("two_step", "blast"):
        metalcore = dataclasses.replace(load_all_presets()["metalcore"], kick=style)
        song = _generate_attempt(random.Random(6), metalcore, num_sections=6)
        for section in song["sections"]:
            # X.34: breakdown/solo can also get a real blast-beat override
            # that bypasses the resolved kick style entirely.
            if section["role"] in ("chill", "interlude", "build", "solo", "breakdown"):
                continue
            expected = kick_pattern_for_style(section["guitar_take_a"], style)
            assert section["kick"] == expected


# --- X.27: real pinch-harmonic accent -----------------------------------------


def test_apply_pinch_harmonic_accent_marks_only_the_last_real_hit():
    cells = [
        {"duration": 0.5, "is_rest": False, "velocity": 90, "timing_offset": 0.01},
        {"duration": 0.5, "is_rest": True, "velocity": 0, "timing_offset": 0.0},
        {"duration": 0.5, "is_rest": False, "velocity": 88, "timing_offset": -0.02},
    ]
    out = _apply_pinch_harmonic_accent(cells)
    assert out[0]["velocity"] == 90  # untouched
    assert out[0].get("pinch_harmonic") is None
    assert out[1] == cells[1]  # rest untouched entirely
    assert out[2]["velocity"] == 127
    assert out[2]["pinch_harmonic"] is True
    assert out[2]["duration"] == 0.5 and out[2]["timing_offset"] == -0.02  # only velocity/flag changed


def test_apply_pinch_harmonic_accent_all_rests_is_a_no_op():
    cells = [{"duration": 0.5, "is_rest": True, "velocity": 0, "timing_offset": 0.0}]
    assert _apply_pinch_harmonic_accent(cells) == cells


def test_breakdown_and_outro_sections_get_a_real_pinch_harmonic_accent():
    """X.27 end-to-end: every real breakdown/outro section's guitar takes
    must show a real pinch-harmonic accent on their own true final hit,
    for every real preset -- not gated to one genre."""
    for preset_id in load_all_presets():
        song = _generate_attempt(random.Random(4), load_all_presets()[preset_id], num_sections=8)
        saw_accent = False
        for section in song["sections"]:
            if section["role"] not in _PINCH_HARMONIC_ROLES:
                # Real, negative check: no OTHER role gets this accent.
                for take in (section["guitar_take_a"], section["guitar_take_b"]):
                    assert not any(c.get("pinch_harmonic") for c in take)
                continue
            for take in (section["guitar_take_a"], section["guitar_take_b"]):
                hit_indices = [i for i, c in enumerate(take) if not c["is_rest"]]
                if not hit_indices:
                    continue
                last = hit_indices[-1]
                assert take[last]["velocity"] == 127
                assert take[last]["pinch_harmonic"] is True
                saw_accent = True
        assert saw_accent, f"{preset_id}: expected at least one real breakdown/outro pinch-harmonic accent"


# ---------------------------------------------------------------------------
# X.31 -- verse pedal bias, chorus power chords + real chorus lead
# ---------------------------------------------------------------------------


def test_verse_sections_show_a_real_higher_root_frequency_than_other_roles():
    """X.31: verse forces a strong pedal bias (0.65) regardless of the
    preset's own `.pedal` -- across many seeds, a verse section's fraction
    of root-degree (delta==0) hits should be measurably higher than a
    same-preset section that isn't verse."""
    metalcore = load_all_presets()["metalcore"]
    verse_root_fracs = []
    other_root_fracs = []
    for seed in range(20):
        song = _generate_attempt(random.Random(seed), metalcore, num_sections=8)
        for section in song["sections"]:
            deltas = section["motif"].deltas
            if not deltas:
                continue
            root_frac = sum(1 for d in deltas if d == 0) / len(deltas)
            if section["role"] == "verse":
                verse_root_fracs.append(root_frac)
            elif section["role"] not in ("chorus",):
                other_root_fracs.append(root_frac)
    assert verse_root_fracs, "expected at least one real verse section across 20 seeds"
    assert sum(verse_root_fracs) / len(verse_root_fracs) > sum(other_root_fracs) / len(other_root_fracs)


def test_chorus_sections_get_a_real_non_silent_lead():
    """X.31: chorus gets a real accompanying lead (lead_mode='chorus_lead'),
    unlike the other dense-chug roles (silent)."""
    metalcore = load_all_presets()["metalcore"]
    saw_chorus = False
    for seed in range(20):
        song = _generate_attempt(random.Random(seed), metalcore, num_sections=8)
        for section in song["sections"]:
            if section["role"] == "chorus":
                saw_chorus = True
                assert section["lead_mode"] == "chorus_lead"
                assert len(section["lead"]) > 0
                assert section["legato"] is None
    assert saw_chorus, "expected at least one real chorus section across 20 seeds"


def test_chorus_gets_a_real_chord_progression_but_verse_stays_single_note():
    from midi_export import _CHORD_THICKENED_ROLES

    assert "chorus" in _CHORD_THICKENED_ROLES
    assert "verse" not in _CHORD_THICKENED_ROLES


# ---------------------------------------------------------------------------
# Real synth-doubles-the-riff device (scope sec.16.1's own Born-of-Osiris
# research finding: "synth leads that double or harmonize with the guitar
# riff... not just atmospheric texture") for every dense-chug ("silent"
# lead_mode) section -- found unwired during a 2026-09-10 user listening
# session ("no melody... no synth... nothing"), traced to 7/10 sections of
# a real generated song having zero melodic voice by design.
#
# RETIRED 2026-09-11: direct user listening feedback ("I can't even tell
# it apart, there's so much spam") plus a real, measured count (a single
# verse: SIX voices, including this one, all locked to the identical 120
# rhythmic hits) confirmed this had become pure redundant stacking once
# `lead_mode = "ambient_lead"` (above) started giving every dense-chug
# section a genuinely independent melodic voice -- the exact role this
# synth-doubling device was originally built to fill, now filled better
# by something that isn't just a locked-rhythm copy of the riff. `atmosphere.
# synth_double` itself is untouched (still real, still tested in
# `test_atmosphere.py`) -- only the call site in `song.py`'s dense-chug
# branch was removed. `section["synth_double"]` is now unconditionally
# `[]` for every role, same real "not applicable" convention every other
# field already uses when a device doesn't apply.
# ---------------------------------------------------------------------------


def test_synth_double_is_always_empty_now_that_ambient_lead_fills_its_role():
    metalcore = load_all_presets()["metalcore"]
    song = _generate_attempt(random.Random(3), metalcore, num_sections=8)
    for section in song["sections"]:
        assert section["synth_double"] == []


# ---------------------------------------------------------------------------
# Real pedal/chug doubler guitar -- a genuinely SEPARATE second rhythm-
# guitar part (not another double-tracked copy of guitar_take_a/take_b),
# found via direct measurement of a real user-supplied Born-of-Osiris-
# style reference MIDI (2026-09-10): its own "Guitar 2" track was 95.9%
# root-note, tight low register -- see song._PEDAL_DOUBLE_WEIGHTS' own
# module comment for the full real citation.
# ---------------------------------------------------------------------------


def test_pedal_guitar_is_rhythmically_thinned_relative_to_the_main_guitar():
    """2026-09-11: the pedal guitar used to copy the main guitar's rhythm
    hit-for-hit (real, but confirmed via direct user listening feedback
    -- "so much spam" -- plus a real measured count of six voices locked
    to the identical rhythm in one section -- to be pure redundant
    stacking). `_thin_pedal_cells` now keeps every OTHER real hit: same
    overall cell grid (count/duration), but a real, genuinely SPARSER
    rhythm than the main guitar, and never a hit where the main guitar
    itself rests."""
    metalcore = load_all_presets()["metalcore"]
    song = _generate_attempt(random.Random(3), metalcore, num_sections=8)
    saw_a_real_thinned_section = False
    for section in song["sections"]:
        if section["role"] in ("chill", "interlude"):
            continue
        take_a = section["guitar_take_a"]
        pedal = section["guitar_pedal"]
        assert len(pedal) == len(take_a)
        main_hits = 0
        pedal_hits = 0
        for cell_a, cell_p in zip(take_a, pedal):
            # Duration is invariant under both thinning and X.24 blending
            # by construction -- the overall timing grid never changes.
            assert cell_a["duration"] == cell_p["duration"]
            # The pedal guitar must never hit where the main guitar rests
            # -- its own hits are strictly a subset of the main guitar's.
            if not cell_p["is_rest"]:
                assert not cell_a["is_rest"]
                pedal_hits += 1
            if not cell_a["is_rest"]:
                main_hits += 1
        if main_hits >= 8:
            saw_a_real_thinned_section = True
            assert pedal_hits < main_hits, (
                f"expected the pedal guitar to be genuinely sparser than the main "
                f"guitar, got {pedal_hits} pedal hits vs {main_hits} main hits"
            )
    assert saw_a_real_thinned_section, "expected at least one section with enough real hits to check thinning"


def test_pedal_guitar_pitches_are_real_and_fretboard_reachable():
    metalcore = load_all_presets()["metalcore"]
    song = _generate_attempt(random.Random(3), metalcore, num_sections=8)
    guitar_fb = song["guitar_fretboard"]
    saw_any = False
    for section in song["sections"]:
        ppc = section.get("pedal_pitches_per_cell") or []
        for p in ppc:
            if p is None:
                continue
            saw_any = True
            guitar_fb.pitch_to_fret(p, max_fret=guitar_fb.max_fret)
    assert saw_any, "expected at least one real pedal-guitar pitch across 8 sections"


def test_pedal_guitar_is_heavily_root_weighted_matching_the_real_measured_reference():
    """Real, statistical proof of `_PEDAL_DOUBLE_WEIGHTS`' own effect --
    not just a shape check. The reference measured 95.9% root; this
    checks the generated pedal guitar lands solidly in that same
    real ballpark (a generous >= 80% threshold, since a single seeded
    song is a small sample), never the near-even spread the MAIN
    riff's own preset vocab would produce."""
    from theory import Scale

    metalcore = load_all_presets()["metalcore"]
    song = _generate_attempt(random.Random(3), metalcore, num_sections=10)
    scale = Scale(root=song["guitar_fretboard"].tuning[0], name=metalcore.scale)
    root_pitch_classes = {scale.degree(0) % 12}

    total = 0
    root_count = 0
    for section in song["sections"]:
        for p in section.get("pedal_pitches_per_cell") or []:
            if p is None:
                continue
            total += 1
            if p % 12 in root_pitch_classes:
                root_count += 1
    assert total > 20, "expected substantial real pedal-guitar hit content across 10 sections"
    assert root_count / total >= 0.80


def test_pedal_guitar_absent_for_chill_and_interlude():
    chill = load_all_presets()["chill"]
    song = _generate_attempt(random.Random(3), chill, num_sections=8)
    for section in song["sections"]:
        if section["role"] in ("chill", "interlude"):
            assert section["guitar_pedal"] == []
            assert section["pedal_pitches_per_cell"] == []


def test_regenerate_section_pitch_mode_leaves_pedal_guitar_unchanged():
    """Same established precedent as `lead`/kick/snare/hihat/chord data in
    pitch-only regen: the pedal guitar's pitch is its own independent
    draw (not derived from the main guitar's pitch content the way bass
    is), so a "new notes, same hits" edit to the MAIN riff has no reason
    to touch it."""
    from song import regenerate_section

    metalcore = load_all_presets()["metalcore"]
    song = _generate_attempt(random.Random(3), metalcore, num_sections=4)
    index = next(i for i, s in enumerate(song["sections"]) if s["role"] not in ("chill", "interlude"))
    original_pedal = song["sections"][index]["guitar_pedal"]
    original_ppc = song["sections"][index]["pedal_pitches_per_cell"]

    new_song = regenerate_section(song, index, random.Random(99), metalcore, mode="pitch")
    assert new_song["sections"][index]["guitar_pedal"] == original_pedal
    assert new_song["sections"][index]["pedal_pitches_per_cell"] == original_ppc


def test_regenerate_section_full_mode_refreshes_pedal_guitar():
    from song import regenerate_section

    metalcore = load_all_presets()["metalcore"]
    song = _generate_attempt(random.Random(3), metalcore, num_sections=4)
    index = next(i for i, s in enumerate(song["sections"]) if s["role"] not in ("chill", "interlude"))

    new_song = regenerate_section(song, index, random.Random(99), metalcore, mode="full")
    new_section = new_song["sections"][index]
    assert len(new_section["guitar_pedal"]) == len(new_section["guitar_take_a"])
    assert len(new_section["pedal_pitches_per_cell"]) == len(new_section["guitar_pedal"])


# ---------------------------------------------------------------------------
# X.32 -- real per-role feel: breakdown forced, build gets real variety
# ---------------------------------------------------------------------------


def test_breakdown_role_always_gets_real_breakdown_feel_regardless_of_preset():
    """X.32: breakdown role is FORCED to real breakdown duration weighting
    even for a preset whose own declared .feel is something else entirely
    (tech = "triplet") -- not just metalcore, which happens to already
    declare "breakdown" as its own feel."""
    from rhythm import FEEL_DURATION_WEIGHTS

    tech = load_all_presets()["tech"]
    assert tech.feel == "triplet"
    saw_breakdown = False
    for seed in range(10):
        song = _generate_attempt(random.Random(seed), tech, num_sections=6)
        for section in song["sections"]:
            if section["role"] != "breakdown":
                continue
            saw_breakdown = True
            durations = {c["duration"] for c in section["motif"].cell}
            # Real breakdown weighting only ever produces the standard
            # [0.25, 0.5, 1.0] menu (or half of one of those values, from
            # X.19's real IRVD Destruction-bar densification), never a
            # genuine 1/3-beat triplet value (which tech's own declared
            # feel would otherwise produce).
            allowed = set(FEEL_DURATION_WEIGHTS["breakdown"])
            allowed |= {v / 2 for v in allowed}
            assert durations <= allowed
    assert saw_breakdown, "expected at least one real breakdown section across 10 seeds"


def test_build_role_shows_real_variety_across_gallop_stutter_chug_and_preset_feel():
    """X.32: build gets a real chance at gallop/stutter_chug on top of the
    preset's own declared feel -- across enough seeds, more than one of
    the three should actually occur."""
    djent = load_all_presets()["djent"]
    assert djent.feel == "bounce"
    seen_shapes = set()
    for seed in range(30):
        song = _generate_attempt(random.Random(seed), djent, num_sections=6)
        for section in song["sections"]:
            if section["role"] != "build":
                continue
            durations = [c["duration"] for c in section["motif"].cell]
            if len(durations) >= 3 and durations[:3] == [0.25, 0.25, 0.5]:
                seen_shapes.add("gallop")
            elif len(set(round(d, 9) for d in durations)) == 1:
                seen_shapes.add("stutter_chug")
            else:
                seen_shapes.add("preset_feel")
    assert len(seen_shapes) > 1, f"expected real variety across seeds, got only {seen_shapes}"


# ---------------------------------------------------------------------------
# X.34 -- real blast beats, wired into the actual drum track
# ---------------------------------------------------------------------------


def test_blast_fill_is_real_and_occasional_across_breakdown_and_solo():
    """X.34: across enough seeds, some breakdown/solo sections show a real
    blast (kick+snare alternating, cell-aligned with guitar) and some
    don't -- occasional, not universal."""
    deathcore = load_all_presets()["deathcore"]
    saw_blast = False
    saw_non_blast = False
    for seed in range(20):
        song = _generate_attempt(random.Random(seed), deathcore, num_sections=8)
        for section in song["sections"]:
            if section["role"] not in ("breakdown", "solo"):
                continue
            kick_hits = sum(1 for c in section["kick"] if not c["is_rest"])
            snare_hits = sum(1 for c in section["snare"] if not c["is_rest"])
            # A real blast section's kick/snare stay perfectly cell-aligned
            # with the guitar (the hard invariant judge()'s kick-lock zip
            # and every other consumer depend on).
            assert len(section["kick"]) == len(section["guitar_take_a"])
            assert len(section["snare"]) == len(section["guitar_take_a"])
            # Heuristic real-blast detector: a real blast shows measurably
            # MORE snare activity than the normal sparse backbeat
            # (snare_pattern_for_role's "step"/genre styles rarely exceed
            # a handful of hits per section).
            if snare_hits > 6 and kick_hits > 0:
                saw_blast = True
            else:
                saw_non_blast = True
    assert saw_blast, "expected at least one real blast section across 20 seeds"
    assert saw_non_blast, "expected at least one real NON-blast section across 20 seeds"


def test_blast_survives_cross_section_blending_still_cell_aligned():
    """X.34: a blast section's kick/snare must be correctly re-locked
    (same real blast type, not a fresh re-roll) after X.24's blend pass --
    never left stale or clobbered by the normal kick_style re-lock."""
    deathcore = load_all_presets()["deathcore"]
    for seed in range(20):
        song = _generate_attempt(random.Random(seed), deathcore, num_sections=8)
        for section in song["sections"]:
            if section["role"] not in ("breakdown", "solo"):
                continue
            # After blending, kick/snare must still be exactly cell-aligned
            # with the (now blended) guitar_take_a -- the real invariant
            # this whole design exists to preserve.
            assert len(section["kick"]) == len(section["guitar_take_a"])
            assert len(section["snare"]) == len(section["guitar_take_a"])
            assert [c["duration"] for c in section["kick"]] == [
                c["duration"] for c in section["guitar_take_a"]
            ]


# ---------------------------------------------------------------------------
# X.36 -- real melodic sequence passage spliced into solo sections
# ---------------------------------------------------------------------------


def test_solo_sections_include_a_real_spliced_sequence_passage():
    """X.36: a solo's lead notes must include a real, repeating-shape
    sequence passage (see lead.generate_sequence_line) between the main
    phrase and the legato tail -- not just move()/stab()-driven notes."""
    from theory import Scale

    djent = load_all_presets()["djent"]
    found = False
    for seed in range(20):
        song = _generate_attempt(random.Random(seed), djent, num_sections=10)
        for section in song["sections"]:
            if section["role"] != "solo":
                continue
            found = True
            legato = section["legato"]
            legato_len = len(legato["pitches"]) if legato else 0
            expected_min_len = (
                max(1, round(djent.bars * 4 * 2))  # main phrase (total_beats*2)
                + _SOLO_SEQUENCE_MOTIF_LEN * _SOLO_SEQUENCE_REPEATS
                + legato_len
            )
            assert len(section["lead"]) == expected_min_len
    assert found, "expected at least one real solo section across 20 seeds"


def test_solo_sequence_notes_stay_in_the_real_solo_register():
    djent = load_all_presets()["djent"]
    for seed in range(20):
        song = _generate_attempt(random.Random(seed), djent, num_sections=10)
        for section in song["sections"]:
            if section["role"] != "solo":
                continue
            # Every real lead note (main phrase, sequence, and legato
            # tail alike) must be a genuine MIDI pitch, never fabricated.
            assert all(isinstance(p, int) for p in section["lead"])


# ---------------------------------------------------------------------------
# P9.3 -- real single-section regeneration
# ---------------------------------------------------------------------------


def test_regenerate_section_pitch_mode_keeps_rhythm_changes_pitch():
    from song import regenerate_section

    metalcore = load_all_presets()["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=6)
    original = song["sections"][2]

    new_song = regenerate_section(song, 2, random.Random(42), metalcore, mode="pitch")
    new_section = new_song["sections"][2]

    assert new_section["motif"].cell == original["motif"].cell
    assert new_section["role"] == original["role"]
    assert len(new_section["kick"]) == len(new_section["guitar_take_a"])
    assert len(new_section["bass"]) == len(new_section["guitar_take_a"])
    # Real evidence the pitch layer actually changed (extremely unlikely
    # to coincidentally match exactly across a real reroll).
    assert new_section["motif"].deltas != original["motif"].deltas or new_section["pitches_per_cell"] != original["pitches_per_cell"]


def test_regenerate_section_rhythm_mode_changes_rhythm_keeps_alignment():
    from song import regenerate_section

    metalcore = load_all_presets()["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=6)

    new_song = regenerate_section(song, 2, random.Random(42), metalcore, mode="rhythm")
    new_section = new_song["sections"][2]

    assert len(new_section["kick"]) == len(new_section["guitar_take_a"])
    assert len(new_section["snare"]) == len(new_section["guitar_take_a"])
    assert len(new_section["bass"]) == len(new_section["guitar_take_a"])
    assert sum(c["duration"] for c in new_section["guitar_take_a"]) == pytest.approx(metalcore.bars * 4)


def test_regenerate_section_full_mode_is_a_real_fresh_section():
    from song import regenerate_section

    metalcore = load_all_presets()["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=6)

    new_song = regenerate_section(song, 2, random.Random(42), metalcore, mode="full")
    new_section = new_song["sections"][2]
    assert len(new_section["kick"]) == len(new_section["guitar_take_a"])
    assert sum(c["duration"] for c in new_section["guitar_take_a"]) == pytest.approx(metalcore.bars * 4)


def test_regenerate_section_role_override_converts_section_type():
    from song import regenerate_section

    metalcore = load_all_presets()["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=6)
    assert song["sections"][2]["role"] != "breakdown"

    new_song = regenerate_section(song, 2, random.Random(7), metalcore, mode="full", role="breakdown")
    assert new_song["sections"][2]["role"] == "breakdown"
    assert new_song["sequence"][2] == "breakdown"


def test_regenerate_section_hit_chance_bias_measurably_changes_density():
    from song import regenerate_section

    metalcore = load_all_presets()["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=6)
    original_hits = sum(1 for c in song["sections"][2]["guitar_take_a"] if not c["is_rest"])

    sparser = regenerate_section(song, 2, random.Random(7), metalcore, mode="rhythm", hit_chance_bias=-0.4)
    sparser_hits = sum(1 for c in sparser["sections"][2]["guitar_take_a"] if not c["is_rest"])
    assert sparser_hits < original_hits


def test_regenerate_section_does_not_mutate_the_original_song():
    from song import regenerate_section

    metalcore = load_all_presets()["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=6)
    original_cell = list(song["sections"][2]["motif"].cell)
    original_neighbor_kick = list(song["sections"][1]["kick"])

    regenerate_section(song, 2, random.Random(42), metalcore, mode="full")

    assert song["sections"][2]["motif"].cell == original_cell
    assert song["sections"][1]["kick"] == original_neighbor_kick


def test_regenerate_section_rejects_bad_input():
    from song import regenerate_section

    metalcore = load_all_presets()["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=6)
    with pytest.raises(ValueError):
        regenerate_section(song, 99, random.Random(1), metalcore)
    with pytest.raises(ValueError):
        regenerate_section(song, 0, random.Random(1), metalcore, mode="not-a-real-mode")


def test_regenerate_section_is_reproducible_with_same_regen_seed():
    from song import regenerate_section

    metalcore = load_all_presets()["metalcore"]
    song = compose_song("metalcore", seed=1, num_sections=6)
    a = regenerate_section(song, 2, random.Random(99), metalcore, mode="full")
    b = regenerate_section(song, 2, random.Random(99), metalcore, mode="full")
    assert a["sections"][2]["motif"].deltas == b["sections"][2]["motif"].deltas
    assert a["sections"][2]["motif"].cell == b["sections"][2]["motif"].cell


def test_compose_song_from_preset_works_with_a_real_blended_preset():
    from song import compose_song_from_preset
    from presets import blend_presets

    presets = load_all_presets()
    blended = blend_presets(presets["djent"], presets["deathcore"], 0.5)
    song = compose_song_from_preset(blended, seed=3, num_sections=6)
    assert song["sections"]
    assert song["judge"]["hits"] > 0


def test_compose_song_from_preset_reproducible_with_same_seed():
    from song import compose_song_from_preset

    preset = load_all_presets()["metalcore"]
    a = compose_song_from_preset(preset, seed=5, num_sections=4)
    b = compose_song_from_preset(preset, seed=5, num_sections=4)
    assert a["sequence"] == b["sequence"]


def test_compose_song_blast_fill_chance_override_is_real():
    """P9.2: blast_fill_chance is a real per-section coin-flip threshold
    (song._generate_one_section) -- 0.0 must never fire it, 1.0 must
    always fire it for a real eligible role, checked directly against the
    real per-section function rather than an indirect heuristic on the
    resulting drum density (which varies by preset/style already)."""
    from song import _generate_one_section
    from presets import load_all_presets
    from theory import Scale
    from fretboard import Fretboard
    from bass import build_bass_fretboard
    from presets import get_tuning, load_tunings

    preset = load_all_presets()["deathcore"]
    tunings = load_tunings()
    tuning = get_tuning(preset.tuning_key, tunings)
    guitar_fb = Fretboard(tuning.open)
    bass_fb = build_bass_fretboard(tuning.open)
    scale = Scale(root=tuning.open[0], name=preset.scale)

    def fresh_theme_source(key, *a, **kw):
        from motif import generate_motif
        return generate_motif(*a, **kw)

    for seed in range(10):
        _section, _kick, blast_type = _generate_one_section(
            random.Random(seed), preset, "breakdown", 0, scale, guitar_fb, bass_fb,
            16.0, False, None, fresh_theme_source, blast_fill_chance=0.0,
        )
        assert blast_type is None

        _section, _kick, blast_type = _generate_one_section(
            random.Random(seed), preset, "breakdown", 0, scale, guitar_fb, bass_fb,
            16.0, False, None, fresh_theme_source, blast_fill_chance=1.0,
        )
        assert blast_type is not None


# ---------------------------------------------------------------------------
# Real, verbatim riff-fragment bank for Born of Osiris ("labyrinth") ONLY --
# `_try_riff_bank_motif` must be a genuine no-op (byte-identical to the
# pre-existing Markov/statistical path) for every OTHER preset, and for
# `labyrinth` itself whenever no local bank file exists or the bank has no
# real fragments for the requested role (every automated test environment,
# and any fresh checkout -- the bank file is gitignored/local-only, see
# riff_bank.py's own docstring).
# ---------------------------------------------------------------------------

from riff_bank import RiffFragment


@pytest.fixture(autouse=True)
def _reset_riff_bank_cache():
    """`song._load_riff_bank` caches process-wide -- reset it before and
    after every test in this module so one test's monkeypatched bank path
    can never leak into another's."""
    import song

    song._riff_bank_cache = None
    yield
    song._riff_bank_cache = None


def _write_bank(tmp_path, fragments):
    import riff_bank

    path = tmp_path / "riff_bank.json"
    riff_bank.save_riff_bank(fragments, path)
    return path


_VERSE_FRAGMENT = RiffFragment(
    source_song="Fixture Song", source_file="fixture.gp5", measure_index=0,
    cell=[{"duration": 0.5, "is_rest": False} for _ in range(8)],
    deltas=[0, 2, -2, 0, 3, -3, 0, 1],
    role="verse", raw_marker="Verse",
)


def test_try_riff_bank_motif_is_none_for_every_non_labyrinth_preset(tmp_path, monkeypatch):
    import riff_bank
    from song import _try_riff_bank_motif
    from theory import Scale

    monkeypatch.setattr(riff_bank, "DEFAULT_RIFF_BANK_PATH", _write_bank(tmp_path, [_VERSE_FRAGMENT]))
    scale = Scale(root=0, name="minor")
    for preset_id in ALL_PRESET_IDS:
        if preset_id == "labyrinth":
            continue
        preset = load_all_presets()[preset_id]
        result = _try_riff_bank_motif(preset, "verse", scale, 0, 8.0, random.Random(1))
        assert result is None


def test_try_riff_bank_motif_is_none_without_a_real_bank_file_present(tmp_path, monkeypatch):
    import riff_bank
    from song import _try_riff_bank_motif
    from theory import Scale

    monkeypatch.setattr(riff_bank, "DEFAULT_RIFF_BANK_PATH", tmp_path / "does_not_exist.json")
    preset = load_all_presets()["labyrinth"]
    scale = Scale(root=0, name="minor")
    result = _try_riff_bank_motif(preset, "verse", scale, 0, 8.0, random.Random(1))
    assert result is None


def test_try_riff_bank_motif_is_none_without_consuming_extra_rng_when_unavailable():
    # The real, load-bearing guarantee: a checkout with no local bank file
    # must consume the EXACT SAME rng stream as before this feature
    # existed -- zero behavior change for anyone not opted in.
    from song import _try_riff_bank_motif
    from theory import Scale

    preset = load_all_presets()["deathcore"]  # not labyrinth
    scale = Scale(root=0, name="minor")
    rng = random.Random(1)
    _try_riff_bank_motif(preset, "verse", scale, 0, 8.0, rng)
    expected_next = random.Random(1).random()
    assert rng.random() == pytest.approx(expected_next)


def test_try_riff_bank_motif_returns_none_when_bank_has_no_fragments_for_role(tmp_path, monkeypatch):
    import riff_bank
    from song import _try_riff_bank_motif
    from theory import Scale

    monkeypatch.setattr(riff_bank, "DEFAULT_RIFF_BANK_PATH", _write_bank(tmp_path, [_VERSE_FRAGMENT]))
    preset = load_all_presets()["labyrinth"]
    scale = Scale(root=0, name="minor")
    result = _try_riff_bank_motif(preset, "breakdown", scale, 0, 8.0, random.Random(1))
    assert result is None


def test_try_riff_bank_motif_uses_the_real_bank_when_fragments_exist(tmp_path, monkeypatch):
    import riff_bank
    from song import _try_riff_bank_motif
    from theory import Scale

    monkeypatch.setattr(riff_bank, "DEFAULT_RIFF_BANK_PATH", _write_bank(tmp_path, [_VERSE_FRAGMENT]))
    preset = load_all_presets()["labyrinth"]
    scale = Scale(root=0, name="minor")
    result = _try_riff_bank_motif(preset, "verse", scale, 0, 4.0, random.Random(1))
    assert result is not None
    assert result.hit_count == len(result.deltas)


def test_generate_one_section_uses_the_real_riff_bank_for_labyrinth_when_available(tmp_path, monkeypatch):
    """End-to-end: `_generate_one_section` (not just the helper in
    isolation) actually wires a real bank motif into `labyrinth`'s guitar
    cells when a local bank file with matching-role fragments exists."""
    import riff_bank
    from song import _generate_one_section
    from theory import Scale
    from fretboard import Fretboard
    from bass import build_bass_fretboard
    from presets import get_tuning, load_tunings

    monkeypatch.setattr(riff_bank, "DEFAULT_RIFF_BANK_PATH", _write_bank(tmp_path, [_VERSE_FRAGMENT]))

    preset = load_all_presets()["labyrinth"]
    tunings = load_tunings()
    tuning = get_tuning(preset.tuning_key, tunings)
    guitar_fb = Fretboard(tuning.open)
    bass_fb = build_bass_fretboard(tuning.open)
    scale = Scale(root=tuning.open[0], name=preset.scale)

    def theme_source_that_must_not_be_called(*a, **kw):
        raise AssertionError("theme_source must not be called when the riff bank has real coverage")

    section, _kick, _blast = _generate_one_section(
        random.Random(1), preset, "verse", 0, scale, guitar_fb, bass_fb,
        4.0, False, None, theme_source_that_must_not_be_called,
    )
    assert len(section["guitar_take_a"]) == 8


def test_generate_one_section_seeds_riff_bank_theme_for_real_cross_section_reuse(tmp_path, monkeypatch):
    """The real fix for the earlier riff-model's own ThemeRegistry-bypass
    bug: a role's FIRST occurrence draws from the bank and seeds that
    result as the role's canonical base theme; a SECOND occurrence of the
    same role must NOT draw a second, unrelated bank motif -- it reuses/
    develops the seeded one via the normal `theme_source`/`_develop_theme`
    path, exactly like the Markov path already does."""
    import riff_bank
    from song import _generate_one_section
    from motif import ThemeRegistry
    from theory import Scale
    from fretboard import Fretboard
    from bass import build_bass_fretboard
    from presets import get_tuning, load_tunings

    monkeypatch.setattr(riff_bank, "DEFAULT_RIFF_BANK_PATH", _write_bank(tmp_path, [_VERSE_FRAGMENT]))

    calls = []
    real_select = riff_bank.select_and_resolve_motif

    def counting_select(*a, **kw):
        calls.append(1)
        return real_select(*a, **kw)

    monkeypatch.setattr(riff_bank, "select_and_resolve_motif", counting_select)

    preset = load_all_presets()["labyrinth"]
    tunings = load_tunings()
    tuning = get_tuning(preset.tuning_key, tunings)
    guitar_fb = Fretboard(tuning.open)
    bass_fb = build_bass_fretboard(tuning.open)
    scale = Scale(root=tuning.open[0], name=preset.scale)

    themes = ThemeRegistry()

    def shared_theme_source(key, *a, **kw):
        return themes.get_or_create(key, *a, **kw)

    for occurrence in (0, 1):
        _generate_one_section(
            random.Random(1), preset, "verse", occurrence, scale, guitar_fb, bass_fb,
            4.0, False, None, shared_theme_source, themes=themes,
        )

    assert len(calls) == 1  # the bank was consulted only on the real first occurrence
    assert "theme-verse" in themes  # the bank result was genuinely seeded into the registry
