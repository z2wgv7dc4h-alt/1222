import numpy as np
import pytest
import soundfile as sf

from audio_vocab import analyze_track, tonal_descriptor


def _write_click_track(path, sr=22050, bpm=120.0, duration_s=8.0, bright=True):
    """A synthetic click track: short bursts of noise/tone on a steady
    beat grid, so tests don't depend on any real audio file being present
    (mirrors midi_vocab.py's synthetic-in-memory-MIDI test strategy)."""
    n_samples = int(sr * duration_s)
    y = np.zeros(n_samples, dtype=np.float32)
    beat_period = 60.0 / bpm
    click_freq = 4000.0 if bright else 300.0
    click_len = int(sr * 0.03)
    t_click = np.arange(click_len) / sr
    click_wave = 0.8 * np.sin(2 * np.pi * click_freq * t_click) * np.exp(-t_click * 40)

    t = 0.0
    while t < duration_s:
        start = int(t * sr)
        end = min(n_samples, start + click_len)
        y[start:end] += click_wave[: end - start]
        t += beat_period

    sf.write(str(path), y, sr)


def test_analyze_track_recovers_approximate_tempo(tmp_path):
    path = tmp_path / "click.wav"
    _write_click_track(path, bpm=120.0, duration_s=10.0)
    result = analyze_track(path, n_sections=4)
    # Beat tracking on a pure click grid is approximate (librosa may lock
    # onto a half/double-tempo multiple) -- accept any octave of the true
    # tempo, but it must be a real detected tempo, not garbage/zero.
    assert result["tempo_bpm"] > 0
    ratio = result["tempo_bpm"] / 120.0
    assert any(abs(ratio - m) < 0.15 for m in (0.5, 1.0, 2.0))


def test_analyze_track_returns_expected_shape(tmp_path):
    path = tmp_path / "click.wav"
    _write_click_track(path, bpm=100.0, duration_s=6.0)
    result = analyze_track(path, n_sections=3)
    assert set(result.keys()) == {
        "duration_s", "tempo_bpm", "n_beats", "percussive_onsets_per_beat",
        "harmonic_onsets_per_beat", "mean_spectral_centroid_hz",
        "tonal_descriptor", "section_density_curve",
    }
    assert len(result["section_density_curve"]) == 3
    assert result["duration_s"] == pytest.approx(6.0, abs=0.05)


def test_analyze_track_rejects_bad_n_sections(tmp_path):
    path = tmp_path / "click.wav"
    _write_click_track(path, duration_s=2.0)
    with pytest.raises(ValueError):
        analyze_track(path, n_sections=0)
    with pytest.raises(ValueError):
        analyze_track(path, n_sections=-1)


def test_tonal_descriptor_buckets():
    assert tonal_descriptor(500.0) == "dark/scooped"
    assert tonal_descriptor(2500.0) == "balanced"
    assert tonal_descriptor(5000.0) == "bright/aggressive"


def test_analyze_track_density_curve_flags_a_denser_section(tmp_path):
    """Build a track that's sparse for the first half and dense for the
    second half; the density curve should reflect that real structural
    difference, not just noise."""
    sr = 22050
    duration_s = 8.0
    path = tmp_path / "sparse_then_dense.wav"
    n_samples = int(sr * duration_s)
    y = np.zeros(n_samples, dtype=np.float32)
    click_len = int(sr * 0.02)
    t_click = np.arange(click_len) / sr
    click_wave = 0.8 * np.sin(2 * np.pi * 3000 * t_click) * np.exp(-t_click * 50)

    def add_click(t):
        start = int(t * sr)
        end = min(n_samples, start + click_len)
        y[start:end] += click_wave[: end - start]

    # Sparse half: one click per second. Dense half: 8 clicks per second.
    t = 0.0
    while t < duration_s / 2:
        add_click(t)
        t += 1.0
    t = duration_s / 2
    while t < duration_s:
        add_click(t)
        t += 0.125

    sf.write(str(path), y, sr)
    result = analyze_track(path, n_sections=2)
    sparse_rel, dense_rel = result["section_density_curve"]
    assert dense_rel > sparse_rel
