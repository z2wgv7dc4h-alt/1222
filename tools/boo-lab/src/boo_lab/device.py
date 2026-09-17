"""Torch device selection: CUDA when a real GPU + CUDA build is present,
else CPU. One place every torch/GPU call site reads from."""
from __future__ import annotations


def torch_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def gpu_name() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return str(torch.cuda.get_device_name(0))
    except Exception:
        pass
    return ""
