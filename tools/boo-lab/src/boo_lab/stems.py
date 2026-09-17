from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def find_drums(flac: Path, cache: Path) -> Path | None:
    name = flac.stem
    for model in ("htdemucs_6s", "htdemucs", "htdemucs_ft", "mdx_extra", "mdx_extra_q"):
        p = cache / model / name / "drums.wav"
        if p.exists():
            return p
    near = [
        flac.parent / "stems" / (name + ".drums.wav"),
        flac.parent / "stems" / "drums.wav",
        flac.parent / (name + ".drums.wav"),
    ]
    for p in near:
        if p.exists():
            return p
    return None


def stem_dir(flac: Path, cache: Path, model: str = "htdemucs_6s") -> Path:
    return cache / model / flac.stem


def find_stem(flac: Path, cache: Path, name: str) -> Path | None:
    # htdemucs_6s first: its separate guitar.wav/piano.wav cache layout is
    # preferred, while any existing 4-stem htdemucs cache stays valid (and
    # is still found, just not preferred) -- forward-only, never deleted.
    for model in ("htdemucs_6s", "htdemucs", "htdemucs_ft", "mdx_extra"):
        p = cache / model / flac.stem / f"{name}.wav"
        if p.exists():
            return p
    return None


def run_demucs(
    flac: Path,
    out_dir: Path,
    model: str = "htdemucs_6s",
    two_stems: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "demucs", "-n", model, "-o", str(out_dir)]
    if two_stems:
        cmd += ["--two-stems", two_stems]
    cmd.append(str(flac))
    # Real corpus paths contain non-cp1252 characters ("∆"); without a UTF-8
    # IO env the demucs subprocess crashes printing the track path.
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    subprocess.run(cmd, check=True, timeout=900, env=env)
    return out_dir / model / flac.stem


def try_roformer_vocals(flac: Path, cache: Path) -> tuple[Path | None, str]:
    """Optional better vocal stem. Needs: pip install audio-separator"""
    dest = cache / "roformer" / flac.stem / "vocals.wav"
    if dest.exists():
        return dest, "cached roformer vocals"
    try:
        from audio_separator.separator import Separator
    except Exception:
        return None, "roformer not installed (pip install audio-separator) — using demucs"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        sep = Separator(output_dir=str(dest.parent))
        sep.load_model(model_filename="vocals_mel_band_roformer.ckpt")
        sep.separate(str(flac))
    except Exception as e:
        return None, "roformer: %s" % e
    hits = list(dest.parent.glob("*Vocal*.wav")) + list(dest.parent.glob("*vocals*.wav"))
    if hits:
        if hits[0] != dest:
            import shutil

            shutil.copy2(hits[0], dest)
        return dest, "roformer vocals"
    return None, "roformer wrote nothing"


def ensure_drums(flac: Path, cache: Path) -> tuple[Path | None, str]:
    hit = find_drums(flac, cache)
    if hit:
        return hit, "cached drums"
    try:
        import demucs  # noqa: F401
    except ImportError:
        return None, "pip install demucs"
    try:
        run_demucs(flac, cache)
    except Exception as e:
        return None, "demucs: %s" % e
    hit = find_drums(flac, cache)
    return hit, "demucs drums" if hit else "demucs wrote nothing"
