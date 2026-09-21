"""Cell layer: one short representative cell per `figure_id`, never a whole pin.

LAW: the pin layer is human boxes + `figure_id` (long spans are fine). The cell
layer is the shortest repeating cell inside that figure -- 2, 3, or 4 bars,
preferring the hashed window already in `data/figures.jsonl`. Every other hit
of the figure is a pointer (bar + optional seconds when `times_trusted`), not
another bank fragment. So an 8-bar human `riff-A` box becomes one 2-4 bar cell,
not an 8-bar fragment. Writes `data/riffs.jsonl` (never `sections.jsonl`), and
never blanks an existing file on a zero-cell run.
"""
from __future__ import annotations

import json
from pathlib import Path


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _bar_of(frag) -> int:
    return int(_get(frag, "measure_index", 0) or 0) + 1


def _concat(cells):
    """Concatenate bar fragments into one cell; deltas are recomputed across
    the whole cell (top note per hit) so the interval chain stays continuous."""
    cell: list[dict] = []
    chord_notes: list[list[int]] = []
    chord_frets: list[list] = []
    for frag in cells:
        cell.extend(_get(frag, "cell") or [])
        chord_notes.extend(_get(frag, "chord_notes") or [])
        chord_frets.extend(_get(frag, "chord_frets") or [])
    deltas: list[int] = []
    prev = None
    for notes in chord_notes:
        top = max(int(n) for n in notes) if notes else 0
        deltas.append(0 if prev is None else top - prev)
        prev = top
    return cell, deltas, chord_notes, chord_frets


def _name_bar(frag, sec, human_boxes, fig_rows, trusted) -> str:
    """figure_id for one bar: human keeper covering its time (when times are
    trusted) -> figures.jsonl occurrence covering its bar -> marker letter."""
    if trusted and human_boxes:
        for hb in human_boxes:
            start, end = hb.get("start"), hb.get("end")
            if (hb.get("figure_id") and start is not None and end is not None
                    and float(start) <= sec <= float(end)):
                return hb["figure_id"]
    bar = _bar_of(frag)
    for row in fig_rows:
        for occ in row.get("occurrences") or []:
            b0, b1 = occ.get("start_bar"), occ.get("end_bar")
            if b0 is not None and b1 is not None and int(b0) <= bar <= int(b1):
                return row["figure_id"]
    from .extract import _section_letter
    from .figures import hash_window

    role = _get(frag, "role") or "riff"
    _form, token = _section_letter(_get(frag, "raw_marker") or "")
    if token:
        return "%s-%s" % (role, token)
    return "cell-" + hash_window([frag])


def _first_window_bars(fig_row, by_mi):
    """The first occurrence's bars, mapped to the extracted one-bar fragments."""
    occ = fig_row.get("occurrences") or []
    if not occ:
        return None
    first = occ[0]
    b0, b1 = first.get("start_bar"), first.get("end_bar")
    if b0 is None or b1 is None:
        return None
    bars = []
    for bar in range(int(b0), int(b1) + 1):
        frag = by_mi.get(bar - 1)
        if frag is None:
            return None
        bars.append(frag)
    return bars or None


def _representative(fid, entries, fig_row, by_mi):
    """`(bars, source)` for one figure: hashed window when present, else the
    longest run of identical bar fingerprints, else the first 1-2 bars."""
    if fig_row is not None:
        n_bars = fig_row.get("n_bars")
        if isinstance(n_bars, int) and 2 <= n_bars <= 4:
            bars = _first_window_bars(fig_row, by_mi)
            if bars:
                return bars[:4], "window"

    # Longest run of consecutive entries sharing a bar fingerprint.
    best: list = []
    run: list = []
    for entry in entries:
        if run and entry["fp"] == run[-1]["fp"]:
            run.append(entry)
        else:
            run = [entry]
        if len(run) > len(best):
            best = run
    if len(best) >= 2:
        if len(best) % 2 == 0:
            return [e["frag"] for e in best[:2]], "run-even"
        return [best[0]["frag"], best[0]["frag"]], "run-odd"

    return [e["frag"] for e in entries[:2]] or [entries[0]["frag"]], "first"


