"""Per-album calibration from the first accepted drafts, plus a corpus-wide
cold-start fallback for an album that has none of its own yet.

When the human Saves keepers, remember how those boxes differ from the drafts
that were on that song: a median edge shift (seconds), an intern-role ->
saved-role map, a draft/suggested figure_id -> saved figure_id map, and the
median heard-breakdown span. The NEXT Guess on that album applies those to
its draft boxes. This is calibration, not electing an intern (learn.py still
uses its 5-song vote) and not training. Drafts only: keepers are detected and
skipped, `heard` is never ticked, and `sections.jsonl` is never written.
`data/adapt.json` is generated/local.

A brand-new album has zero keeper-vs-draft pairs of its own, so its
per-album blob never arms (`n_pairs < 1`) -- `rebuild_global` pools every
non-holdout album's pairs into one blob under `GLOBAL_KEY`, and `load_adapt`
falls back to it only when the requested album has no armed blob of its own.
Shift/role/breakdown-span are real personal habits that plausibly generalize
across albums (timing feel, what you call a Hook, how long a real breakdown
runs); `figures` is deliberately NEVER pooled globally -- a figure_id like
`riff-A` is a per-song identifier, and remapping it across unrelated songs
would inject noise, not signal. Once an album earns its own armed blob, that
takes over completely; the global blob is a cold-start prior, not a blend.
"""
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

PAIR_TOL = 3.0
CLAMP = 0.50
DRAFT_SOURCES = frozenset({
    "guess", "msa-draft", "songformer-draft", "keeper-model",
    "gp-marker", "tabnotes-density", "tabnotes-structure", "tabnotes-phrase",
})
GLOBAL_KEY = "__global__"


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


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _clamp(x: float) -> float:
    return max(-CLAMP, min(CLAMP, x))


def _pair(keepers: list[dict], drafts: list[dict], tol: float = PAIR_TOL) -> list[tuple[dict, dict]]:
    """Greedy one-to-one pairing by nearest start within `tol` (same idea as
    compare's `_hit_pairs`)."""
    cand: list[tuple[float, int, int]] = []
    for i, k in enumerate(keepers):
        ks = float(k.get("start", 0.0))
        for j, d in enumerate(drafts):
            delta = abs(ks - float(d.get("start", 0.0)))
            if delta <= tol:
                cand.append((delta, i, j))
    cand.sort(key=lambda t: (t[0], t[1], t[2]))
    used_k: set[int] = set()
    used_d: set[int] = set()
    pairs: list[tuple[dict, dict]] = []
    for _delta, i, j in cand:
        if i in used_k or j in used_d:
            continue
        used_k.add(i)
        used_d.add(j)
        pairs.append((keepers[i], drafts[j]))
    return pairs


def albums_with_keepers(lab_root: Path) -> list[str]:
    from .schema import is_keeper, load_section_rows

    albums = {
        rec.get("album") or ""
        for rec in load_section_rows(Path(lab_root) / "data" / "sections.jsonl")
        if is_keeper(rec.get("source")) and rec.get("heard") is True and rec.get("album")
    }
    return sorted(albums)


