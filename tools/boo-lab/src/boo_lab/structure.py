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


def songformer_available() -> bool:
    """`SONGFORMER_HOME` set, or `import songformer` works."""
    import os

    if os.environ.get("SONGFORMER_HOME"):
        return True
    try:
        import songformer  # noqa: F401
        return True
    except Exception:
        return False


def run_songformer(flac: Path) -> dict:
    """Best-effort SongFormer inference -> a dict with `segments`. The exact
    model API is resolved at call time so a missing/renamed entry point fails
    closed per track rather than crashing the run."""
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
    for r in rows:
        fp = r.get("flac_path")
        if not fp or not Path(fp).exists():
            print("SKIP structure", r.get("track"), "no flac")
            continue

        try:
            payload = run_allin1(Path(fp), cache_dir=lab_root / "work" / "allin1")
        except Exception as exc:
            print("SKIP structure", r.get("track"), exc)
            payload = None
        if payload is not None:
            (out_dir / f"{r.get('track')}.json").write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8")
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
            try:
                sres = run_songformer(Path(fp))
            except Exception as exc:
                print("SKIP songformer", r.get("track"), exc)
                sres = None
            if sres is not None:
                (out_dir / f"{r.get('track')}.songformer.json").write_text(
                    json.dumps(sres, indent=2, default=str), encoding="utf-8")
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