def assemble_cells(
    fragments, slots, human_boxes, fig_rows, trusted,
    *, source_song="", album="", track="",
) -> tuple[list[dict], int]:
    """Pure: one representative cell per figure. Returns `(cells, skipped_long)`
    where `skipped_long` counts human boxes longer than 4 bars reduced to a
    cell. Fake fragments/slots are fine -- no GP parsing here."""
    from .figures import hash_window

    by_mi = {int(_get(f, "measure_index", 0)): f for f in fragments}
    entries: list[dict] = []
    for (mi, sec, bar, dur) in slots:
        frag = by_mi.get(int(mi))
        if frag is None:
            continue
        entries.append({
            "mi": int(mi), "bar": int(bar), "sec": float(sec), "dur": float(dur),
            "frag": frag, "fp": hash_window([frag]),
            "fid": _name_bar(frag, float(sec), human_boxes, fig_rows, trusted),
        })

    fig_by_id = {r.get("figure_id"): r for r in fig_rows}

    skipped_long = 0
    if trusted and human_boxes:
        for hb in human_boxes:
            if not hb.get("figure_id"):
                continue
            start, end = hb.get("start"), hb.get("end")
            if start is None or end is None:
                continue
            covered = [e for e in entries
                       if float(start) <= e["sec"] <= float(end)]
            if len(covered) > 4:
                skipped_long += 1

    groups: dict[str, list[dict]] = {}
    for entry in entries:
        groups.setdefault(entry["fid"], []).append(entry)

    cells: list[dict] = []
    for fid, group in groups.items():
        fig_row = fig_by_id.get(fid)
        bars, _how = _representative(fid, group, fig_row, by_mi)
        if fig_row is not None and fig_row.get("occurrences"):
            occ = [{"start": o.get("start") if trusted else None,
                    "end": o.get("end") if trusted else None,
                    "start_bar": o.get("start_bar"), "end_bar": o.get("end_bar")}
                   for o in fig_row["occurrences"]]
        else:
            occ = [{"start": e["sec"] if trusted else None,
                    "end": (e["sec"] + e["dur"]) if trusted else None,
                    "start_bar": e["bar"], "end_bar": e["bar"]} for e in group]

        cell, deltas, chord_notes, chord_frets = _concat(bars)
        first = bars[0]
        cells.append({
            "figure_id": fid, "n_bars": len(bars), "source": "cell",
            "source_song": source_song, "album": album, "track": track,
            "start_bar": _bar_of(first), "end_bar": _bar_of(bars[-1]),
            "occurrences": occ,
            # riff_bank-compatible fields so export-bank still works
            "source_file": _get(first, "source_file") or "",
            "measure_index": int(_get(first, "measure_index", 0) or 0),
            "track": _get(first, "track") or "",
            "cell": cell, "deltas": deltas,
            "role": _get(first, "role"), "raw_marker": _get(first, "raw_marker"),
            "instrument": _get(first, "instrument") or "guitar",
            "source_type": "tab_verbatim",
            "chord_notes": chord_notes, "chord_frets": chord_frets,
        })
    return cells, skipped_long


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


def _human_boxes(lab_root: Path, album: str, track: str) -> list[dict]:
    from .schema import load_section_rows

    rows = load_section_rows(Path(lab_root) / "data" / "sections.jsonl", keepers_only=True)
    out = []
    for rec in rows:
        if (rec.get("album") or "") != album or (rec.get("track") or "") != track:
            continue
        if rec.get("figure_id") and rec.get("start") is not None and rec.get("end") is not None:
            out.append({"figure_id": rec["figure_id"],
                        "start": float(rec["start"]), "end": float(rec["end"])})
    return out


def _sync_ok(lab_root: Path, album: str, track: str) -> bool:
    for rec in _read_jsonl(Path(lab_root) / "data" / "sync.jsonl"):
        if (rec.get("album") or "") == album and (rec.get("track") or "") == track:
            return rec.get("sync_ok") is True
    return False


