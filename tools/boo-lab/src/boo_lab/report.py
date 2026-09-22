from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .schema import ROLES, canonical_role, load_section_rows

# The one lab role vocabulary: schema.ROLES exactly (includes `blast`). Health
# never mixes engine/MSA labels (verse/chorus/interlude) into lab coverage --
# that engine mapping lives only in extract.py's _BOO_LAB_TO_ENGINE_ROLE.
ROLE_VOCABULARY = list(ROLES)

_MATCH_YES = {"yes", "y", "1", "true"}


def _rel(lab_root: Path, path: Path) -> str:
    """Path relative to the lab root, POSIX separators -- health JSON never
    leaks a machine-absolute `C:\\Users\\...` root."""
    try:
        rel = os.path.relpath(str(path), str(lab_root))
    except ValueError:
        rel = str(path)
    return rel.replace("\\", "/")

# Real pipeline files this report checks. `keys` is the real identity tuple
# used for the distinct count; `extras` lists extra per-value breakdowns to
# report when present on the rows.
_SPECS: list[dict] = [
    {"name": "data/map.csv", "rel": "data/map.csv", "kind": "map", "keys": ("album", "track")},
    {"name": "data/sections.jsonl", "rel": "data/sections.jsonl", "kind": "jsonl", "keys": ("album", "track")},
    {"name": "data/rebirth-sections.jsonl", "rel": "data/rebirth-sections.jsonl", "kind": "jsonl", "keys": ("album", "track")},
    {"name": "data/drum_patterns.jsonl", "rel": "data/drum_patterns.jsonl", "kind": "jsonl", "keys": ("album", "track")},
    {"name": "data/vocal_melody.jsonl", "rel": "data/vocal_melody.jsonl", "kind": "jsonl", "keys": ("album", "track")},
    {"name": "data/riffs.jsonl", "rel": "data/riffs.jsonl", "kind": "jsonl", "keys": ("album", "track"), "extras": ("source_type", "instrument")},
    {"name": "data/learn.jsonl", "rel": "data/learn.jsonl", "kind": "jsonl", "keys": ("album", "track")},
    {"name": "data/section_tempo.jsonl", "rel": "data/section_tempo.jsonl", "kind": "jsonl", "keys": ("album", "track")},
    {"name": "engine/data/riff_bank.json", "rel": "engine/data/riff_bank.json", "kind": "json_array", "keys": ("source_song", "source_file"), "extras": ("instrument", "source_type", "role")},
    {"name": "engine/data/bass_riff_bank.json", "rel": "engine/data/bass_riff_bank.json", "kind": "json_array", "keys": ("source_song", "source_file"), "extras": ("instrument", "source_type", "role")},
    {"name": "engine/data/lead_riff_bank.json", "rel": "engine/data/lead_riff_bank.json", "kind": "json_array", "keys": ("source_song", "source_file"), "extras": ("instrument", "source_type", "role")},
]


