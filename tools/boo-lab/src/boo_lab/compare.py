"""Read-only comparison of machine drafts vs human keeper pins.

Drafts (`data/drafts.jsonl`, msa-draft/guess) are scored against the saved
keeper boxes (`data/sections.jsonl`) at 0.5s and 3.0s boundary tolerance:
precision / recall / F, plus role agreement on 3.0s hit pairs.

Never writes `sections.jsonl` or `drafts.jsonl`; the only output is a
`compare.json` report. Not a model -- a boundary/label audit.
"""
from __future__ import annotations

import json
from pathlib import Path

from .holdout import load_holdout, split_for
from .schema import canonical_role, is_keeper, msa_label_to_lab

DRAFT_SOURCES = frozenset({"msa-draft", "guess", "songformer-draft"})


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _norm_role(role: str | None) -> str:
    return canonical_role(msa_label_to_lab(role))


def keeper_rows(lab_root: Path) -> tuple[dict[tuple[str, str], list[dict]], int]:
    """`(by_song, warned)` -- keeper rows are `is_keeper(source)` AND
    `heard is True`. A legacy row with no source counts as keeper when heard
    is True; when `heard` is itself missing it is treated as a keeper for
    this read-only command and counted in `warned`."""
    by_song: dict[tuple[str, str], list[dict]] = {}
    warned = 0
    for rec in _read_jsonl(Path(lab_root) / "data" / "sections.jsonl"):
        source = rec.get("source")
        heard = rec.get("heard")
        if source is None or source == "":
            if heard is False:
                continue
            if heard is None:
                warned += 1
        else:
            if not is_keeper(source) or heard is not True:
                continue
        key = (rec.get("album") or "", rec.get("track") or "")
        by_song.setdefault(key, []).append(rec)
    return by_song, warned


def draft_rows(lab_root: Path) -> dict[tuple[str, str], dict[str, list[dict]]]:
    """`{(album,track): {source: [boxes]}}` for every draft source."""
    by_song: dict[tuple[str, str], dict[str, list[dict]]] = {}
    for rec in _read_jsonl(Path(lab_root) / "data" / "drafts.jsonl"):
        source = rec.get("source") or ""
        if source not in DRAFT_SOURCES:
            continue
        key = (rec.get("album") or "", rec.get("track") or "")
        by_song.setdefault(key, {}).setdefault(source, []).append(rec)
    return by_song


def _boundaries(boxes: list[dict]) -> list[float]:
    out: list[float] = []
    for b in boxes:
        out.append(float(b.get("start", 0.0)))
        out.append(float(b.get("end", 0.0)))
    return out


def _hit_counts(ref: list[dict], pred: list[dict], tol: float) -> dict:
    r = _boundaries(ref)
    p = _boundaries(pred)
    matched_r = sum(1 for x in r if any(abs(x - y) <= tol for y in p))
    matched_p = sum(1 for y in p if any(abs(x - y) <= tol for x in r))
    precision = matched_p / len(p) if p else 0.0
    recall = matched_r / len(r) if r else 0.0
    f = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"matched_ref": matched_r, "n_ref": len(r),
            "matched_pred": matched_p, "n_pred": len(p),
            "precision": precision, "recall": recall, "f": f}


def _hit_pairs(ref: list[dict], pred: list[dict], tol: float) -> list[tuple[int, int]]:
    """Greedy one-to-one pairing by nearest start within `tol` seconds."""
    cand: list[tuple[float, int, int]] = []
    for i, k in enumerate(ref):
        ks = float(k.get("start", 0.0))
        for j, d in enumerate(pred):
            delta = abs(ks - float(d.get("start", 0.0)))
            if delta <= tol:
                cand.append((delta, i, j))
    cand.sort(key=lambda t: (t[0], t[1], t[2]))
    used_r: set[int] = set()
    used_p: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _d, i, j in cand:
        if i in used_r or j in used_p:
            continue
        used_r.add(i)
        used_p.add(j)
        pairs.append((i, j))
    return pairs


def _role_agreement(ref: list[dict], pred: list[dict], tol: float = 3.0) -> tuple[float, int]:
    pairs = _hit_pairs(ref, pred, tol)
    if not pairs:
        return 0.0, 0
    same = sum(1 for i, j in pairs if _norm_role(ref[i].get("role")) == _norm_role(pred[j].get("role")))
    return same / len(pairs), len(pairs)


