# applied; do not re-run on current tree

# Hand patches on origin files

## 1. `src/boo_lab/cli.py`

Add next to the structure parser:

```python
    s = sub.add_parser(
        "structure",
        help="MSA draft overlay → data/drafts.jsonl (does NOT touch sections.jsonl)",
    )
    s.add_argument("--album")
    sub.add_parser("audit", help="pin hygiene: sources, overlaps, heard, short boxes")
```

Replace the entire `if args.cmd == "structure":` block with:

```python
    if args.cmd == "audit":
        from .audit import audit_lab, print_audit
        print_audit(audit_lab(root()))
        return 0

    if args.cmd == "structure":
        from .schema import stamp_box
        from .structure import run_allin1, segments_from_allin1

        out_dir = root() / "work" / "msa"
        out_dir.mkdir(parents=True, exist_ok=True)
        draft_path = data_dir() / "drafts.jsonl"
        keep = []
        if draft_path.exists():
            for line in draft_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                key = (rec.get("album"), rec.get("track"))
                if any((r.get("album"), r.get("track")) == key for r in rows):
                    continue
                keep.append(rec)
        written = 0
        with draft_path.open("w", encoding="utf-8") as f:
            for rec in keep:
                f.write(json.dumps(rec) + "\n")
            for r in rows:
                fp = r.get("flac_path")
                if not fp or not Path(fp).exists():
                    print("SKIP structure", r.get("track"), "no flac")
                    continue
                try:
                    payload = run_allin1(Path(fp))
                except Exception as exc:
                    print("SKIP structure", r.get("track"), exc)
                    continue
                (out_dir / f"{r.get('track')}.json").write_text(
                    json.dumps(payload, indent=2, default=str), encoding="utf-8"
                )
                for seg in segments_from_allin1(payload):
                    rec = stamp_box(
                        seg["start"], seg["end"], seg.get("role") or seg.get("label"),
                        source="msa-draft",
                        extra={"album": r.get("album"), "track": r.get("track"),
                               "msa_label": seg.get("label") or ""},
                    )
                    f.write(json.dumps(rec) + "\n")
                    written += 1
                print("DRAFT", r.get("track"), payload.get("bpm"), "→ data/drafts.jsonl")
        print("wrote", written, "drafts (sections.jsonl untouched)")
        return 0
```

Confirm the old block that did `sec_path.open("w")` on `sections.jsonl` is gone.

## 2. `src/boo_lab/structure.py`

Replace the `role_map = {...}; out["role"] = role_map.get(...)` with:

```python
    from .schema import msa_label_to_lab
    out["role"] = msa_label_to_lab(label)
```

## 3. `src/boo_lab/pack.py`

In `_load_sections`, only keepers:

```python
        from .schema import is_keeper
        if rec.get("role") and is_keeper(rec.get("source")):
            out.append(rec)
```

Add `"figure_id": seg.get("figure_id") or ""` and `"source": seg.get("source") or "human"` to pack `meta`.

## 4. `src/boo_lab/extract.py`

Inside `load_human_sections` after `json.loads`:

```python
                from .schema import is_keeper
                if not is_keeper(rec.get("source")):
                    continue
```

## 5. `src/boo_lab/guess.py`

Replace the hardcoded `GP5_ROOTS = [Path(r"C:\Users\...")]` with:

```python
import os

def _gp5_roots() -> list[Path]:
    roots: list[Path] = []
    env = os.environ.get("BOO_GP_ROOT")
    if env:
        p = Path(env)
        roots.extend([p / "gp5", p])
    roots.extend(
        [
            Path(r"C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\gp-tabs\gp5"),
            Path(r"C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\gp-tabs"),
            Path(r"C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference"),
        ]
    )
    seen: list[Path] = []
    for r in roots:
        if r not in seen:
            seen.append(r)
    return seen

GP5_ROOTS = _gp5_roots()
```

Anywhere you loop `GP5_ROOTS` for disk search, call `_gp5_roots()` so `.env` is respected after import.
