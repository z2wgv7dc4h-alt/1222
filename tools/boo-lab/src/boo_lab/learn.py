"""Intern-rank spine -- which draft source is worth trusting, from keepers.

Machines still never label: this only ranks the machine draft sources
(`guess` / `msa-draft` / `songformer-draft`) against human keeper pins, using
the existing `compare.compare()` boundary F-scores. A source is only preferred
once it has >= 5 non-holdout songs that carry BOTH keepers and drafts, clears
F@0.5 >= 0.50, and beats the next source by >= 0.03. Holdout songs are scored
but never vote. Writes `data/intern_rank.json` and appends events to
`data/learn.jsonl`; never writes `sections.jsonl`, never trains torch, never
fits a model on mixed FLACs. The old `enough_to_train`/`role_prior` trainer
gate is gone.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

KINDS = frozenset({
    "save_snapshot", "compare_source", "figure_agree",
    "sync_rate", "agree_pass", "policy",
})
MIN_VOTED = 5
MIN_F05 = 0.50
MARGIN = 0.03


def record(lab_root, kind, album="", track="", **payload) -> None:
    """Append one event to `data/learn.jsonl`. NEVER raises into the caller --
    a broken learn log must not break Save (or anything else)."""
    try:
        path = Path(lab_root) / "data" / "learn.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": round(time.time(), 3), "kind": kind, "album": album,
               "track": track, "payload": payload}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _ensure_compare(lab_root: Path) -> dict:
    """`compare.json` when fresh; otherwise rebuild it with `compare.compare()`
    (never a second F@0.5/F@3 implementation)."""
    lab_root = Path(lab_root)
    cpath = lab_root / "data" / "compare.json"
    inputs = [lab_root / "data" / "sections.jsonl", lab_root / "data" / "drafts.jsonl"]
    stale = not cpath.exists()
    if not stale:
        try:
            ctime = cpath.stat().st_mtime
        except OSError:
            stale = True
        else:
            for p in inputs:
                if p.exists() and p.stat().st_mtime > ctime:
                    stale = True
                    break
    if not stale:
        try:
            return json.loads(cpath.read_text(encoding="utf-8"))
        except Exception:
            pass
    from .compare import compare, write_report

    report = compare(lab_root)
    try:
        write_report(report, cpath)
    except Exception:
        pass
    return report


def _f(matched_ref: int, n_ref: int, matched_pred: int, n_pred: int) -> float:
    p = matched_pred / n_pred if n_pred else 0.0
    r = matched_ref / n_ref if n_ref else 0.0
    return round((2 * p * r / (p + r)) if (p + r) else 0.0, 4)


def _qualifying(report: dict, include_holdout: bool) -> list[dict]:
    out = []
    for t in report.get("tracks") or []:
        if not include_holdout and (t.get("split") in {"holdout", "val"}):
            continue
        if not (int(t.get("n_keep") or 0) > 0 and int(t.get("n_draft") or 0) > 0):
            continue
        out.append(t)
    return out


def _aggregate(tracks: list[dict]) -> dict:
    """Micro-F per source from the per-track precision/recall compare already
    wrote (pooled matched/n counts reconstructed; no reimplementation)."""
    agg: dict[str, dict] = {}
    for t in tracks:
        src = t.get("source") or ""
        a = agg.setdefault(src, {"m05": 0, "n05r": 0, "p05": 0, "n05p": 0,
                                 "m30": 0, "n30r": 0, "p30": 0, "n30p": 0,
                                 "role_same": 0, "role_pairs": 0, "n": 0})
        n_keep = int(t.get("n_keep") or 0)
        n_draft = int(t.get("n_draft") or 0)
        n_ref, n_pred = 2 * n_keep, 2 * n_draft
        a["n05r"] += n_ref
        a["n05p"] += n_pred
        a["n30r"] += n_ref
        a["n30p"] += n_pred
        a["m05"] += round(float(t.get("recall_0_5") or 0.0) * n_ref)
        a["p05"] += round(float(t.get("precision_0_5") or 0.0) * n_pred)
        a["m30"] += round(float(t.get("recall_3_0") or 0.0) * n_ref)
        a["p30"] += round(float(t.get("precision_3_0") or 0.0) * n_pred)
        pairs = int(t.get("hit_pairs_3_0") or 0)
        a["role_pairs"] += pairs
        a["role_same"] += round(float(t.get("role_agree_3_0") or 0.0) * pairs)
        a["n"] += 1
    scores: dict[str, dict] = {}
    for src, a in agg.items():
        scores[src] = {
            "f05": _f(a["m05"], a["n05r"], a["p05"], a["n05p"]),
            "f3": _f(a["m30"], a["n30r"], a["p30"], a["n30p"]),
            "role3": round(a["role_same"] / a["role_pairs"], 4) if a["role_pairs"] else 0.0,
            "n": a["n"],
        }
    return scores


def _choose(scores: dict) -> tuple[str, str]:
    qualifying = [(src, s) for src, s in scores.items()
                  if s["n"] >= MIN_VOTED and s["f05"] >= MIN_F05]
    if not qualifying:
        return "none", ("no draft source has >=%d non-holdout songs with keepers+drafts "
                        "and F@0.5>=%.2f" % (MIN_VOTED, MIN_F05))
    qualifying.sort(key=lambda kv: (-kv[1]["f05"], kv[0]))
    best_src, best = qualifying[0]
    if len(qualifying) > 1 and best["f05"] - qualifying[1][1]["f05"] < MARGIN:
        return "none", ("%s F@0.5=%.3f does not beat %s by >=%.2f"
                        % (best_src, best["f05"], qualifying[1][0], MARGIN))
    return best_src, "%s leads F@0.5=%.3f (n=%d)" % (best_src, best["f05"], best["n"])


def _write_rank(lab_root: Path, rank: dict) -> None:
    from .schema import write_jsonl_atomic

    # A one-line JSON document is valid JSON; reuse the one atomic writer.
    write_jsonl_atomic(Path(lab_root) / "data" / "intern_rank.json", [rank])


def figure_agree(lab_root) -> dict:
    """Read-only: keeper boxes that carry a `figure_id` vs `figures.jsonl`.
    Never renames a box."""
    from .schema import is_keeper

    figs: dict[tuple, list[dict]] = defaultdict(list)
    for r in _read_jsonl(Path(lab_root) / "data" / "figures.jsonl"):
        figs[(r.get("album"), r.get("track"))].append(r)
    match = miss = 0
    for rec in _read_jsonl(Path(lab_root) / "data" / "sections.jsonl"):
        if not (is_keeper(rec.get("source")) and rec.get("heard") is True):
            continue
        fid = rec.get("figure_id")
        rows = figs.get((rec.get("album"), rec.get("track")))
        if not rows or not fid:
            continue
        if any(r.get("figure_id") == fid for r in rows):
            match += 1
        else:
            miss += 1
    conflict = sum(1 for rows in figs.values() for r in rows if r.get("conflict"))
    return {"match": match, "miss": miss, "conflict": conflict}


def sync_rate(lab_root) -> dict:
    rows = _read_jsonl(Path(lab_root) / "data" / "sync.jsonl")
    total = len(rows)
    ok = sum(1 for r in rows if r.get("sync_ok") is True)
    return {"total": total, "ok": ok, "rate": round(ok / total, 3) if total else 0.0}


def agree_pass(lab_root) -> dict | None:
    """Pass-1 vs pass-2 numbers, via agree.py's own `diff_passes`. `None` when
    there is no song with both passes (or agree.py is unavailable)."""
    try:
        from .agree import diff_passes
    except Exception:
        return None
    passes: dict[tuple, dict] = defaultdict(dict)
    for rec in _read_jsonl(Path(lab_root) / "data" / "agree.jsonl"):
        passes[(rec.get("album"), rec.get("track"))][rec.get("pass")] = rec.get("boxes") or []
    both = [(v.get(1), v.get(2)) for v in passes.values()
            if v.get(1) is not None and v.get(2) is not None]
    if not both:
        return None
    h05 = h30 = 0.0
    for p1, p2 in both:
        d = diff_passes(p1, p2)
        h05 += d["boundary_hit_0_5"]
        h30 += d["boundary_hit_3_0"]
    n = len(both)
    return {"songs": n, "boundary_hit_0_5": round(h05 / n, 3),
            "boundary_hit_3_0": round(h30 / n, 3)}


def build_rank(lab_root) -> dict:
    """Rank the machine draft sources from keepers. Writes intern_rank.json."""
    lab_root = Path(lab_root)
    report = _ensure_compare(lab_root)
    voted = _qualifying(report, include_holdout=False)
    hold = _qualifying(report, include_holdout=True)
    hold = [t for t in hold if t.get("split") in {"holdout", "val"}]
    scores = _aggregate(voted)
    prefer, reason = _choose(scores)
    rank = {
        "prefer": prefer,
        "scores": scores,
        "n_voted": len({(t.get("album"), t.get("track")) for t in voted}),
        "holdout": _aggregate(hold),
        "ts": round(time.time(), 3),
        "reason": reason,
    }
    _write_rank(lab_root, rank)
    return rank


def preferred_source(lab_root) -> str | None:
    """The ranked winner, or `None` when no rank file exists / prefer is none."""
    try:
        data = json.loads((Path(lab_root) / "data" / "intern_rank.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    prefer = data.get("prefer")
    return prefer if prefer and prefer != "none" else None


def run_learn(lab_root, album=None) -> dict:
    """Rebuild the rank, append the read-only events + one policy event."""
    rank = build_rank(lab_root)
    for src, s in rank["scores"].items():
        record(lab_root, "compare_source", album or "", "", source=src, **s)
    fa = figure_agree(lab_root)
    record(lab_root, "figure_agree", album or "", "", **fa)
    sr = sync_rate(lab_root)
    record(lab_root, "sync_rate", album or "", "", **sr)
    ap = agree_pass(lab_root)
    if ap:
        record(lab_root, "agree_pass", album or "", "", **ap)
    record(lab_root, "policy", album or "", "",
           prefer=rank["prefer"], reason=rank["reason"], n_voted=rank["n_voted"])
    rank["figure_agree"] = fa
    rank["sync_rate"] = sr
    if ap:
        rank["agree_pass"] = ap
    return rank
