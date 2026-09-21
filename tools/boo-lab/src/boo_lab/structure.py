from __future__ import annotations

import json
from pathlib import Path


POP_ROLES = {
    "intro",
    "verse",
    "pre-chorus",
    "chorus",
    "bridge",
    "inst",
    "instrumental",
    "outro",
    "silence",
}


def relabel_breakdown(seg: dict) -> dict:
    """Placeholder: caller may attach stem stats later.

    If the analyze JSON already has half_time or kick_lock flags, promote to breakdown.
    """
    out = dict(seg)
    label = (out.get("label") or "").lower()
    if out.get("half_time") or out.get("kick_lock"):
        out["role"] = "breakdown"
        return out
    if label in {"chorus", "verse"} and out.get("energy") == "low":
        out["role"] = "chill"
        return out
    from .schema import msa_label_to_lab

    out["role"] = msa_label_to_lab(label)
    return out


def load_allin1_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def segments_from_allin1(result: dict) -> list[dict]:
    raw = result.get("segments") or result.get("paths") or []
    segs = []
    for s in raw:
        if isinstance(s, dict):
            segs.append(
                {
                    "start": float(s.get("start", s.get("begin", 0))),
                    "end": float(s.get("end", 0)),
                    "label": s.get("label") or s.get("function") or "",
                }
            )
    return [relabel_breakdown(s) for s in segs]


def run_allin1(flac: Path, cache_dir: Path | None = None) -> dict:
    from . import _natten_compat
    from .device import torch_device

    _natten_compat.install()
    import allin1  # optional extra

    kwargs: dict = {"device": torch_device(), "multiprocess": False}
    if cache_dir is not None:
        kwargs["demix_dir"] = str(Path(cache_dir) / "demix")
        kwargs["spec_dir"] = str(Path(cache_dir) / "spec")
    result = allin1.analyze(str(flac), **kwargs)
    if hasattr(result, "__dict__"):
        payload = {
            "bpm": getattr(result, "bpm", None),
            "beats": list(getattr(result, "beats", []) or []),
            "downbeats": list(getattr(result, "downbeats", []) or []),
            "segments": [
                {
                    "start": getattr(s, "start", 0),
                    "end": getattr(s, "end", 0),
                    "label": getattr(s, "label", ""),
                }
                if not isinstance(s, dict)
                else s
                for s in (getattr(result, "segments", None) or [])
            ],
        }
        return payload
    if isinstance(result, dict):
        return result
    return {"raw": str(result)}


def _songformer_repo() -> Path | None:
    """The official repo checkout (has `src/SongFormer/infer/infer.py`)."""
    import os

    home = os.environ.get("SONGFORMER_HOME")
    if not home:
        return None
    root = Path(home)
    if (root / "src" / "SongFormer" / "infer" / "infer.py").exists():
        return root
    return None


def songformer_available() -> bool:
    """Usable when the official repo env is configured (`SONGFORMER_HOME` +
    `SONGFORMER_PY` pointing at its own interpreter), or a plain `import
    songformer` works."""
    import os

    if _songformer_repo() and os.environ.get("SONGFORMER_PY"):
        return True
    try:
        import songformer  # noqa: F401
        return True
    except Exception:
        return False


def _run_songformer_subprocess(repo: Path, py: str, flac: Path) -> dict:
    """Run the official `infer.py` in its OWN env and read back its segments.
    Heavy (MuQ + MusicFM + SongFormer weights); only used when configured."""
    import os
    import subprocess
    import tempfile

    sf = Path(repo) / "src" / "SongFormer"
    with tempfile.TemporaryDirectory() as td:
        scp = Path(td) / "in.scp"
        scp.write_text(str(Path(flac).resolve()) + "\n", encoding="utf-8")
        out = Path(td) / "out"
        out.mkdir()
        cmd = [
            py, str(sf / "infer" / "infer.py"), "-i", str(scp), "-o", str(out),
            "-gn", "1", "-tn", "1", "--model", "SongFormer",
            "--checkpoint", "SongFormer.safetensors", "--config_path", "SongFormer.yaml",
        ]
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONPATH"] = os.pathsep.join([
            str(sf), str(Path(repo) / "src" / "third_party"), env.get("PYTHONPATH", ""),
        ])
        # EMA load + one-track infer is usually <2 min on a 5080. A hung
        # "Loading EMA" (CUDA wedge) used to block START forever because the
        # old 1800s timeout still left orphan multiprocessing children on the
        # GPU. Fail closed per track and kill the whole tree.
        try:
            timeout = float(os.environ.get("BOO_SONGFORMER_TIMEOUT_SEC") or "360")
        except ValueError:
            timeout = 360.0
        kwargs = dict(cwd=str(sf), env=env)
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        proc = subprocess.Popen(cmd, **kwargs)
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    check=False, capture_output=True,
                )
            else:
                proc.kill()
            proc.wait(timeout=30)
            raise RuntimeError(
                "SongFormer timed out after %.0fs (EMA/infer hang); "
                "set BOO_SONGFORMER_TIMEOUT_SEC to raise" % timeout
            )
        if rc != 0:
            raise RuntimeError("SongFormer exited with code %s" % rc)
        produced = list(out.glob("*.json"))
        if not produced:
            raise RuntimeError("SongFormer produced no output")
        return {"segments": json.loads(produced[0].read_text(encoding="utf-8"))}


