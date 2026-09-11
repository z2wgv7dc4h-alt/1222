from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_demucs(flac: Path, out_dir: Path, model: str = "htdemucs_ft") -> Path:
    """Local Demucs only. Model default is 4-stem (vocals/drums/bass/other)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "demucs",
        "-n",
        model,
        "-o",
        str(out_dir),
        str(flac),
    ]
    subprocess.run(cmd, check=True)
    # demucs writes out_dir/model/songname/*.wav
    song = flac.stem
    return out_dir / model / song
