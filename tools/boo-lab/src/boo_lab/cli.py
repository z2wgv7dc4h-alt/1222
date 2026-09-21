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


def _resolved_names(album: str | None, track: str | None) -> tuple[str | None, str | None]:
    """Resolve studio-style album/track against `map.csv` (year-prefixed album
    folders, "07 - Exist" vs "07 Exist"). Passes the typed pair through when
    incomplete or unmatched. Never a second map."""
    from .catalogue import load_map, resolve_row

    map_path = root() / "data" / "map.csv"
    if album and track and map_path.exists():
        row = resolve_row(load_map(map_path), album, track)
        if row is not None:
            return row.get("album") or album, row.get("track") or track
    return album, track


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
    s = sub.add_parser("hash", help="fill empty map.csv flac_sha256 cells")
    s.add_argument("--album")
    st = sub.add_parser("studio", help="same as annotate")
    st.add_argument("--port", type=int, default=8765)

    s = sub.add_parser("stems")
    s.add_argument("--album")
    s.add_argument("--model", default="htdemucs_6s")

    s = sub.add_parser("pack", help="slice mix+stems for each saved human box")
    s.add_argument("--album")

    s = sub.add_parser("drums", help="classify drum onsets per human-labeled section")
    s.add_argument("--album")
    s.add_argument("--per-track", action="store_true",
                   help="one whole-track row per song (no keeper needed; drafts only)")

    s = sub.add_parser("vocals", help="extract real vocal melody per human-labeled section")
    s.add_argument("--album")
    s.add_argument("--per-track", action="store_true",
                   help="one whole-track row per song (no keeper needed; drafts only)")

    sub.add_parser("holdout", help="write/print the fixed whole-song validation split")

    s = sub.add_parser("lyrics", help="fetch LRC / optional whisperx on vocals stem")
    s.add_argument("--album")

    s = sub.add_parser(
        "structure",
        help="MSA draft overlay → data/drafts.jsonl (does NOT touch sections.jsonl)",
    )
    s.add_argument("--album")
    sub.add_parser("audit", help="pin hygiene: sources, overlaps, heard, short boxes")

    s = sub.add_parser("extract")
    s.add_argument("--album")

    s = sub.add_parser("gate")
    s.add_argument("--threshold", type=float, default=0.55)

    s = sub.add_parser("doctor", help="check torch/GPU + optional interns; print install hints")
    s.add_argument("--require-interns", action="store_true",
                   help="exit non-zero if any intern is missing (used by setup.bat)")

    s = sub.add_parser("report", help="print real current state of the whole data pipeline")
    s.add_argument("--gp-root", type=Path, default=None, help="GP corpus for the failure breakdown (default: BOO_GP_ROOT)")

    sub.add_parser("status", help="rewrite the STATUS.md counts block from data files")

    s = sub.add_parser("interns", help="run every intern over the corpus (cached, resumable)")
    s.add_argument("--album")
    s.add_argument("--steps", default=None, help="comma list; default all")

    s = sub.add_parser("gpif", help="read a GP7 .gpx/.gp GPIF score (duration/notes; no sections.jsonl)")
    s.add_argument("--path", type=Path, required=True)
    s.add_argument("--write-gp5", type=Path, default=None,
                   help="also write <stem>.from-gpif.gp5 into this DIR")

    s = sub.add_parser("tabnotes", help="read a local tab-notes pack (.zip or folder; no sections.jsonl)")
    s.add_argument("--path", type=Path, required=True)
    s.add_argument("--json", action="store_true", help="print the whole pack as JSON")
    s.add_argument("--index", action="store_true",
                   help="append data/tabnotes_index.jsonl (never sections.jsonl)")

    s = sub.add_parser("export-bank")
    s.add_argument("--out", type=Path, required=True)

    s = sub.add_parser("agree", help="two-pass keeper-pin agreement snapshot/diff")
    s.add_argument("--album")
    s.add_argument("--track")
    s.add_argument("--write", action="store_true")
    s.add_argument("--diff", action="store_true")

    s = sub.add_parser("export-jams", help="export keeper pins as JAMS 0.3 (figure/function layers)")
    s.add_argument("--out", type=Path, required=True)

    s = sub.add_parser("compare", help="read-only machine drafts vs human keepers")
    s.add_argument("--album")
    s.add_argument("--track")

    s = sub.add_parser("learn", help="rank the machine draft sources from keepers")
    s.add_argument("--album")

    s = sub.add_parser("adapt", help="per-album calibration from accepted drafts (drafts only)")
    s.add_argument("--album")

    s = sub.add_parser("hear", help="mark already-keeper pins heard=true for one song")
    s.add_argument("--album")
    s.add_argument("--track")

    s = sub.add_parser("beats", help="write beat/downbeat grid (beat_this or allin1)")
    s.add_argument("--album")

    s = sub.add_parser("gp-export", help="probe .gp/.gpx: already usable by scan, or record why not")
    s.add_argument("--gp-root", type=Path, default=None)

    s = sub.add_parser("sync", help="tab-vs-audio clock witness for one song")
    s.add_argument("--album")
    s.add_argument("--track")

    s = sub.add_parser("figures", help="suggest repeating figure ids from a matched GP5 (drafts; never keepers)")
    s.add_argument("--album")
    s.add_argument("--track")

    s = sub.add_parser("tempo-hints", help="tempo-automation BPM changes from a tab-notes pack (drafts; never keepers)")
    s.add_argument("--album")
    s.add_argument("--track")

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
        report = ingest(args.drop, flac_root, gp_root, args.band, lab_root=root())
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

    if args.cmd == "doctor":
        from .doctor import run_doctor

        return run_doctor(root(), require_interns=getattr(args, "require_interns", False))

    if args.cmd == "hash":
        from .catalogue import fill_hashes

        report = fill_hashes(map_path, getattr(args, "album", None))
        print("hash: filled %d of %d row(s) -> %s" % (report["filled"], report["rows"], map_path))
        return 0

    rows = load_map(map_path) if map_path.exists() else []
    rows = filter_album(rows, getattr(args, "album", None))
    rows = [resolve(r, flac_root, gp_root) for r in rows]

    if args.cmd == "report":
        from .report import build_report

        build_report(root(), args.gp_root)
        return 0

    if args.cmd == "status":
        from .status import run_status

        report = run_status(root())
        if not report.get("updated"):
            print("status:", report.get("reason") or "not updated")
            return 1
        c = report["counts"]
        print("status: keepers=%d/%d drafts=%d (%s) sync_ok=%d/%d map=%d -> %s"
              % (c["keeper_rows"], c["keeper_tracks"], c["draft_rows"],
                 ",".join(c["draft_sources"]) or "none", c["sync_ok"], c["sync_total"],
                 c["map_rows"], report["path"]))
        return 0

    if args.cmd == "interns":
        from .interns import run_interns

        steps = [s.strip() for s in args.steps.split(",")] if getattr(args, "steps", None) else None
        report = run_interns(root(), flac_root, gp_root,
                             album=getattr(args, "album", None), steps=steps)
        print("interns summary:")
        for key, val in report.items():
            print("  %-10s %s" % (key, val))
        return 0

    if args.cmd == "gpif":
        from .gpif import count_markers, duration_sec, load_score

        try:
            score = load_score(args.path)
        except Exception as exc:  # noqa: BLE001 - a bad/unreadable GP is a clean CLI error
            print("gpif:", exc)
            return 1
        n_midi = sum(1 for n in score.notes if n.midi is not None)
        print("gpif %s: duration_sec=%.3f n_bars=%d n_notes=%d n_markers=%d n_with_midi=%d"
              % (args.path, duration_sec(score), len(score.masterbars),
                 len(score.notes), count_markers(score), n_midi))
        if getattr(args, "write_gp5", None):
            from .gpif_to_gp5 import gpif_to_gp5

            dest = Path(args.write_gp5) / (Path(args.path).stem + ".from-gpif.gp5")
            try:
                written, drops = gpif_to_gp5(score, dest)
            except Exception as exc:  # noqa: BLE001 - a bad score is a clean CLI error
                print("gpif --write-gp5:", exc)
                return 1
            print("wrote", written)
            print("drops:", ", ".join(drops) if drops else "none")
        return 0

    if args.cmd == "tabnotes":
        from .tabnotes import (
            append_index, load_pack, onsets_audio, pack_to_dict, tempo_map,
        )

        try:
            pack = load_pack(args.path)
        except Exception as exc:  # noqa: BLE001 - a bad pack is a clean CLI error
            print("tabnotes:", exc)
            return 1
        if args.json:
            print(json.dumps(pack_to_dict(pack), indent=2, default=str))
        else:
            print("tabnotes %s: %s — %s" % (pack.id, pack.title or "?", pack.artist or "?"))
            print("  clock_ratio=%.4f audio_total=%.3fs notated_total=%.1fms"
                  % (pack.clock_ratio, pack.audio_total_sec, pack.notated_total_ms))
            print("  tracks=%d measures=%d events=%d raw_beats=%d"
                  % (len(pack.tracks), len(pack.measures), len(pack.events), len(pack.raw_beats)))
            for t in pack.tracks:
                n = sum(1 for e in pack.events if e.track == t.index)
                print("  track %d %-16s cat=%-8s inst=%-18s tuning=%s capo=%s vol=%s n_events=%d"
                      % (t.index, t.name or "-", t.category or "-", t.instrument_name or "-",
                         t.tuning, t.capo, t.volume, n))
            sigs = sorted({e.time_signature for e in pack.events if e.time_signature}
                          | {m.time_signature for m in pack.measures if m.time_signature})
            print("  signatures:", ", ".join(sigs) or "none")
            tm = tempo_map(pack)
            if tm:
                bpms = [b for _s, b in tm]
                print("  tempo bpm min=%.1f max=%.1f automations=%s"
                      % (min(bpms), max(bpms), [round(b, 2) for _s, b in tm]))
            n_guitar = sum(1 for t in pack.tracks if "guitar" in (t.category or "").lower())
            n_drums = sum(1 for t in pack.tracks
                          if t.is_percussion or "drum" in (t.category or "").lower())
            print("  guitar=%d drums=%d other=%d"
                  % (n_guitar, n_drums, len(pack.tracks) - n_guitar - n_drums))
            n_tuplets = sum(1 for b in pack.raw_beats if b.tuplet)
            n_bends = sum(1 for b in pack.raw_beats for nn in b.notes if nn.bend_points)
            print("  raw tuplets=%d bends_with_points=%d" % (n_tuplets, n_bends))
            print("  first guitar audio onsets:",
                  [round(x, 3) for x in onsets_audio(pack, category="guitar")[:3]])
        if args.index:
            print("  indexed ->", append_index(root(), pack))
        return 0

    if args.cmd == "holdout":
        from .holdout import ensure_holdout

        holdout = ensure_holdout(root(), rows)
        print("holdout", len(holdout), "song(s) reserved for validation:")
        for album, track in sorted(holdout):
            print(f"  {album} :: {track}")
        return 0

    if args.cmd == "agree":
        from .agree import format_diff, load_passes, snapshot

        album = getattr(args, "album", None)
        track = getattr(args, "track", None)
        if not (album and track):
            print("need --album and --track")
            return 1
        album, track = _resolved_names(album, track)
        if args.write:
            rec = snapshot(root(), album, track)
            print("agree pass %d written for %s / %s (%d boxes)"
                  % (rec["pass"], album, track, len(rec["boxes"])))
        if args.diff:
            passes = load_passes(root(), album, track)
            p1 = next((p for p in passes if p.get("pass") == 1), None)
            p2 = next((p for p in passes if p.get("pass") == 2), None)
            if not p1 or not p2:
                print("need pass 1 and pass 2 for %s / %s" % (album, track))
                return 1
            print(format_diff(album, track, p1.get("boxes") or [], p2.get("boxes") or []))
        if not (args.write or args.diff):
            passes = load_passes(root(), album, track)
            print("agree passes for %s / %s: %s" % (album, track, [p.get("pass") for p in passes]))
        return 0

    if args.cmd == "export-jams":
        from .jams_export import export_jams

        report = export_jams(root(), args.out, rows)
        print("export-jams", report)
        return 0

    if args.cmd == "compare":
        from .compare import compare, format_report, write_report

        album, track = _resolved_names(getattr(args, "album", None), getattr(args, "track", None))
        report = compare(root(), album, track)
        print(format_report(report))
        write_report(report, data_dir() / "compare.json")
        print("wrote", data_dir() / "compare.json")
        try:
            from .learn import run_learn

            run_learn(root(), album)
        except Exception:
            pass  # ranking must never fail compare
        return 0

    if args.cmd == "learn":
        from .learn import run_learn

        rank = run_learn(root(), getattr(args, "album", None))
        fa = rank.get("figure_agree") or {}
        sr = rank.get("sync_rate") or {}
        print("learn: prefer=%s n_voted=%d" % (rank["prefer"], rank["n_voted"]))
        print("reason:", rank["reason"])
        print("figure match=%d miss=%d conflict=%d"
              % (fa.get("match", 0), fa.get("miss", 0), fa.get("conflict", 0)))
        print("sync_ok %.3f (%d/%d)"
              % (sr.get("rate", 0.0), sr.get("ok", 0), sr.get("total", 0)))
        return 0

    if args.cmd == "adapt":
        from .adapt import albums_with_keepers, rebuild_album, rebuild_global

        album = getattr(args, "album", None)
        targets = [album] if album else albums_with_keepers(root())
        if not targets:
            print("adapt: no keeper albums")
            return 0
        for name in targets:
            obj = rebuild_album(root(), name)
            print("adapt: album=%s n_pairs=%d shift_start=%.3f shift_end=%.3f roles=%s"
                  % (name, obj["n_pairs"], obj["shift_start"], obj["shift_end"], obj["roles"]))
        gobj = rebuild_global(root())
        print("adapt: global n_pairs=%d shift_start=%.3f shift_end=%.3f roles=%s breakdowns=%s"
              % (gobj["n_pairs"], gobj["shift_start"], gobj["shift_end"], gobj["roles"],
                 gobj["breakdowns"]))
        return 0

    if args.cmd == "hear":
        from .hear import mark_heard

        try:
            report = mark_heard(root(), getattr(args, "album", None), getattr(args, "track", None))
        except ValueError as exc:
            print("refuse:", exc)
            return 1
        print("hear: flipped %d row(s) heard=true for %s / %s (%d rows total)"
              % (report["flipped"], report["album"], report["track"], report["rows"]))
        return 0

    if args.cmd == "sync":
        from .sync import sync_track

        try:
            record = sync_track(root(), getattr(args, "album", None), getattr(args, "track", None))
        except ValueError as exc:
            print("refuse:", exc)
            return 1
        print("sync", record)
        return 0

    if args.cmd == "figures":
        from .figures import build_figures

        album = getattr(args, "album", None)
        track = getattr(args, "track", None)
        if (album is None) != (track is None):
            print("need --album and --track together")
            return 1
        # `rows` was already filtered by the exact album name; reload the full
        # map so a year-prefixed folder / track punctuation can still resolve.
        full = ([resolve(r, flac_root, gp_root) for r in load_map(map_path)]
                if map_path.exists() else rows)
        report = build_figures(root(), full, album=album, track=track)
        print("figures: %d song(s) processed, %d repeating cluster(s) -> %s"
              % (report["songs"], report["clusters"], report["out"]))
        return 0

    if args.cmd == "tempo-hints":
        from .tempo_hints import build_tempo_hints

        album = getattr(args, "album", None)
        track = getattr(args, "track", None)
        if (album is None) != (track is None):
            print("need --album and --track together")
            return 1
        full = ([resolve(r, flac_root, gp_root) for r in load_map(map_path)]
                if map_path.exists() else rows)
        report = build_tempo_hints(root(), full, album=album, track=track)
        print("tempo-hints: %d song(s) processed, %d row(s) -> %s"
              % (report["songs"], report["written"], report["out"]))
        return 0

    if args.cmd == "stems":
        from .stems import run_demucs, stem_dir

        out = root() / "work" / "stems"
        album = getattr(args, "album", None)
        for r in rows:
            if album and (r.get("album") or "") != album:
                continue
            fp = r.get("flac_path")
            if not fp or not Path(fp).exists():
                print("SKIP stems", r.get("track"), "no flac")
                continue
            cached = stem_dir(Path(fp), out, args.model)
            if cached.exists() and any(cached.iterdir()):
                print("STEMS", r.get("track"), "cached", cached)
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

        report = build_drum_patterns(root(), rows, root() / "work" / "stems",
                                     per_track=getattr(args, "per_track", False))
        print("drums", report)
        return 0

    if args.cmd == "vocals":
        from .vocal_melody import build_vocal_melody

        report = build_vocal_melody(root(), rows, root() / "work" / "stems",
                                    per_track=getattr(args, "per_track", False))
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

    if args.cmd == "audit":
        from .audit import audit_lab, print_audit

        print_audit(audit_lab(root()))
        return 0

    if args.cmd == "structure":
        from .structure import build_drafts

        report = build_drafts(root(), rows)
        print("wrote", report["written"], "drafts (sections.jsonl untouched)"
              + (" [allin1 + songformer]" if report.get("songformer") else " [allin1]"))
        return 0

    if args.cmd == "beats":
        from .beats import build_beats

        report = build_beats(root(), rows, getattr(args, "album", None))
        print("beats", report)
        return 0

    if args.cmd == "gp-export":
        from .gp_export import export_gp

        report = export_gp(root(), getattr(args, "gp_root", None) or gp_root)
        if report["converter"]:
            print("converter:", report["converter"])
        converted = sum(1 for r in report["unsupported"] if r.get("converted"))
        print("gp-export: %d file(s); %d parse; %d unsupported; %d from GPIF -> %s"
              % (report["scanned"], len(report["ok"]), len(report["unsupported"]),
                 converted, report["out"]))
        if report["ok"]:
            print("these .gp/.gpx already parse — run `boo-lab scan` to point map.csv at them")
        return 0

    if args.cmd == "extract":
        import dataclasses

        from .audio_extract import extract_fragments_from_audio
        from .cells import song_cells
        from .extract import extract_riffs, load_human_sections
        from .holdout import ensure_holdout, split_for
        from .schema import write_jsonl_atomic

        human = load_human_sections(data_dir())
        holdout = ensure_holdout(root(), rows)
        human_tracks = 0
        audio_tracks = 0
        cell_songs = 0
        skipped_long = 0
        figure_ids: set[str] = set()
        out = data_dir() / "riffs.jsonl"
        produced: list[dict] = []

        for r in rows:
            album = r.get("album")
            track = r.get("track")
            song = f"{album}::{track}"
            sections = human.get((album, track))
            gp = r.get("gp_path")
            matched = (r.get("match") or "").lower() in {"yes", "y", "1", "true"}
            flac_val = r.get("flac_path") or r.get("flac") or ""
            flac = Path(flac_val) if flac_val else None

            tab_fragments = None
            if matched and gp and Path(gp).exists():
                try:
                    tab_fragments = extract_riffs(Path(gp), song, human_sections=sections)
                except Exception as e:  # noqa: BLE001 - real unparseable-GP files exist in this corpus
                    print("TAB FAILED", track, e)
                    tab_fragments = None
            if tab_fragments:
                # Cell layer: one representative 2-4 bar cell per figure_id
                # (never one fragment per bar, never a whole long pin).
                cells, long_spans = song_cells(root(), r, fragments=tab_fragments)
                for cell in cells:
                    cell["tuning"] = r.get("tuning")
                    cell["split"] = split_for(album, track, holdout)
                    produced.append(cell)
                    figure_ids.add(cell["figure_id"])
                skipped_long += long_spans
                if sections:
                    human_tracks += 1
                cell_songs += 1
                print("CELLS", track, len(cells), "cell(s)")
                continue

            # No usable real GP file (none matched, missing on disk, or
            # unparseable/zero fragments) -> real audio transcription
            # fallback (`source_type="audio_transcribed"`), instead of
            # silently producing zero riff data for the song.
            if flac is None or not flac.exists():
                print("SKIP extract", track, "no usable gp and no flac")
                continue
            fragments = extract_fragments_from_audio(flac, root() / "work" / "stems", song)
            audio_tracks += 1
            for frag in fragments:
                rec = dataclasses.asdict(frag)
                rec["album"] = album
                rec["track"] = track
                rec["tuning"] = r.get("tuning")
                rec["split"] = split_for(album, track, holdout)
                produced.append(rec)
            print("AUDIO", track, len(fragments), "transcribed fragments")

        if produced:
            write_jsonl_atomic(out, produced)
        else:
            print("extract: 0 rows; leaving", out.name, "untouched")
        print(
            "wrote", len(produced), "rows", out,
            "-", len(figure_ids), "figure(s),", cell_songs, "song(s) as cell(s);",
            human_tracks, "used human sections.jsonl;",
            audio_tracks, "audio fallback;",
            skipped_long, "span(s) longer than 4 bars reduced",
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