def run_songformer(flac: Path) -> dict:
    """Best-effort SongFormer inference -> a dict with `segments`. With the
    official repo configured (`SONGFORMER_HOME` + `SONGFORMER_PY`) this shells
    out to its own env's `infer.py`; otherwise it falls back to an in-process
    `songformer` module. Fails closed per track."""
    import os

    repo = _songformer_repo()
    py = os.environ.get("SONGFORMER_PY")
    if repo is not None and py:
        return _run_songformer_subprocess(repo, py, flac)
    import songformer

    model = None
    loader = getattr(songformer, "load_model", None)
    if callable(loader):
        model = loader()
    else:
        cls = getattr(songformer, "SongFormer", None)
        if cls is not None:
            model = cls()
    if model is None:
        raise RuntimeError("songformer API not recognized (no load_model/SongFormer)")
    for name in ("analyze", "infer", "predict", "segment"):
        fn = getattr(model, name, None)
        if callable(fn):
            out = fn(str(flac))
            return out if isinstance(out, dict) else {"segments": out}
    if callable(model):
        out = model(str(flac))
        return out if isinstance(out, dict) else {"segments": out}
    raise RuntimeError("songformer model exposes no analyze/infer/predict")


def segments_from_songformer(result: dict) -> list[dict]:
    """Same normalization/label mapping as the allin1 segments."""
    return segments_from_allin1(result)


