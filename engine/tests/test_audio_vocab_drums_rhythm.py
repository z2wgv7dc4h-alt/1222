import numpy as np
import pytest
import soundfile as sf

from audio_vocab import classify_drum_onsets, guitar_rhythm_pattern, load_audio


def _burst(sr, freq, duration_s=0.05, amp=0.9):
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    return (amp * np.sin(2 * np.pi * freq * t) * np.exp(-t * 30)).astype(np.float32)


def test_classify_drum_onsets_distinguishes_kick_snare_hihat(tmp_path):
    sr = 22050
    duration_s = 4.0
    n = int(sr * duration_s)
    y = np.zeros(n, dtype=np.float32)
    kick = _burst(sr, 60.0)
    snare = (0.7 * np.random.default_rng(0).standard_normal(len(kick))).astype(np.float32) * np.exp(
        -np.arange(len(kick)) / len(kick) * 5
    ).astype(np.float32)
    hihat = _burst(sr, 9000.0)

    def place(wave, t):
        start = int(t * sr)
        end = min(n, start + len(wave))
        y[start:end] += wave[: end - start]

    place(kick, 0.5)
    place(snare, 1.5)
    place(hihat, 2.5)

    path = tmp_path / "kshh.wav"
    sf.write(str(path), y, sr)
    y2, sr2 = load_audio(path)
    results = classify_drum_onsets(y2, sr2)

    roles_by_time = {round(r["time"]): r["role"] for r in results}
    assert roles_by_time.get(0) == "KICK" or roles_by_time.get(1) == "KICK"
    assert "HIHAT_OR_CYMBAL" in [r["role"] for r in results]


def test_classify_drum_onsets_empty_signal_returns_empty(tmp_path):
    sr = 22050
    y = np.zeros(sr * 2, dtype=np.float32)
    path = tmp_path / "silence.wav"
    sf.write(str(path), y, sr)
    y2, sr2 = load_audio(path)
    assert classify_drum_onsets(y2, sr2) == []


def test_guitar_rhythm_pattern_detects_straight(tmp_path):
    sr = 22050
    duration_s = 6.0
    n = int(sr * duration_s)
    y = np.zeros(n, dtype=np.float32)
    click = _burst(sr, 200.0, duration_s=0.03)
    t = 0.0
    while t < duration_s:
        start = int(t * sr)
        end = min(n, start + len(click))
        y[start:end] += click[: end - start]
        t += 0.25  # perfectly even spacing
    path = tmp_path / "straight.wav"
    sf.write(str(path), y, sr)
    y2, sr2 = load_audio(path)
    result = guitar_rhythm_pattern(y2, sr2)
    assert result["pattern"] == "straight"


def test_guitar_rhythm_pattern_detects_gallop(tmp_path):
    sr = 22050
    duration_s = 8.0
    n = int(sr * duration_s)
    y = np.zeros(n, dtype=np.float32)
    click = _burst(sr, 200.0, duration_s=0.03)
    t = 0.0
    # short-short-long, repeating: 0.15, 0.15, 0.3 seconds
    pattern = [0.15, 0.15, 0.3]
    i = 0
    while t < duration_s:
        start = int(t * sr)
        end = min(n, start + len(click))
        y[start:end] += click[: end - start]
        t += pattern[i % 3]
        i += 1
    path = tmp_path / "gallop.wav"
    sf.write(str(path), y, sr)
    y2, sr2 = load_audio(path)
    result = guitar_rhythm_pattern(y2, sr2)
    assert result["pattern"] == "gallop"


def test_guitar_rhythm_pattern_insufficient_onsets(tmp_path):
    sr = 22050
    y = np.zeros(sr * 2, dtype=np.float32)
    path = tmp_path / "silence.wav"
    sf.write(str(path), y, sr)
    y2, sr2 = load_audio(path)
    result = guitar_rhythm_pattern(y2, sr2)
    assert result["pattern"] == "insufficient_onsets"