def _read_jsonl(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _read_json_array(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _counts(rows: list[dict], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        v = r.get(field)
        if v:
            out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _distinct(rows: list[dict], keys: tuple[str, ...]) -> int:
    return len({tuple(r.get(k) for k in keys) for r in rows})


def _map_summary(rows: list[dict]) -> dict:
    matched_real = matched_missing = no_tab = unmatched = match_yes = 0
    for r in rows:
        gp = (r.get("gp") or "").strip()
        match = (r.get("match") or "").lower()
        if match in _MATCH_YES:
            match_yes += 1
        if match in _MATCH_YES and gp and Path(gp).exists():
            matched_real += 1
        elif match in _MATCH_YES and gp:
            matched_missing += 1
        elif not gp:
            no_tab += 1
        else:
            unmatched += 1
    return {
        "total": len(rows),
        "match_yes": match_yes,
        "matched_real_gp_on_disk": matched_real,
        "matched_gp_missing_on_disk": matched_missing,
        "no_tab_empty_gp_path": no_tab,
        "unmatched_has_gp": unmatched,
    }


def _riff_bank_failure_breakdown(gp_source: Path, lab_root: Path) -> dict:
    """Actually run `engine/riff_bank.build_riff_bank` for all three
    instrument families over `gp_source` and count real failure reasons per
    category (via `riff_bank.classify_failure_reason`) -- surfacing WHY
    files contributed zero fragments (parse error vs. gpx-unsupported vs.
    no guitar/bass/lead track), not just a flat count."""
    engine_root = Path(__file__).resolve().parents[4] / "engine"
    if str(engine_root) not in sys.path:
        sys.path.insert(0, str(engine_root))
    try:
        import riff_bank
    except Exception as e:  # noqa: BLE001 - real honest unavailable case
        return {"available": False, "reason": f"engine riff_bank import failed: {e}"}
    if not gp_source.exists():
        return {"available": False, "reason": f"GP source dir does not exist: {gp_source}"}

    by_instrument: dict[str, dict] = {}
    for instrument in ("guitar", "bass", "lead"):
        try:
            fragments, failures = riff_bank.build_riff_bank(gp_source, instrument=instrument)
        except Exception as e:  # noqa: BLE001
            by_instrument[instrument] = {"error": str(e)}
            continue
        by_category: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        for _path, reason in failures:
            by_reason[reason] = by_reason.get(reason, 0) + 1
            category = riff_bank.classify_failure_reason(reason)
            by_category[category] = by_category.get(category, 0) + 1
        by_instrument[instrument] = {
            "fragments": len(fragments),
            "failures_total": len(failures),
            "by_category": dict(sorted(by_category.items(), key=lambda kv: (-kv[1], kv[0]))),
            "by_reason": dict(sorted(by_reason.items(), key=lambda kv: (-kv[1], kv[0]))),
        }
    return {"available": True, "source": _rel(lab_root, gp_source), "by_instrument": by_instrument}


def build_report(lab_root: Path, gp_source: Path | None = None) -> dict:
    """Actually parse every real pipeline file and report the numbers. Writes
    `data/corpus_health.json` and returns the same structure. Missing files
    are reported as 0 rows, never skipped.

    `gp_source` (default: `BOO_GP_ROOT`) is the real GP corpus the riff-bank
    failure breakdown is computed over; when neither is available that
    section honestly reports `available: false`."""
    lab_root = Path(lab_root)
    repo_root = Path(__file__).resolve().parents[4]
    out_path = lab_root / "data" / "corpus_health.json"

    files: dict[str, dict] = {}
    missing: list[str] = []

    for spec in _SPECS:
        base = repo_root if spec["rel"].startswith("engine/") else lab_root
        path = base / spec["rel"]
        entry: dict = {"path": _rel(lab_root, path), "exists": path.exists()}
        rows = None
        if entry["exists"]:
            if spec["kind"] == "map":
                from .catalogue import load_map

                rows = load_map(path)
            elif spec["kind"] == "jsonl":
                rows = _read_jsonl(path)
            else:
                rows = _read_json_array(path)
        if rows is None:
            entry.update({"rows": 0, "distinct": 0, "distinct_key": ",".join(spec["keys"])})
            missing.append(spec["name"])
        else:
            entry["rows"] = len(rows)
            entry["distinct"] = _distinct(rows, spec["keys"])
            entry["distinct_key"] = ",".join(spec["keys"])
            roles = _counts(rows, "role")
            if roles or any("role" in r for r in rows):
                # Raw per-file provenance only -- never summed into lab
                # coverage (engine `verse`/`chorus` must not become lab riff).
                entry["role_counts"] = roles
            for extra in spec.get("extras", []):
                if extra != "role":
                    entry[f"{extra}_counts"] = _counts(rows, extra)
        if spec["kind"] == "map" and rows is not None:
            entry["map"] = _map_summary(rows)
        files[spec["name"]] = entry

    # Lab coverage comes ONLY from the keeper rows (schema.load_section_rows),
    # normalized to the lab vocabulary. Engine/MSA labels are never summed here.
    keepers = load_section_rows(lab_root / "data" / "sections.jsonl")
    role_totals: dict[str, int] = {}
    for rec in keepers:
        role = canonical_role(rec.get("role"))
        if role in ROLE_VOCABULARY:
            role_totals[role] = role_totals.get(role, 0) + 1

    zero_coverage = [r for r in ROLE_VOCABULARY if role_totals.get(r, 0) == 0]
    if gp_source is None:
        env_val = os.environ.get("BOO_GP_ROOT") or ""
        gp_source = Path(env_val) if env_val else None
    failures = (
        _riff_bank_failure_breakdown(gp_source, lab_root)
        if gp_source is not None
        else {"available": False, "reason": "no GP source dir (set BOO_GP_ROOT or pass --gp-root)"}
    )
    report = {
        "role_vocabulary": ROLE_VOCABULARY,
        "role_totals": dict(sorted(role_totals.items(), key=lambda kv: (-kv[1], kv[0]))),
        "roles_zero_coverage": zero_coverage,
        "files": files,
        "riff_bank_failures": failures,
        "missing_files": missing,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    _print_report(report, out_path)
    return report


def _print_report(report: dict, out_path: Path) -> None:
    print("boo-lab pipeline report")
    print("=" * 78)
    print(f"{'FILE':40s} {'ROWS':>7s} {'DISTINCT':>9s}  STATUS")
    for name, entry in report["files"].items():
        if not entry["exists"]:
            print(f"{name:40s} {'0':>7s} {'0':>9s}  0 rows (file does not exist)")
            continue
        status = "ok"
        print(f"{name:40s} {entry['rows']:>7d} {entry['distinct']:>9d}  {status}")

    map_entry = report["files"].get("data/map.csv", {}).get("map")
    if map_entry:
        print()
        print("map.csv cross-reference")
        print("-" * 78)
        print(f"  total rows:                        {map_entry['total']}")
        print(f"  match=yes:                         {map_entry['match_yes']}")
        print(f"  match=yes + real gp on disk:       {map_entry['matched_real_gp_on_disk']}")
        print(f"  match=yes + gp path missing:       {map_entry['matched_gp_missing_on_disk']}")
        print(f"  no tab (empty gp path):            {map_entry['no_tab_empty_gp_path']}")
        print(f"  unmatched (match != yes, has gp):  {map_entry['unmatched_has_gp']}")

    failures = report.get("riff_bank_failures", {})
    print()
    print("riff_bank failure reasons")
    print("-" * 78)
    if not failures.get("available"):
        print(f"  not available: {failures.get('reason')}")
    else:
        print(f"  source: {failures['source']}")
        for instrument, entry in failures["by_instrument"].items():
            if "error" in entry:
                print(f"  {instrument}: ERROR {entry['error']}")
                continue
            cats = ", ".join(f"{k}={v}" for k, v in entry["by_category"].items()) or "(none)"
            print(
                f"  {instrument}: fragments={entry['fragments']} "
                f"failures={entry['failures_total']} -- {cats}"
            )

    print()
    print("role breakdown (files that carry a role field)")
    print("-" * 78)
    any_roles = False
    for name, entry in report["files"].items():
        if entry.get("role_counts"):
            any_roles = True
            pairs = ", ".join(f"{k}={v}" for k, v in entry["role_counts"].items())
            print(f"  {name}: {pairs}")
    if not any_roles:
        print("  (no file carries a role field)")

    print()
    print("role vocabulary coverage (tools/boo-lab/CURRENT.md ## Roles)")
    print("-" * 78)
    for role in report["role_vocabulary"]:
        n = report["role_totals"].get(role, 0)
        print(f"  {role:10s} {n}")
    if report["roles_zero_coverage"]:
        print(f"  ZERO real entries anywhere: {', '.join(report['roles_zero_coverage'])}")
    else:
        print("  ZERO real entries anywhere: (none)")

    print()
    print(f"machine-readable: {out_path}")


if __name__ == "__main__":
    build_report(Path(__file__).resolve().parents[2])
