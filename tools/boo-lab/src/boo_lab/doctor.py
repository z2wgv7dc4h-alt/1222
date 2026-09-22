"""`boo-lab doctor`: report what is installed, whether the GPU is visible, and
the exact command to fix anything missing.

This is the durable answer to "why did the intern fail on the new machine":
run it after setup and it names the gap instead of failing deep inside a model.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

CORE = ("librosa", "soundfile", "guitarpro", "demucs")
INTERNS = ("beat_this", "allin1", "jams", "mir_eval")
EXTRAS = {"torchcrepe": "pitch", "whisperx": "align"}

GPU_HINT = ('pip install torch torchaudio --index-url '
            'https://download.pytorch.org/whl/cu128')


def _has(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


def _line(name: str, ok: bool, note: str = "") -> bool:
    print(f"  [{'OK' if ok else '--'}] {name}" + (f"  {note}" if note else ""))
    return ok


def run_doctor(lab_root: Path | None = None, require_interns: bool = False) -> int:
    print("boo-lab doctor")
    print(f"  python {sys.version.split()[0]}")

    cuda = False
    try:
        import torch

        from . import device

        cuda = device.torch_device() == "cuda"
        gpu = device.gpu_name() if cuda else ""
        _line("torch", True, f"{torch.__version__}"
              + (f"  cuda=True  gpu={gpu}" if cuda else "  cuda=False"))
    except Exception as exc:  # noqa: BLE001
        _line("torch", False, repr(exc))

    print(" core:")
    core_ok = True
    for mod in CORE:
        core_ok &= _line(mod, _has(mod))

    print(" interns (structure/beats research):")
    intern_ok = True
    for mod in INTERNS:
        if mod == "allin1":
            from ._natten_compat import install

            install()
            intern_ok &= _line("allin1", _has("allin1"),
                               "natten legacy-API shim installed")
        else:
            intern_ok &= _line(mod, _has(mod))
    intern_ok &= _line("natten", _has("natten"))

    print(" extras:")
    for mod, extra in EXTRAS.items():
        _line(f"{mod}  (pip install -e \".[{extra}]\")", _has(mod))

    if lab_root is not None:
        print(" lab:")
        try:
            from .status import collect_counts

            c = collect_counts(lab_root)
        except Exception:
            c = None
        if c is not None:
            print("  keepers: %d row(s) across %d track(s)"
                  % (c["keeper_rows"], c["keeper_tracks"]))
            print("  holdout: %d song(s) reserved" % c.get("holdout_songs", 0))
            print("  identity: %d row(s)" % c.get("identity_rows", 0))
            if c.get("audit_warnings") is not None:
                print("  audit warnings: %d" % c["audit_warnings"])
            print("  prefer=: %s" % c.get("prefer", "none"))

    print(" hints:")
    if not cuda:
        print(f"  gpu: {GPU_HINT}")
    if not all(_has(m) for m in INTERNS):
        print('  interns: pip install -e ".[intern]"')
    print("  pitch:   pip install -e \".[pitch]\"")
    print("  align:   pip install -e \".[align]\"")
    if not core_ok:
        return 1
    if require_interns and not intern_ok:
        print("FAIL: --require-interns and an intern is missing (see hints above)")
        return 1
    return 0