def rebuild_album(lab_root, album) -> dict:
    """Rebuild one album's calibration object from its heard keeper pairs."""
    from .holdout import load_holdout
    from .schema import canonical_role, is_keeper, load_section_rows, write_jsonl_atomic

    lab_root = Path(lab_root)
    section_rows = load_section_rows(lab_root / "data" / "sections.jsonl")
    keepers = [
        r for r in section_rows
        if is_keeper(r.get("source")) and r.get("heard") is True
        and (r.get("album") or "") == (album or "")
    ]
    draft_rows = [r for r in _read_jsonl(lab_root / "data" / "drafts.jsonl")
                  if r.get("source") in DRAFT_SOURCES]
    tracks = {r.get("track") or "" for r in keepers}
    # "Other tracks" means any track of the album (keepers OR drafts), so
    # Rebirth cannot teach a 13-track A Higher Place album just because it is
    # the only keeper; a genuinely holdout-ONLY album may build for itself.
    album_tracks = ({r.get("track") or "" for r in section_rows
                     if (r.get("album") or "") == (album or "")}
                    | {r.get("track") or "" for r in draft_rows
                       if (r.get("album") or "") == (album or "")})
    holdout = load_holdout(lab_root)
    held = {t for (a, t) in holdout if a == (album or "")}
    non_held = album_tracks - held
    eligible = tracks if not non_held else {t for t in tracks if t not in held}

    drafts = [
        r for r in draft_rows
        if (r.get("album") or "") == (album or "") and (r.get("track") or "") in eligible
    ]
    k_by: dict[str, list[dict]] = defaultdict(list)
    d_by: dict[str, list[dict]] = defaultdict(list)
    for r in keepers:
        if (r.get("track") or "") in eligible:
            k_by[r.get("track") or ""].append(r)
    for r in drafts:
        d_by[r.get("track") or ""].append(r)

    pairs: list[tuple[dict, dict]] = []
    for track in sorted(eligible):
        pairs.extend(_pair(k_by.get(track, []), d_by.get(track, [])))

    shift_start = _clamp(_median([float(k.get("start", 0.0)) - float(d.get("start", 0.0))
                                  for k, d in pairs]))
    shift_end = _clamp(_median([float(k.get("end", 0.0)) - float(d.get("end", 0.0))
                                for k, d in pairs]))

    min_count = 2 if len(pairs) >= 3 else 1
    by_drole: dict[str, list[str]] = defaultdict(list)
    by_fig: dict[str, list[str]] = defaultdict(list)
    for k, d in pairs:
        dr = d.get("role")
        kr = k.get("role")
        if dr and kr:
            by_drole[dr].append(kr)
        df = d.get("figure_id")
        kf = k.get("figure_id")
        if df and kf:
            by_fig[df].append(kf)
    roles = {dr: Counter(kr).most_common(1)[0][0]
             for dr, kr in by_drole.items() if len(kr) >= min_count}
    figures = {df: Counter(kf).most_common(1)[0][0] for df, kf in by_fig.items()}

    # Per-album breakdown span gate: heard breakdown keepers on this album,
    # excluding holdout (never let VAL teach another album). n>=2 arms it.
    bd_spans = sorted(
        float(r.get("end", 0.0)) - float(r.get("start", 0.0))
        for r in keepers
        if canonical_role(r.get("role")) == "breakdown" and (r.get("track") or "") not in held
    )
    bd_spans = [s for s in bd_spans if s > 0]

    # Same per-album span gate for the full-speed Blast function (opposite of
    # Breakdown); Guess's `_gate_blasts` reads it.
    bl_spans = sorted(
        float(r.get("end", 0.0)) - float(r.get("start", 0.0))
        for r in keepers
        if canonical_role(r.get("role")) == "blast" and (r.get("track") or "") not in held
    )
    bl_spans = [s for s in bl_spans if s > 0]

    obj = {
        "album": album,
        "n_pairs": len(pairs),
        "shift_start": round(shift_start, 4),
        "shift_end": round(shift_end, 4),
        "roles": roles,
        "figures": figures,
        "breakdowns": {"n": len(bd_spans), "median_span_sec": round(_median(bd_spans), 4)},
        "blasts": {"n": len(bl_spans), "median_span_sec": round(_median(bl_spans), 4)},
        "ts": round(time.time(), 3),
    }
    path = lab_root / "data" / "adapt.json"
    existing: dict = {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            existing = {}
    except Exception:
        existing = {}
    existing[album] = obj
    write_jsonl_atomic(path, [existing])  # one-line JSON; atomic; other albums kept
    return obj


def rebuild_global(lab_root) -> dict:
    """Rebuild the corpus-wide cold-start blob from every non-holdout album's
    heard keeper-vs-draft pairs, pooled together. Same pairing/shift/role
    logic as `rebuild_album`; `figures` is always empty here (see module
    docstring -- a figure_id is a per-song identifier, never pooled)."""
    from .holdout import load_holdout
    from .schema import canonical_role, is_keeper, load_section_rows, write_jsonl_atomic

    lab_root = Path(lab_root)
    section_rows = load_section_rows(lab_root / "data" / "sections.jsonl")
    draft_rows = [r for r in _read_jsonl(lab_root / "data" / "drafts.jsonl")
                  if r.get("source") in DRAFT_SOURCES]
    held = {(a, t) for (a, t) in load_holdout(lab_root)}

    keepers = [
        r for r in section_rows
        if is_keeper(r.get("source")) and r.get("heard") is True
        and (r.get("album"), r.get("track")) not in held
    ]
    drafts = [r for r in draft_rows if (r.get("album"), r.get("track")) not in held]

    k_by: dict[tuple, list[dict]] = defaultdict(list)
    d_by: dict[tuple, list[dict]] = defaultdict(list)
    for r in keepers:
        k_by[(r.get("album") or "", r.get("track") or "")].append(r)
    for r in drafts:
        d_by[(r.get("album") or "", r.get("track") or "")].append(r)

    pairs: list[tuple[dict, dict]] = []
    for key in sorted(k_by):
        pairs.extend(_pair(k_by[key], d_by.get(key, [])))

    shift_start = _clamp(_median([float(k.get("start", 0.0)) - float(d.get("start", 0.0))
                                  for k, d in pairs]))
    shift_end = _clamp(_median([float(k.get("end", 0.0)) - float(d.get("end", 0.0))
                                for k, d in pairs]))

    min_count = 2 if len(pairs) >= 3 else 1
    by_drole: dict[str, list[str]] = defaultdict(list)
    for k, d in pairs:
        dr, kr = d.get("role"), k.get("role")
        if dr and kr:
            by_drole[dr].append(kr)
    roles = {dr: Counter(kr).most_common(1)[0][0]
             for dr, kr in by_drole.items() if len(kr) >= min_count}

    bd_spans = sorted(
        float(r.get("end", 0.0)) - float(r.get("start", 0.0))
        for r in keepers if canonical_role(r.get("role")) == "breakdown"
    )
    bd_spans = [s for s in bd_spans if s > 0]
    bl_spans = sorted(
        float(r.get("end", 0.0)) - float(r.get("start", 0.0))
        for r in keepers if canonical_role(r.get("role")) == "blast"
    )
    bl_spans = [s for s in bl_spans if s > 0]

    obj = {
        "n_pairs": len(pairs),
        "shift_start": round(shift_start, 4),
        "shift_end": round(shift_end, 4),
        "roles": roles,
        "figures": {},
        "breakdowns": {"n": len(bd_spans), "median_span_sec": round(_median(bd_spans), 4)},
        "blasts": {"n": len(bl_spans), "median_span_sec": round(_median(bl_spans), 4)},
        "ts": round(time.time(), 3),
    }
    path = lab_root / "data" / "adapt.json"
    existing: dict = {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            existing = {}
    except Exception:
        existing = {}
    existing[GLOBAL_KEY] = obj
    write_jsonl_atomic(path, [existing])
    return obj


def load_adapt(lab_root, album) -> dict | None:
    """The album's own calibration blob if it has anything a consumer could
    use; else the corpus-wide `GLOBAL_KEY` blob if that does; else `None`.
    A brand-new album with no keepers of its own therefore still gets a real
    cold-start correction once any other album has taught the global blob.

    "Has anything usable" is `n_pairs >= 1` (shift/role, what `apply_adapt`
    itself re-checks) OR `breakdowns.n >= 2` (what `_gate_breakdowns` reads
    on its own, independent of pairing) -- a blob built from breakdown
    keepers with no matched draft pairs is real and must not be skipped."""
    path = Path(lab_root) / "data" / "adapt.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    def _armed(blob):
        if not isinstance(blob, dict):
            return False
        if int(blob.get("n_pairs") or 0) >= 1:
            return True
        if int((blob.get("breakdowns") or {}).get("n") or 0) >= 2:
            return True
        return int((blob.get("blasts") or {}).get("n") or 0) >= 2

    blob = data.get(album)
    if _armed(blob):
        return blob
    global_blob = data.get(GLOBAL_KEY)
    return global_blob if _armed(global_blob) else None


def apply_adapt(sections: list[dict], blob: dict | None) -> list[dict]:
    """Apply one album's calibration to draft boxes. Keepers are left alone;
    `heard` is never touched and no file is written."""
    if not blob or int(blob.get("n_pairs") or 0) < 1:
        return sections
    from .schema import is_keeper

    shift_start = float(blob.get("shift_start") or 0.0)
    shift_end = float(blob.get("shift_end") or 0.0)
    roles = blob.get("roles") or {}
    figures = blob.get("figures") or {}

    out: list[dict] = []
    for section in sections or []:
        s = dict(section)
        # Keepers and already-calibrated rows are left alone (no double-apply
        # when structure wrote an adapted row and the studio later loads it).
        if not is_keeper(s.get("source")) and not s.get("_adapted"):
            old_start = float(s.get("start", 0.0))
            old_end = float(s.get("end", 0.0))
            new_start = old_start + shift_start
            new_end = old_end + shift_end
            parts: list[str] = []
            if new_end > new_start:
                if abs(new_start - old_start) >= 0.02 or abs(new_end - old_end) >= 0.02:
                    parts.append("shift")
                s["start"] = round(new_start, 3)
                s["end"] = round(new_end, 3)
            # else: an inverted box keeps its original times (shift skipped)
            role = s.get("role")
            if role in roles:
                if roles[role] != role:
                    parts.append("role")
                s["role"] = roles[role]
            figure = s.get("figure_id")
            if figure in figures:
                if figures[figure] != figure:
                    parts.append("figure")
                s["figure_id"] = figures[figure]
            if parts:
                s["adapt"] = "+".join(parts)  # visibility only; never a source
            s["_adapted"] = True
        out.append(s)
    return out
