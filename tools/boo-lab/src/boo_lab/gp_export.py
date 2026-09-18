"""GP7 / .gpx import probe -- record what cannot feed markers.

LAW: GP7 is not a Guess marker clock. `.gp`/`.gpx` may feed extract and figure
hashes only after a real, deterministic export to GP5, and there is no such
converter here (pyguitarpro cannot write GP7, no Guitar Pro CLI is installed),
so this command never invents a GP7 writer. It instead probes each `.gp`/`.gpx`
under the GP root: a file pyguitarpro can already parse works in `extract`/`scan`
(so it just tells you to run `scan`), and anything else is recorded with a
stable reason in `data/gp_export.jsonl`. Never writes `sections.jsonl`.
"""
from __future__ import annotations

import shutil
from pathlib import Path

GP7_EXTS = (".gpx", ".gp")


def find_files(gp_root) -> list[Path]:
    """Every real `.gp` / `.gpx` under `gp_root` (recursive)."""
    if not gp_root:
        return []
    root = Path(gp_root)
    if not root.exists():
        return []
    found: set[Path] = set()
    for ext in GP7_EXTS:
        found.update(root.rglob("*" + ext))
    return sorted(found)


def find_converter() -> str | None:
    """A real Guitar Pro CLI / converter on PATH, if one is installed. None
    here -- so nothing is exported and no binary writer is invented."""
    for name in ("guitarpro", "guitar-pro", "gpconvert", "gp7-convert", "tuxguitar"):
        exe = shutil.which(name)
        if exe:
            return exe
    return None


def classify(path, riff_bank=None) -> tuple[bool, str]:
    """`(ok, reason)`. A `.gpx` -- or a ZIP-container `.gp` (`.gpx` content
    under a `.gp` name) -- can never be read by pyguitarpro, so it is
    `gpx-unsupported`; anything else that fails parse is `gp7-unsupported`.
    A file that parses already works in `extract`, so `ok` means "run scan"."""
    path = Path(path)
    if riff_bank is None:
        from .extract import _engine_riff_bank

        riff_bank = _engine_riff_bank()
    if path.suffix.lower() == ".gpx" or riff_bank._is_zip_container(path):
        return False, "gpx-unsupported"
    try:
        riff_bank.extract_fragments_from_file(path, song_title=path.stem)
        return True, ""
    except Exception as exc:  # noqa: BLE001 - real unparseable GP7 files exist
        reason = riff_bank.classify_failure_reason(str(exc))
        return False, "gpx-unsupported" if reason == "gpx_unsupported" else "gp7-unsupported"


def export_gp(lab_root, gp_root) -> dict:
    """Probe every `.gp`/`.gpx` under `gp_root`; record the unsupported ones.

    Writes `data/gp_export.jsonl` (the unsupported rows) when the root exists
    and real files were found. A missing/empty root is reported, not blanked."""
    lab_root = Path(lab_root)
    out = lab_root / "data" / "gp_export.jsonl"
    root = Path(gp_root) if gp_root else None
    converter = find_converter()
    files = find_files(root)
    ok: list[str] = []
    unsupported: list[dict] = []
    if files:
        from .extract import _engine_riff_bank

        riff_bank = _engine_riff_bank()
        for path in files:
            good, reason = classify(path, riff_bank)
            if good:
                ok.append(str(path))
            else:
                unsupported.append(
                    {"path": str(path), "ext": path.suffix.lower(), "reason": reason}
                )
    wrote = False
    if files and root is not None and root.exists():
        from .schema import write_jsonl_atomic

        write_jsonl_atomic(out, unsupported)
        wrote = True
    return {
        "gp_root": str(root) if root else "",
        "converter": converter,
        "scanned": len(files),
        "ok": ok,
        "unsupported": unsupported,
        "wrote": wrote,
        "out": str(out),
    }
