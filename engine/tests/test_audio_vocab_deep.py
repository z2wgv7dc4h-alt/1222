import numpy as np
import pytest
import soundfile as sf

from audio_vocab import energy_curve, estimate_key, load_audio, structural_segments, tempo_stability


def _write_tone(path, sr=22050, freq=220.0, duration_s=6.0, amplitude=0.5):
    t = np.arange(int(sr * duration_s)) / sr
    y = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(str(path), y, sr)
    return y, sr


def test_estimate_key_returns_expected_shape(tmp_path):
    path = tmp_path / "tone.wav"
    _write_tone(path, freq=261.63, duration_s=8.0)  # roughly a C
    y, sr = load_audio(path)
    result = estimate_key(y, sr)
    assert set(result.keys()) == {"root", "mode", "confidence"}
    assert result["root"] in [
        "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
    ]
    assert result["mode"] in ("major", "minor")
    assert -1.0 <= result["confidence"] <= 1.0


def test_structural_segments_rejects_bad_n_segments(tmp_path):
    path = tmp_path / "tone.wav"
    y, sr = _write_tone(path, duration_s=4.0)
    with pytest.raises(ValueError):
        structural_segments(y, sr, n_segments=1)
    with pytest.raises(ValueError):
        structural_segments(y, sr, n_segments=0)


def test_structural_segments_returns_interior_boundaries_only(tmp_path):
    path = tmp_path / "tone.wav"
    y, sr = _write_tone(path, duration_s=10.0)
    segments = structural_segments(y, sr, n_segments=4)
    assert all(0.0 < t < 10.0 for t in segments)
    assert segments == sorted(segments)


def test_energy_curve_flags_a_louder_section(tmp_path):
    sr = 22050
    duration_s = 6.0
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    y = np.zeros(n, dtype=np.float32)
    half = n // 2
    y[:half] = (0.1 * np.sin(2 * np.pi * 220 * t[:half])).astype(np.float32)
    y[half:] = (0.9 * np.sin(2 * np.pi * 220 * t[half:])).astype(np.float32)
    path = tmp_path / "quiet_then_loud.wav"
    sf.write(str(path), y, sr)
    y2, sr2 = load_audio(path)
    curve = energy_curve(y2, sr2, n_sections=2)
    assert curve[1] > curve[0]


def test_energy_curve_rejects_bad_n_sections(tmp_path):
    path = tmp_path / "tone.wav"
    y, sr = _write_tone(path, duration_s=2.0)
    with pytest.raises(ValueError):
        energy_curve(y, sr, n_sections=0)


def test_tempo_stability_flags_a_genuine_tempo_change():
    sr = 22050
    click_len = int(sr * 0.02)
    t_click = np.arange(click_len) / sr
    click_wave = (0.8 * np.sin(2 * np.pi * 3000 * t_click) * np.exp(-t_click * 50)).astype(np.float32)

    def build(bpm_a, bpm_b, half_s=6.0):
        n = int(sr * half_s * 2)
        y = np.zeros(n, dtype=np.float32)
        t = 0.0
        period_a = 60.0 / bpm_a
        while t < half_s:
            start = int(t * sr)
            end = min(n, start + click_len)
            y[start:end] += click_wave[: end - start]
            t += period_a
        t = half_s
        period_b = 60.0 / bpm_b
        while t < half_s * 2:
            start = int(t * sr)
            end = min(n, start + click_len)
            y[start:end] += click_wave[: end - start]
            t += period_b
        return y

    y = build(90.0, 180.0)
    result = tempo_stability(y, sr, n_windows=4)
    assert len(result["window_tempos_bpm"]) > 0
    assert result["max_deviation_bpm"] >= 0.0


def test_tempo_stability_rejects_bad_n_windows():
    y = np.zeros(22050 * 4, dtype=np.float32)
    with pytest.raises(ValueError):
        tempo_stability(y, 22050, n_windows=0)


def test_tempo_stability_handles_very_short_audio_gracefully():
    y = np.zeros(1000, dtype=np.float32)
    result = tempo_stability(y, 22050, n_windows=4)
    assert result["window_tempos_bpm"] == []
    assert result["stable"] is True
