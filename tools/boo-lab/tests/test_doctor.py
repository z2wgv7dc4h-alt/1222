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


def test_require_interns_fails_when_missing(monkeypatch):
    monkeypatch.setattr(doctor, "_has", lambda m: m in doctor.CORE)
    assert doctor.run_doctor() == 0
    assert doctor.run_doctor(require_interns=True) == 1


def test_doctor_empty_gold_reports_zero_keepers_and_exits_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "_has", lambda m: True)

    rc = doctor.run_doctor(tmp_path)

    out = capsys.readouterr().out
    assert rc == 0                                   # empty gold is valid
    assert "keepers: 0 row(s) across 0 track(s)" in out
    assert "prefer=: none" in out


def test_doctor_reports_cuda_from_device(tmp_path, monkeypatch, capsys):
    import boo_lab.device as device

    monkeypatch.setattr(device, "torch_device", lambda: "cuda")
    monkeypatch.setattr(device, "gpu_name", lambda: "FakeGPU")
    monkeypatch.setattr(doctor, "_has", lambda m: True)

    doctor.run_doctor(tmp_path)

    out = capsys.readouterr().out
    assert "cuda=True" in out and "FakeGPU" in out