def build_drafts(lab_root: Path, rows: list[dict]) -> dict:
    """Write MSA (allin1) and, when available, SongFormer machine drafts to
    `data/drafts.jsonl`. NEVER writes `sections.jsonl`. Drafts for tracks not
    in `rows` (e.g. another album) are preserved."""
    from .schema import canonical_role, stamp_box, write_jsonl_atomic

    lab_root = Path(lab_root)
    out_dir = lab_root / "work" / "msa"
    out_dir.mkdir(parents=True, exist_ok=True)
    draft_path = lab_root / "data" / "drafts.jsonl"
    draft_path.parent.mkdir(parents=True, exist_ok=True)

    row_keys = {(r.get("album"), r.get("track")) for r in rows}
    keep: list[dict] = []
    if draft_path.exists():
        for line in draft_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if (rec.get("album"), rec.get("track")) in row_keys:
                continue
            keep.append(rec)

    use_songformer = songformer_available()
    new_recs: list[dict] = []
    # Tracks that already have stamped drafts for cached models — skip rewrite noise.
    drafted_msa: set[tuple[str, str]] = set()
    drafted_sf: set[tuple[str, str]] = set()
    if draft_path.exists():
        for line in draft_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (rec.get("album") or "", rec.get("track") or "")
            src = rec.get("source") or ""
            if src == "msa-draft":
                drafted_msa.add(key)
            elif src == "songformer-draft":
                drafted_sf.add(key)

    for r in rows:
        fp = r.get("flac_path")
        if not fp or not Path(fp).exists():
            print("SKIP structure", r.get("track"), "no flac")
            continue

        album = r.get("album") or ""
        track = r.get("track") or ""
        key = (album, track)
        msa_path = out_dir / f"{r.get('track')}.json"
        sf_path = out_dir / f"{r.get('track')}.songformer.json"
        msa_cached = msa_path.exists()
        sf_cached = sf_path.exists()
        # Fully warm: model JSON on disk and drafts already stamped — keep prior
        # draft rows for this track (do not drop them via row_keys filter alone).
        if (msa_cached and key in drafted_msa
                and ((not use_songformer) or (sf_cached and key in drafted_sf))):
            # Preserve this track's drafts (stripped above by row_keys filter).
            if draft_path.exists():
                for line in draft_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if (rec.get("album") or "", rec.get("track") or "") == key:
                        if rec.get("source") in {"msa-draft", "songformer-draft"}:
                            new_recs.append(rec)
            print("CACHE structure", track, "(drafts unchanged)")
            continue

        payload = None
        if msa_cached:
            try:
                payload = json.loads(msa_path.read_text(encoding="utf-8"))
                print("CACHE allin1", r.get("track"))
            except Exception:
                payload = None
        if payload is None:
            try:
                payload = run_allin1(Path(fp), cache_dir=lab_root / "work" / "allin1")
            except Exception as exc:
                print("SKIP structure", r.get("track"), exc)
                payload = None
            if payload is not None:
                msa_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        if payload is not None:
            for seg in segments_from_allin1(payload):
                role = canonical_role(seg.get("role") or seg.get("label"))
                if role is None:
                    continue  # unmapped label: never fabricate a role
                new_recs.append(stamp_box(
                    seg["start"], seg["end"], role,
                    source="msa-draft",
                    extra={"album": r.get("album"), "track": r.get("track"),
                           "msa_label": seg.get("label") or ""},
                ))
            print("DRAFT", r.get("track"), payload.get("bpm"), "-> data/drafts.jsonl")

        if use_songformer:
            sf_path = out_dir / f"{r.get('track')}.songformer.json"
            sres = None
            if sf_path.exists():
                try:
                    sres = json.loads(sf_path.read_text(encoding="utf-8"))
                    print("CACHE songformer", r.get("track"))
                except Exception:
                    sres = None
            if sres is None:
                try:
                    sres = run_songformer(Path(fp))
                except Exception as exc:
                    print("SKIP songformer", r.get("track"), exc)
                    sres = None
                if sres is not None:
                    sf_path.write_text(json.dumps(sres, indent=2, default=str), encoding="utf-8")
            if sres is not None:
                for seg in segments_from_songformer(sres):
                    role = canonical_role(seg.get("role") or seg.get("label"))
                    if role is None:
                        continue  # unmapped label: never fabricate a role
                    new_recs.append(stamp_box(
                        seg["start"], seg["end"], role,
                        source="songformer-draft",
                        extra={"album": r.get("album"), "track": r.get("track"),
                               "msa_label": seg.get("label") or "",
                               "source_model": "songformer"},
                    ))
                print("SONGFORMER", r.get("track"), "-> data/drafts.jsonl")

    # Per-album calibration: nudge/remap the intern drafts before they land,
    # so the studio and later reads see the calibrated box. Flag each row so a
    # later Load does not apply the same shift twice.
    if new_recs:
        try:
            from .adapt import apply_adapt, load_adapt

            blobs: dict = {}
            calibrated: list[dict] = []
            for rec in new_recs:
                alb = rec.get("album")
                if alb not in blobs:
                    blobs[alb] = load_adapt(lab_root, alb)
                calibrated.extend(apply_adapt([rec], blobs[alb]))
            new_recs = calibrated
            for blob in blobs.values():
                if blob and int(blob.get("n_pairs") or 0) >= 1:
                    print("adapt: intern drafts n_pairs=%d" % int(blob["n_pairs"]))
        except Exception:
            pass

    # Non-destructive on a zero-row run (same discipline as `beats`): a failed
    # or no-op structure pass must never blank a good `data/drafts.jsonl`.
    # Atomic replace only when something was actually produced.
    if new_recs:
        write_jsonl_atomic(draft_path, keep + new_recs)
    else:
        print("structure: 0 drafts written; leaving existing", draft_path.name, "untouched")
    # Ranking only: if the intern rank prefers a source this command emits,
    # say so. Other sources are never dropped; a missing rank changes nothing.
    try:
        from .learn import preferred_source

        prefer = preferred_source(lab_root)
        if prefer in {"msa-draft", "songformer-draft"}:
            print("prefer=%s" % prefer)
    except Exception:
        pass
    return {"written": len(new_recs), "out": str(draft_path), "songformer": use_songformer}
