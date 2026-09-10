import importlib.util

import numpy as np
import pytest
import soundfile as sf

from audio_vocab import transcribe_and_split_registers

_BASIC_PITCH_AVAILABLE = importlib.util.find_spec("basic_pitch") is not None


def test_transcribe_and_split_registers_raises_clear_error_without_basic_pitch(tmp_path, monkeypatch):
    """Regardless of whether basic_pitch happens to be installed in THIS
    environment, the function must fail with a clear, actionable
    ImportError (not a confusing transitive-dependency traceback) when it
    isn't available -- simulate that by blocking the import."""
    import builtins
    real_import = builtins.__import__

    def blocking_import(name, *args, **kwargs):
        if name == "basic_pitch" or name.startswith("basic_pitch."):
            raise ImportError("simulated missing basic_pitch")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocking_import)
    path = tmp_path / "tone.wav"
    sf.write(str(path), np.zeros(22050, dtype=np.float32), 22050)
    with pytest.raises(ImportError, match="basic_pitch"):
        transcribe_and_split_registers(path)


@pytest.mark.skipif(not _BASIC_PITCH_AVAILABLE, reason="basic_pitch not installed in this environment (optional dependency)")
def test_transcribe_and_split_registers_returns_expected_shape(tmp_path):
    sr = 22050
    duration_s = 3.0
    t = np.arange(int(sr * duration_s)) / sr
    # A low tone (rhythm-register) and a higher tone (lead-register) mixed.
    low = 0.5 * np.sin(2 * np.pi * 110.0 * t)  # ~A2, MIDI 45
    high = 0.3 * np.sin(2 * np.pi * 440.0 * t)  # ~A4, MIDI 69
    y = (low + high).astype(np.float32)
    path = tmp_path / "mixed.wav"
    sf.write(str(path), y, sr)

    result = transcribe_and_split_registers(path, rhythm_cutoff_midi=52)
    assert set(result.keys()) == {"rhythm", "lead"}
    for layer in result.values():
        assert set(layer.keys()) == {
            "n_notes", "density_per_s", "avg_duration_s", "pitch_class_counts", "pitch_class_sequence",
        }
