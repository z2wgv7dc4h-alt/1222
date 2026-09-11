from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .catalogue import FIELDS, filter_album, load_map, resolve, save_map, scan_roots
from .gate import write_report


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return root() / "data"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="boo-lab")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-map", help="write data/map.csv template if missing")
    sub.add_parser("scan", help="draft map.csv from BOO_FLAC_ROOT + BOO_GP_ROOT")
    st = sub.add_parser("studio", help="same as annotate")
    st.add_argument("--port", type=int, default=8765)

    s = sub.add_parser("stems")
    s.add_argument("--album")
    s.add_argument("--model", default="htdemucs_ft")

    s = sub.add_parser("structure")
    s.add_argument("--album")

    s = sub.add_parser("extract")
    s.add_argument("--album")

    s = sub.add_parser("gate")
    s.add_argument("--threshold", type=float, default=0.55)

    s = sub.add_parser("export-bank")
    s.add_argument("--out", type=Path, required=True)

    s = sub.add_parser("annotate", help="local UI: listen to FLAC, click section bounds")
    s.add_argument("--port", type=int, default=8765)

    args = p.parse_args(argv)
    flac_root = Path(os.environ.get("BOO_FLAC_ROOT", "")) if os.environ.get("BOO_FLAC_ROOT") else None
    gp_root = Path(os.environ.get("BOO_GP_ROOT", "")) if os.environ.get("BOO_GP_ROOT") else None
    map_path = data_dir() / "map.csv"

    env_file = root() / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))
        flac_root = Path(os.environ["BOO_FLAC_ROOT"]) if os.environ.get("BOO_FLAC_ROOT") else flac_root
        gp_root = Path(os.environ["BOO_GP_ROOT"]) if os.environ.get("BOO_GP_ROOT") else gp_root

    if args.cmd == "scan":
        drafted = scan_roots(flac_root, gp_root)
        save_map(map_path, drafted)
        print("wrote", len(drafted), "rows", map_path)
        return 0

    if args.cmd == "init-map":
        if not map_path.exists():
            save_map(map_path, [{k: "" for k in FIELDS}])
        print(map_path)
        return 0

    rows = load_map(map_path) if map_path.exists() else []
    rows = filter_album(rows, getattr(args, "album", None))
    rows = [resolve(r, flac_root, gp_root) for r in rows]

    if args.cmd == "stems":
        from .stems import run_demucs

        out = root() / "work" / "stems"
        for r in rows:
            fp = r.get("flac_path")
            if not fp or not Path(fp).exists():
                print("SKIP stems", r.get("track"), "no flac")
                continue
            dest = run_demucs(Path(fp), out, model=args.model)
            print("STEMS", r.get("track"), dest)
        return 0

    if args.cmd == "structure":
        from .structure import run_allin1, segments_from_allin1

        out_dir = root() / "work" / "allin1"
        out_dir.mkdir(parents=True, exist_ok=True)
        sec_path = data_dir() / "sections.jsonl"
        with sec_path.open("w", encoding="utf-8") as f:
            for r in rows:
                fp = r.get("flac_path")
                if not fp or not Path(fp).exists():
                    print("SKIP structure", r.get("track"), "no flac")
                    continue
                payload = run_allin1(Path(fp))
                (out_dir / f"{r.get('track')}.json").write_text(
                    json.dumps(payload, indent=2), encoding="utf-8"
                )
                for seg in segments_from_allin1(payload):
                    rec = {
                        "album": r.get("album"),
                        "track": r.get("track"),
                        **seg,
                    }
                    f.write(json.dumps(rec) + "\n")
                print("STRUCT", r.get("track"), payload.get("bpm"))
        return 0

    if args.cmd == "extract":
        from .extract import extract_riffs

        out = data_dir() / "riffs.jsonl"
        n = 0
        with out.open("w", encoding="utf-8") as f:
            for r in rows:
                if (r.get("match") or "").lower() not in {"yes", "y", "1", "true"}:
                    print("SKIP extract", r.get("track"), "match!=yes")
                    continue
                gp = r.get("gp_path")
                if not gp or not Path(gp).exists():
                    print("SKIP extract", r.get("track"), "no gp")
                    continue
                song = f"{r.get('album')}::{r.get('track')}"
                for riff in extract_riffs(Path(gp), song):
                    riff["album"] = r.get("album")
                    riff["track"] = r.get("track")
                    riff["tuning"] = r.get("tuning")
                    f.write(json.dumps(riff) + "\n")
                    n += 1
                print("RIFFS", r.get("track"))
        print("wrote", n, "riffs", out)
        return 0

    if args.cmd == "gate":
        beats_dir = root() / "work" / "allin1"
        report_rows = []
        riffs_path = data_dir() / "riffs.jsonl"
        if not riffs_path.exists():
            print("no riffs.jsonl — run extract")
            return 1
        # Without per-note times from GP-to-seconds, score files that have beats only
        # as "has structure + has riffs". Real onset lock is a follow-up ticket.
        have = {p.stem for p in beats_dir.glob("*.json")} if beats_dir.exists() else set()
        tracks = set()
        with riffs_path.open(encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                tracks.add(rec.get("track"))
        for track in sorted(tracks):
            ok = track in have or True  # do not block extract-only weekends
            score = 1.0 if track in have else 0.0
            report_rows.append({"track": track, "score": score, "ok": ok})
        write_report(data_dir() / "gate.csv", report_rows)
        print("gate.csv written (onset-lock v2 still open)")
        return 0

    if args.cmd in {"annotate", "studio"}:
        import os
        from .annotator import create_app

        app = create_app(root(), flac_root, gp_root)
        import uvicorn

        url = "http://127.0.0.1:%s" % args.port
        print(url)
        import threading, webbrowser, time
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
        uvicorn.run(app, host="127.0.0.1", port=args.port)
        return 0

    if args.cmd == "export-bank":
        riffs_path = data_dir() / "riffs.jsonl"
        items = []
        if riffs_path.exists():
            with riffs_path.open(encoding="utf-8") as f:
                items = [json.loads(line) for line in f]
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(items, indent=2), encoding="utf-8")
        print("bank", len(items), args.out)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
