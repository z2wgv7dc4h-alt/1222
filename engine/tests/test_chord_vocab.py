import pytest

from chord_vocab import (
    CHORD_QUALITIES,
    DISSONANCE_ORDER,
    get_chord_quality,
    quality_for_dissonance,
    voice_named_chord,
)
from fretboard import Fretboard
from presets import load_tunings
from song import compose_song


# --- named quality table -----------------------------------------------------


def test_get_chord_quality_returns_documented_intervals():
    assert get_chord_quality("maj7") == (0, 4, 7, 11)
    assert get_chord_quality("min7") == (0, 3, 7, 10)


def test_get_chord_quality_rejects_unknown_name():
    with pytest.raises(ValueError):
        get_chord_quality("not-a-real-quality")


@pytest.mark.parametrize("quality", sorted(CHORD_QUALITIES.keys()))
def test_every_named_quality_has_a_real_fingering_on_a_real_tuning(quality):
    """Every quality in the table must produce an actual, reachable
    fingering on at least one REAL tuning from presets.json data (not a
    synthetic fretboard) -- rooted at one of that tuning's own open
    strings, so no note is fabricated."""
    tunings = load_tunings()
    found = False
    for tuning in tunings.values():
        fb = Fretboard(tuning.open, max_fret=24)
        for root in tuning.open:
            try:
                fingering = voice_named_chord(root, quality, fb, max_span=4)
            except ValueError:
                continue
            found = True
            assert fingering
            assert len(fingering) == len(CHORD_QUALITIES[quality])
            for string, fret in fingering:
                assert 0 <= string < len(fb.tuning)
                assert 0 <= fret <= fb.max_fret
                pitch = fb.fret_to_midi(string, fret)
                # Every returned position is real: it round-trips through
                # the fretboard's own reverse lookup.
                assert (string, fret) in fb.midi_to_frets(pitch)
            break
        if found:
            break
    assert found, f"quality {quality!r} was unreachable on every real tuning"


# --- fail-closed behavior -----------------------------------------------------


def test_voice_named_chord_rejects_unknown_quality():
    fb = Fretboard(load_tunings()["standard_6"].open, max_fret=24)
    with pytest.raises(ValueError):
        voice_named_chord(40, "not-a-real-quality", fb)


def test_voice_named_chord_propagates_unreachable_chord_failure():
    """A genuinely unreachable chord (max_span far too small for a 5-note
    extended voicing) must raise -- never return a fabricated/partial
    shape, matching voice_chord_section's own contract."""
    tuning = load_tunings()["standard_6"]
    fb = Fretboard(tuning.open, max_fret=24)
    with pytest.raises(ValueError):
        voice_named_chord(tuning.open[0], "maj9", fb, max_span=0)


# --- dissonance -> quality mapping --------------------------------------------


def test_quality_for_dissonance_spans_the_documented_order():
    assert quality_for_dissonance(0.0) == DISSONANCE_ORDER[0]
    assert quality_for_dissonance(1.0) == DISSONANCE_ORDER[-1]
    # Monotonic bucket index: higher dissonance never maps to an earlier
    # (more consonant) bucket than a lower dissonance value.
    prev_idx = -1
    for tenth in range(11):
        d = tenth / 10.0
        idx = DISSONANCE_ORDER.index(quality_for_dissonance(d))
        assert idx >= prev_idx
        prev_idx = idx


def test_quality_for_dissonance_clamps_out_of_range_input():
    assert quality_for_dissonance(-5.0) == DISSONANCE_ORDER[0]
    assert quality_for_dissonance(5.0) == DISSONANCE_ORDER[-1]


# --- end-to-end wiring into song.py (X.6b) ------------------------------------


def test_compose_song_gives_chill_and_interlude_sections_real_chord_voicings():
    """A real, checked seed/preset combo whose generated sequence includes
    both `chill` and `interlude` roles (song.py's `lead_mode == "harmony"`
    branch) -- confirms the chord-voicing wiring is an ALWAYS-EXERCISED
    call path for those roles, not a standalone function nothing calls."""
    song = compose_song("djent", seed=0, num_sections=6)
    guitar_fb = song["guitar_fretboard"]

    roles = [s["role"] for s in song["sections"]]
    assert "chill" in roles or "interlude" in roles

    harmony_sections = [s for s in song["sections"] if s["role"] in ("chill", "interlude")]
    assert harmony_sections, "expected at least one chill/interlude section for this seed"

    saw_real_voicing = False
    for section in harmony_sections:
        assert section["lead_mode"] == "harmony"
        # chord_quality/chord_voicing are always present keys, never
        # silently missing.
        assert "chord_quality" in section
        assert "chord_voicing" in section
        if section["chord_voicing"] is None:
            # Fail-closed is a legitimate outcome (an unreachable extended
            # voicing on this preset's tuning) -- but the quality name
            # must still be real.
            assert section["chord_quality"] in CHORD_QUALITIES
            continue
        saw_real_voicing = True
        assert section["chord_quality"] in CHORD_QUALITIES
        voicing = section["chord_voicing"]
        assert len(voicing) == len(CHORD_QUALITIES[section["chord_quality"]])
        for string, fret in voicing:
            # Every position must be real and playable on the SONG's own
            # guitar_fretboard -- not just any fretboard.
            assert 0 <= string < len(guitar_fb.tuning)
            assert 0 <= fret <= guitar_fb.max_fret
            pitch = guitar_fb.fret_to_midi(string, fret)
            assert (string, fret) in guitar_fb.midi_to_frets(pitch)

    assert saw_real_voicing, "expected at least one section to get a real (non-None) chord voicing"


def test_compose_song_other_roles_leave_chord_voicing_none():
    song = compose_song("djent", seed=0, num_sections=6)
    for section in song["sections"]:
        if section["role"] not in ("chill", "interlude"):
            assert section["chord_quality"] is None
            assert section["chord_voicing"] is None
