"""`doctor` is the new-machine safety net: it must always run, name the
torch/GPU state, and never raise even when optional interns are absent."""
from __future__ import annotations

from boo_lab import doctor


def test_run_doctor_prints_state_and_returns_code(capsys, tmp_path):
    rc = doctor.run_doctor(tmp_path)
    out = capsys.readouterr().out
    assert "boo-lab doctor" in out
    assert "torch" in out
    assert "core:" in out
    assert "interns" in out
    assert rc in (0, 1)


def test_doctor_checks_all_known_interns():
    assert set(doctor.INTERNS) == {"beat_this", "allin1", "jams", "mir_eval"}
    assert "torchcrepe" in doctor.EXTRAS
    assert "whisperx" in doctor.EXTRAS