def compare_song(keepers: list[dict], drafts: list[dict]) -> dict:
    out: dict = {"n_keep": len(keepers), "n_draft": len(drafts)}
    counts: dict[str, dict] = {}
    for tol, key in ((0.5, "0_5"), (3.0, "3_0")):
        c = _hit_counts(keepers, drafts, tol)
        counts[key] = c
        out["precision_" + key] = round(c["precision"], 4)
        out["recall_" + key] = round(c["recall"], 4)
        out["f_" + key] = round(c["f"], 4)
    ra, pair_n = _role_agreement(keepers, drafts, 3.0)
    out["role_agree_3_0"] = round(ra, 4)
    out["hit_pairs_3_0"] = pair_n
    out["_counts"] = counts  # for micro-average; stripped before writing
    return out


def compare(lab_root: Path, album: str | None = None, track: str | None = None) -> dict:
    """Read-only report over every song that has BOTH keepers and drafts."""
    lab_root = Path(lab_root)
    keepers_by, warned = keeper_rows(lab_root)
    drafts_by = draft_rows(lab_root)
    holdout = load_holdout(lab_root)

    tracks: list[dict] = []
    micro = {
        "0_5": {"matched_ref": 0, "n_ref": 0, "matched_pred": 0, "n_pred": 0},
        "3_0": {"matched_ref": 0, "n_ref": 0, "matched_pred": 0, "n_pred": 0},
        "role_same": 0, "role_pairs": 0,
    }
    for key in sorted(set(keepers_by) & set(drafts_by)):
        a, t = key
        if album and a != album:
            continue
        if track and t != track:
            continue
        # One row per draft source, so a second intern prints its own row.
        for source in sorted(drafts_by[key]):
            m = compare_song(keepers_by[key], drafts_by[key][source])
            c = m.pop("_counts")
            for k in ("0_5", "3_0"):
                for f in ("matched_ref", "n_ref", "matched_pred", "n_pred"):
                    micro[k][f] += c[k][f]
            micro["role_pairs"] += m["hit_pairs_3_0"]
            micro["role_same"] += round(m["role_agree_3_0"] * m["hit_pairs_3_0"])
            m["album"] = a
            m["track"] = t
            m["source"] = source
            m["split"] = "holdout" if split_for(a, t, holdout) == "val" else "train"
            tracks.append(m)

    def _f(c: dict) -> float:
        p = c["matched_pred"] / c["n_pred"] if c["n_pred"] else 0.0
        r = c["matched_ref"] / c["n_ref"] if c["n_ref"] else 0.0
        return round((2 * p * r / (p + r)) if (p + r) else 0.0, 4)

    distinct_tracks = len({(t["album"], t["track"]) for t in tracks})
    micro_out = {
        "n_tracks": distinct_tracks,
        "n_rows": len(tracks),
        "f_0_5": _f(micro["0_5"]),
        "f_3_0": _f(micro["3_0"]),
        "role_agree_3_0": round(micro["role_same"] / micro["role_pairs"], 4) if micro["role_pairs"] else 0.0,
    }
    return {"tracks": tracks, "micro": micro_out, "warned_legacy_heard_missing": warned}


def format_report(report: dict) -> str:
    lines = ["%-28s %-8s %-15s %6s %7s %6s %6s %8s %s" % (
        "album", "track", "source", "n_keep", "n_draft", "F0.5", "F3", "role3", "split")]
    for t in report["tracks"]:
        lines.append("%-28s %-8s %-15s %6d %7d %6.3f %6.3f %8.3f %s" % (
            (t["album"] or "")[:28], (t["track"] or "")[:8], (t.get("source") or "")[:15],
            t["n_keep"], t["n_draft"], t["f_0_5"], t["f_3_0"], t["role_agree_3_0"], t["split"]))
    m = report["micro"]
    lines.append("micro (tracks=%d rows=%d): F0.5=%.3f F3=%.3f role3=%.3f"
                 % (m["n_tracks"], m["n_rows"], m["f_0_5"], m["f_3_0"], m["role_agree_3_0"]))
    if report.get("warned_legacy_heard_missing"):
        lines.append("warning: %d legacy keeper row(s) had no heard flag (treated as keepers)"
                     % report["warned_legacy_heard_missing"])
    return "\n".join(lines)


def write_report(report: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
