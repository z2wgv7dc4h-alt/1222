"""GPU auto-selection must never silently fall back to CPU when CUDA is
available -- that was the actual cause of the "why is this on CPU" slowdown."""
from __future__ import annotations

import sys
import types

from boo_lab import device


def _fake_torch(available: bool, name: str = "FakeGPU"):
    return types.SimpleNamespace(
        cuda=types.SimpleNamespace(
            is_available=lambda: available,
            get_device_name=lambda i: name,
        )
    )


def test_cuda_is_selected_when_available(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(True))
    assert device.torch_device() == "cuda"
    assert device.gpu_name() == "FakeGPU"


def test_cpu_when_cuda_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(False))
    assert device.torch_device() == "cpu"
    assert device.gpu_name() == ""


def test_cpu_when_torch_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    assert device.torch_device() == "cpu"
