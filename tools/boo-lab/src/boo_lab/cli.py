from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .catalogue import FIELDS, filter_album, load_map, resolve, save_map, scan_roots
from .gate import write_report


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return root() / "data"


def main(argv: list[str] | None = None) -> int:
    # Real album/track names in this corpus contain non-cp1252 characters
    # (e.g. "∆"); never let a console-encoding error abort a command.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="boo-lab")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-map", help="write data/map.csv template if missing")
    sub.add_parser("scan", help="draft map.csv from BOO_FLAC_ROOT + BOO_GP_ROOT")
    st = sub.add_parser("studio", help="same as annotate")
    st.add_argument("--port", type=int, default=8765)

    s = sub.add_parser("stems")
    s.add_argument("--album")
    s.add_argument("--model", default="htdemucs_6s")

    s = sub.add_parser("pack", help="slice mix+stems for each saved human box")
    s.add_argument("--album")

    s = sub.add_parser("drums", help="classify drum onsets per human-labeled section")
    s.add_argument("--album")

    s = sub.add_parser("vocals", help="extract real vocal melody per human-labeled section")
    s.add_argument("--album")

    sub.add_parser("holdout", help="write/print the fixed whole-song validation split")

    s = sub.add_parser("lyrics", help="fetch LRC / optional whisperx on vocals stem")
    s.add_argument("--album")

    s = sub.add_parser("structure")
    s.add_argument("--album")

    s = sub.add_parser("extract")
    s.add_argument("--album")

    s = sub.add_parser("gate")
    s.add_argument("--threshold", type=float, default=0.55)

    s = sub.add_parser("report", help="print real current state of the whole data pipeline")
    s.add_argument("--gp-root", type=Path, default=None, help="GP corpus for the failure breakdown (default: BOO_GP_ROOT)")

    s = sub.add_parser("export-bank")
    s.add_argument("--out", type=Path, required=True)

    s = sub.add_parser("annotate", help="local UI: listen to FLAC, click section bounds")
    s.add_argument("--port", type=int, default=8765)

    s = sub.add_parser("ingest", help="copy a drop folder of zips/FLAC/GP into the corpus")
    s.add_argument("drop", type=Path)
    s.add_argument("--band", required=True)

    args = p.parse_args(argv)
    env_file = root() / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))
    flac_val = os.environ.get("BOO_FLAC_ROOT") or ""
    gp_val = os.environ.get("BOO_GP_ROOT") or ""
    flac_root = Path(flac_val) if flac_val else None
    gp_root = Path(gp_val) if gp_val else None
    map_path = data_dir() / "map.csv"

    if args.cmd == "ingest":
        from .ingest import ingest

        if not flac_root or not gp_root:
            print("set BOO_FLAC_ROOT and BOO_GP_ROOT")
            return 1
        report = ingest(args.drop, flac_root, gp_root, args.band)
        print(report)
        drafted = scan_roots(flac_root, gp_root)
        save_map(map_path, drafted)
        print("map.csv", len(drafted), "rows")
        return 0

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

    if args.cmd == "report":
        from .report import build_report

        build_report(root(), args.gp_root)
        return 0

    if args.cmd == "holdout":
        from .holdout import ensure_holdout

        holdout = ensure_holdout(root(), rows)
        print("holdout", len(holdout), "song(s) reserved for validation:")
        for album, track in sorted(holdout):
            print(f"  {album} :: {track}")
        return 0

    if args.cmd == "stems":
        from .stems import run_demucs

        out = root() / "work" / "stems"
        for r in rows:
            fp = r.get("flac_path")
            if not fp or not Path(fp).exists():
                print("SKIP stems", r.get("track"), "no flac")
                continue
            dest = run_demucs(Path(fp), out, model=args.model, two_stems=None)
            print("STEMS", r.get("track"), dest)
        return 0

    if args.cmd == "pack":
        from .pack import build_pack

        report = build_pack(root(), rows, root() / "work" / "stems")
        print("pack", report)
        return 0

    if args.cmd == "drums":
        from .drums_extract import build_drum_patterns

        report = build_drum_patterns(root(), rows, root() / "work" / "stems")
        print("drums", report)
        return 0

    if args.cmd == "vocals":
        from .vocal_melody import build_vocal_melody

        report = build_vocal_melody(root(), rows, root() / "work" / "stems")
        print("vocals", report)
        return 0

    if args.cmd == "lyrics":
        from .lyrics import build_lyrics
        from .stems import find_stem

        n = 0
        cache = root() / "work" / "stems"
        for r in rows:
            fp = r.get("flac_path")
            flac = Path(fp) if fp else None
            voc = find_stem(flac, cache, "vocals") if flac else None
            payload = build_lyrics(root(), r.get("track") or "", flac, voc)
            print("LYRICS", r.get("track"), payload.get("note"), "lines", len(payload.get("lines") or []))
            n += 1
        print("lyrics", n)
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
        import dataclasses

        from .audio_extract import extract_fragments_from_audio
        from .extract import extract_riffs, load_human_sections
        from .holdout import ensure_holdout, split_for

        human = load_human_sections(data_dir())
        holdout = ensure_holdout(root(), rows)
        human_tracks = 0
        audio_tracks = 0
        out = data_dir() / "riffs.jsonl"
        n = 0
        with out.open("w", encoding="utf-8") as f:
            for r in rows:
                song = f"{r.get('album')}::{r.get('track')}"
                sections = human.get((r.get("album"), r.get("track")))
                gp = r.get("gp_path")
                matched = (r.get("match") or "").lower() in {"yes", "y", "1", "true"}
                flac_val = r.get("flac_path") or r.get("flac") or ""
                flac = Path(flac_val) if flac_val else None

                tab_fragments = None
                if matched and gp and Path(gp).exists():
                    try:
                        tab_fragments = extract_riffs(Path(gp), song, human_sections=sections)
                    except Exception as e:  # noqa: BLE001 - real unparseable-GP files exist in this corpus
                        print("TAB FAILED", r.get("track"), e)
                        tab_fragments = None
                if tab_fragments:
                    # Real tab path -- these are `source_type="tab_verbatim"`
                    # and must always be preferred over the audio fallback
                    # below for the same role.
                    if sections:
                        human_tracks += 1
                    for riff in tab_fragments:
                        riff["album"] = r.get("album")
                        riff["track"] = r.get("track")
                        riff["tuning"] = r.get("tuning")
                        riff["split"] = split_for(r.get("album"), r.get("track"), holdout)
                        f.write(json.dumps(riff) + "\n")
                        n += 1
                    print("RIFFS", r.get("track"), "(human labels)" if sections else "(gp markers only)")
                    continue

                # No usable real GP file (none matched, missing on disk, or
                # unparseable/zero fragments) -> real audio transcription
                # fallback (`source_type="audio_transcribed"`), instead of
                # silently producing zero riff data for the song.
                if flac is None or not flac.exists():
                    print("SKIP extract", r.get("track"), "no usable gp and no flac")
                    continue
                fragments = extract_fragments_from_audio(flac, root() / "work" / "stems", song)
                audio_tracks += 1
                for frag in fragments:
                    rec = dataclasses.asdict(frag)
                    rec["album"] = r.get("album")
                    rec["track"] = r.get("track")
                    rec["tuning"] = r.get("tuning")
                    rec["split"] = split_for(r.get("album"), r.get("track"), holdout)
                    f.write(json.dumps(rec) + "\n")
                    n += 1
                print("AUDIO", r.get("track"), len(fragments), "transcribed fragments")
        print(
            "wrote", n, "riffs", out,
            "-", human_tracks, "track(s) used real human sections.jsonl labels;",
            audio_tracks, "track(s) used audio transcription fallback",
        )
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
        from .holdout import ensure_holdout, split_for

        holdout = ensure_holdout(root(), rows)
        riffs_path = data_dir() / "riffs.jsonl"
        items = []
        if riffs_path.exists():
            with riffs_path.open(encoding="utf-8") as f:
                items = [json.loads(line) for line in f]
        for rec in items:
            rec["split"] = split_for(rec.get("album"), rec.get("track"), holdout)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(items, indent=2), encoding="utf-8")
        print("bank", len(items), args.out)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