def song_cells(lab_root, row, fragments=None, *, human_boxes=None,
               fig_rows=None, trusted=None, notes_source="gp",
               pack=None) -> tuple[list[dict], int]:
    """Assemble one song's cells. `fragments` may be pre-extracted dicts
    (extract_riffs); otherwise the source's own extractor is called --
    `extract_riffs` for GP (default), `extract_riffs_from_pack` for a pack.
    Reads only the lab stores."""
    from .figures import _playback_slots, _tab_fragments_and_slots, load_figures

    album = row.get("album") or ""
    track = row.get("track") or ""
    if human_boxes is None:
        human_boxes = _human_boxes(Path(lab_root), album, track)
    if fig_rows is None:
        fig_rows = load_figures(lab_root, album, track)
    if trusted is None:
        trusted = _sync_ok(Path(lab_root), album, track)

    if notes_source == "gp":
        from .extract import _engine_riff_bank

        gp_raw = row.get("gp_path") or row.get("gp") or ""
        gp = Path(gp_raw) if gp_raw else None
        if gp is None or not gp.exists():
            return [], 0
        try:
            if fragments is None:
                fragments = _engine_riff_bank().extract_fragments_from_file(
                    gp, song_title=track)
            slots = _playback_slots(gp)
        except Exception:
            return [], 0
    elif notes_source == "pack":
        if pack is None:
            return [], 0
        from . import extract

        try:
            if fragments is None:
                sections = extract.load_human_sections(
                    Path(lab_root) / "data").get((album, track))
                fragments = extract.extract_riffs_from_pack(
                    pack, track, human_sections=sections)
            _frags2, slots = _tab_fragments_and_slots(pack)
        except Exception:
            return [], 0
    else:
        return [], 0

    if not fragments or not slots:
        return [], 0
    return assemble_cells(fragments, slots, human_boxes, fig_rows, trusted,
                          source_song=track, album=album, track=track)


def build_cells(lab_root, rows, *, album=None, track=None) -> dict:
    """Write one representative cell per figure to `data/riffs.jsonl`.

    Replaces only the songs it rebuilt; a run that yields zero cells leaves an
    existing file untouched (same law as beats/figures)."""
    lab_root = Path(lab_root)
    out = lab_root / "data" / "riffs.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    if album and track:
        from .catalogue import resolve_row

        target = resolve_row(rows, album, track)
        if target is not None:
            album = target.get("album") or album
            track = target.get("track") or track
    akey = album.casefold() if album else None
    tkey = track.casefold() if track else None

    from .schema import write_jsonl_atomic

    produced: list[dict] = []
    rebuilt: set[tuple[str, str]] = set()
    figure_ids: set[str] = set()
    songs = 0
    skipped = 0
    skipped_long = 0

    for r in rows:
        ra = r.get("album") or ""
        rt = r.get("track") or ""
        if akey is not None and ra.casefold() != akey:
            continue
        if tkey is not None and rt.casefold() != tkey:
            continue
        matched = (r.get("match") or "").lower() in {"yes", "y", "1", "true"}
        gp_raw = r.get("gp_path") or r.get("gp") or ""
        if not matched or not gp_raw or not Path(gp_raw).exists():
            skipped += 1
            continue
        cells, long_spans = song_cells(lab_root, r)
        rebuilt.add((ra, rt))
        songs += 1
        skipped_long += long_spans
        if cells:
            produced.extend(cells)
            figure_ids.update(c["figure_id"] for c in cells)
        print("CELLS", rt, len(cells), "cell(s)")

    if not produced:
        print("cells: 0 rows written; leaving", out.name, "untouched")
        return {"figures": 0, "cells": 0, "skipped": skipped,
                "skipped_long_spans": 0, "out": str(out)}

    existing = _read_jsonl(out)
    keep = [x for x in existing if (x.get("album"), x.get("track")) not in rebuilt]
    write_jsonl_atomic(out, keep + produced)
    return {"figures": len(figure_ids), "cells": len(produced), "skipped": skipped,
            "skipped_long_spans": skipped_long, "out": str(out)}
