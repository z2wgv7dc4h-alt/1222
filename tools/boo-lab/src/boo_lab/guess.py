from __future__ import annotations

import json
import os
import re
from pathlib import Path


def _delab_figure_id(sections: list[dict]) -> int:
    """Rewrite a FIGURE box's figure_id prefix when it's still an
    engine/MSA alias (verse-A, chorus-B) instead of this project's own
    lab role -- keeps the letter/number suffix untouched. Function
    boxes (breakdown/blast/...) are never touched, even if one somehow
    carries a hyphenated figure_id. Returns how many were rewritten."""
    from .schema import FIGURE_ROLES, canonical_role

    fixed = 0
    for s in sections:
        role = canonical_role(s.get("role"))
        if role not in FIGURE_ROLES:
            continue
        fid = s.get("figure_id") or ""
        prefix, sep, suffix = fid.partition("-")
        if sep and prefix.lower() != role and canonical_role(prefix) == role:
            s["figure_id"] = role + sep + suffix
            fixed += 1
    return fixed


def _gp5_roots() -> list[Path]:
    """GP search roots from `BOO_GP_ROOT` only (`gp5/`, `gp7/`, then root).

    No machine-local path fallbacks. Empty env yields an empty list.
    """
    env = os.environ.get("BOO_GP_ROOT")
    if not env:
        return []
    p = Path(env)
    roots = [p / "gp5", p / "gp7", p]
    seen: list[Path] = []
    for r in roots:
        if r not in seen:
            seen.append(r)
    return seen


GP5_ROOTS = _gp5_roots()

# GP6/GP7 GPIF container suffixes; these are read by `gpif.load_score`, not
# the guitarpro (GP3-5) parser.
GP7_EXTS = (".gp", ".gpx")


def _norm(s: str) -> str:
    s = (s or "").replace("∆", "A").replace("Δ", "A").replace("δ", "a").lower()
    s = re.sub(r"^\d+\s*[-_.]\s*", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def _prefer_tab(gp: Path | None, track: str) -> Path | None:
    """Map-path tab preference: a GP7/GP6 score (`gpif.load_score`) outranks a
    `.gp5`, the same priority sync uses. A `.gp`/`.gpx` path is returned as-is;
    a `.gp5` is upgraded to its matching GP7 via `sync._prefer_gpif_path`;
    otherwise roots are searched by normalized stem, GP7 before GP5."""
    p = Path(gp) if gp else None
    if p is not None and p.suffix.lower() in GP7_EXTS and p.exists():
        return p
    if p is not None and p.suffix.lower() == ".gp5":
        try:
            from .sync import _prefer_gpif_path

            cand = Path(_prefer_gpif_path(p))
        except Exception:
            cand = p
        if cand.suffix.lower() in GP7_EXTS and cand.exists():
            return cand
    key = _norm(track)
    if not key and p is not None:
        # "Born_Of_Osiris-Recreate-s77727" -> recreate
        raw = _norm(p.stem)
        raw = re.sub(r"^bornofosiris", "", raw)
        raw = re.sub(r"s\d+$", "", raw)
        key = raw
    if key:
        gp5_fallback = p if (p is not None and p.suffix.lower() == ".gp5"
                             and p.exists()) else None
        for want_gp7 in (True, False):
            exts = GP7_EXTS if want_gp7 else (".gp5",)
            for root in _gp5_roots():
                if not root.exists():
                    continue
                for ext in exts:
                    try:
                        hits = root.rglob("*" + ext)
                    except Exception:
                        continue
                    for hit in hits:
                        n = _norm(hit.stem)
                        if n == key or key in n or n in key:
                            if want_gp7:
                                return hit
                            if gp5_fallback is None:
                                gp5_fallback = hit
        if gp5_fallback is not None:
            return gp5_fallback
    if p is not None and p.suffix.lower() in GP7_EXTS + (".gp5", ".gp4", ".gp3") and p.exists():
        return p
    return None


# Backward-compat alias; annotator.py still imports `_prefer_gp5`.
_prefer_gp5 = _prefer_tab


def _resolve_names(lab_root: Path, album: str, track: str) -> tuple[str, str]:
    """Map a studio-style name to the `map.csv` album/track (year-prefixed
    folders, track punctuation), the same resolver sync/hear use. Passes the
    typed pair through when incomplete or unmatched."""
    try:
        from .catalogue import load_map, resolve_row

        mp = Path(lab_root) / "data" / "map.csv"
        if mp.exists() and album and track:
            row = resolve_row(load_map(mp), album, track)
            if row is not None:
                return row.get("album") or album, row.get("track") or track
    except Exception:
        pass
    return album, track


def _sync_for(lab_root: Path | None, album: str, track: str) -> dict | None:
    """The recorded tab-vs-audio witness for one song (`data/sync.jsonl`), or
    `None` when it was never run. Lets Guess refuse to emit tab-marker times
    for a tab already measured as misaligned."""
    if lab_root is None:
        return None
    path = Path(lab_root) / "data" / "sync.jsonl"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (rec.get("track") or "") != track:
            continue
        if album and (rec.get("album") or "") != album:
            continue
        return rec
    return None


def _beats_for(lab_root: Path | None, album: str, track: str) -> dict | None:
    """The recorded beat/downbeat grid for one song (`data/beats.jsonl`)."""
    if lab_root is None:
        return None
    path = Path(lab_root) / "data" / "beats.jsonl"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (rec.get("track") or "") != track:
            continue
        if album and (rec.get("album") or "") != album:
            continue
        return rec
    return None


def _snap_to_grid(t: float, downbeats, beats) -> float:
    """Nearest downbeat within 250 ms, else nearest beat within 120 ms, else `t`.
    Audio-derived spans are already in audio time, so the beat grid applies."""
    best = None
    bd = 1e9
    for c in downbeats or []:
        d = abs(c - t)
        if d < bd:
            bd, best = d, c
    if best is not None and bd <= 0.25:
        return best
    for c in beats or []:
        d = abs(c - t)
        if d < bd:
            bd, best = d, c
    return best if (best is not None and bd <= 0.12) else t


# figures.jsonl's own `instrument` vocabulary (guitar/bass/other -- see
# figures.py) is internal bookkeeping, not the studio's `inst` dropdown
# vocabulary (rhythm/lead/bass/drums/synth/vocal/mix, annotator.html
# INSTRUMENTS). `bass` and `other` (a Pulse track) map cleanly; a `guitar`
# row is deliberately left blank -- checked on a real corpus song that mean
# pitch alone doesn't reliably separate rhythm from lead, so this never
# guesses which one a guitar figure is.
_FIGURE_INSTRUMENT_TO_UI = {"bass": "bass", "other": "synth"}


def _figure_drafts(lab_root, album: str, track: str, existing: list[dict],
                   tol: float = 0.35) -> list[dict]:
    """Unheard riff drafts from `figures.jsonl` occurrences with trusted times.

    Includes unique (non-repeating) rows — they still need `times_trusted` so
    seconds came from a sync_ok clock. Skips a span a marker already covers
    within `tol` with the same `figure_id`."""
    from .figures import load_figures

    out: list[dict] = []
    for row in load_figures(lab_root, album, track):
        if not row.get("times_trusted"):
            continue
        fid = row.get("figure_id")
        role = row.get("role") or "riff"
        inst = _FIGURE_INSTRUMENT_TO_UI.get(row.get("instrument") or "", "")
        for occ in row.get("occurrences") or []:
            start, end = occ.get("start"), occ.get("end")
            if start is None or end is None:
                continue
            start, end = float(start), float(end)
            dup = any(
                abs(float(s.get("start", 0.0)) - start) <= tol
                and abs(float(s.get("end", 0.0)) - end) <= tol
                and (s.get("figure_id") or "") == (fid or "")
                for s in existing
            )
            if dup:
                continue
            out.append({
                "role": role, "start": round(start, 3), "end": round(end, 3),
                "figure_id": fid, "form": row.get("form") or "A",
                "unique": bool(row.get("unique")), "instrument": inst,
                "start_bar": occ.get("start_bar"), "end_bar": occ.get("end_bar"),
                "source": "guess", "heard": False,
            })
    return out


def _gate_breakdowns(sections: list[dict], blob: dict | None) -> int:
    """Keep audio breakdown drafts whose span is 0.5-1.5x the album's median
    heard breakdown span (n>=2). n<2 leaves current behavior. Returns kept."""
    bd = (blob or {}).get("breakdowns") or {}
    n = int(bd.get("n") or 0)
    median = float(bd.get("median_span_sec") or 0.0)
    audio = [s for s in sections
             if s.get("role") == "breakdown" and s.get("source") in {"halftime", "kick"}]
    if n < 2 or median <= 0:
        return len(audio)
    kept = 0
    for s in list(audio):
        span = float(s.get("end", 0.0)) - float(s.get("start", 0.0))
        if 0.5 * median <= span <= 1.5 * median:
            kept += 1
        else:
            sections.remove(s)
    return kept


def _gate_blasts(sections: list[dict], blob: dict | None) -> int:
    """Keep blast-hint drafts whose span is 0.5-1.5x the album's median heard
    blast span (n>=2), the same per-album gate as `_gate_breakdowns`. n<2
    leaves the current rules. Returns kept."""
    bd = (blob or {}).get("blasts") or {}
    n = int(bd.get("n") or 0)
    median = float(bd.get("median_span_sec") or 0.0)
    audio = [s for s in sections
             if s.get("role") == "blast" and s.get("source") == "blast-hint"]
    if n < 2 or median <= 0:
        return len(audio)
    kept = 0
    for s in list(audio):
        span = float(s.get("end", 0.0)) - float(s.get("start", 0.0))
        if 0.5 * median <= span <= 1.5 * median:
            kept += 1
        else:
            sections.remove(s)
    return kept


def _blast_spans(drum, *, min_len: float = 1.0) -> list[dict]:
    """Full-speed ('blast') spans from a REAL isolated drum stem. Each onset is
    classified by the engine's own `classify_drum_onsets` (through
    `drums_extract.classify_drums`, never a second classifier), then the
    kick+snare hits are grouped by the existing onset-density detector
    (`tabnotes_drafts._dense_spans`) -- a blast is a stretch whose local
    kick+snare rate is far above the song's average, the strict opposite of a
    half-time breakdown. `[]` when there is no stem, the classifier is
    unavailable, or nothing stands out. `source="blast-hint"`, FLAC clock."""
    if drum is None:
        return []
    try:
        from .drums_extract import classify_drums

        onsets = classify_drums(Path(drum))
    except Exception:
        return []
    times = sorted(float(o["time"]) for o in onsets
                   if o.get("role") in ("kick", "snare"))
    if len(times) < 24:
        return []
    try:
        from .tabnotes_drafts import _dense_spans
    except Exception:
        return []
    return [
        {"role": "blast", "start": round(s, 3), "end": round(e, 3),
         "source": "blast-hint"}
        for s, e in _dense_spans(times, min_len=min_len)
    ]


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


# A tab whose own markers spell out the song already carries the section
# spine. These bound how much figure-hash material Guess may still pile on
# top: N markers or half the duration makes markers PRIMARY; then no draft
# shorter than 4 s, and nothing that overlaps a marker at all.
GP_MARKER_MIN = 4
GP_MARKER_COVER_FRAC = 0.5
FIGURE_DRAFT_MIN_SPAN = 4.0
MARKER_OVERLAP_TOL = 0.35

# A tab-notes pack with no GP still carries a structure spine
# (`tabnotes-structure`). It is the structural equal of `gp-marker`: whenever
# one exists it caps the figure-hash flood the same way. The list source is a
# separate source string so Guess can tell a pack spine from a GP marker.
PACK_STRUCTURE_SOURCE = "tabnotes-structure"
PACK_PHRASE_SOURCE = "tabnotes-phrase"
SPINE_SOURCES = frozenset({"gp-marker", PACK_STRUCTURE_SOURCE, PACK_PHRASE_SOURCE})

# Load-draft sources (`Load drafts`) are never Guess output -- Guess is the
# tab+audio hybrid only.
LOAD_DRAFT_SOURCES = frozenset({"msa-draft", "songformer-draft"})


def _positive_span(s: dict) -> tuple[float, float] | None:
    try:
        start, end = float(s.get("start")), float(s.get("end"))
    except (TypeError, ValueError):
        return None
    return (start, end) if end > start else None


def _merge_spans(spans) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1] + 1e-6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _span_list(sections: list[dict], sources) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for s in sections:
        if s.get("source") in sources:
            p = _positive_span(s)
            if p is not None:
                out.append(p)
    return _merge_spans(out)


def _spine_spans(sections: list[dict]) -> list[tuple[float, float]]:
    """Merged `(start, end)` spans of the structural spine: the tab's own
    `gp-marker` boxes and/or a tab-notes pack's `tabnotes-structure` boxes."""
    return _span_list(sections, SPINE_SOURCES)


def _marker_spans(sections: list[dict]) -> list[tuple[float, float]]:
    """Merged `(start, end)` spans of the tab's own `gp-marker` boxes."""
    return _span_list(sections, {"gp-marker"})


def _markers_primary(sections: list[dict], duration: float | None = None) -> bool:
    """True when the tab's own markers are the spine of the song: at least
    `GP_MARKER_MIN` of them, or they cover `GP_MARKER_COVER_FRAC` of the
    known duration. Markers then outrank figure-hash drafts."""
    n = sum(1 for s in sections if s.get("source") == "gp-marker")
    if n == 0:
        return False
    if n >= GP_MARKER_MIN:
        return True
    if duration and duration > 0:
        covered = sum(e - s for s, e in _marker_spans(sections))
        if covered / float(duration) >= GP_MARKER_COVER_FRAC:
            return True
    return False


def _spine_primary(sections: list[dict], duration: float | None = None) -> bool:
    """True when GP/tab markers outrank the figure-hash stream.

    Pack activity spine (`tabnotes-structure`) is coverage only — it must NOT
    suppress unique/repeating figure drafts or pack-only songs stay empty.
    """
    return _markers_primary(sections, duration)


def _in_marker_gap(start: float, end: float, spans, tol: float) -> bool:
    return all(_overlap(start, end, s, e) <= tol for s, e in spans)


def _suppress_figure_flood(drafts: list[dict], sections: list[dict], *,
                           duration: float | None = None,
                           min_span: float = FIGURE_DRAFT_MIN_SPAN,
                           tol: float = MARKER_OVERLAP_TOL) -> list[dict]:
    """Cap figure-hash drafts against the structural spine.

    With any spine box present, a non-unique figure draft shorter than
    `min_span` is dropped (unique pack runs may be as short as 2s).
    When GP markers make the spine primary (`_spine_primary`), a draft
    that overlaps them is dropped too, so only uncovered gaps get filled.
    Pack activity spine alone is not primary. A
    returning marker letter is already the same `figure_id`, so the pile of
    short hashes is noise. Function overlays (breakdown/blast/kick) are not
    figure drafts and pass through untouched."""
    spans = _spine_spans(sections)
    if not spans:
        return drafts
    primary = _spine_primary(sections, duration)
    out: list[dict] = []
    for d in drafts:
        try:
            start, end = float(d["start"]), float(d["end"])
        except (KeyError, TypeError, ValueError):
            continue
        need = 2.0 if d.get("unique") else min_span
        if end - start < need:
            continue
        if primary and not _in_marker_gap(start, end, spans, tol):
            continue
        out.append(d)
    return out


def _link_on_figure(sections: list[dict]) -> int:
    """Light figure<->function link: every FUNCTION box (breakdown/blast/build/
    chill/intro/outro) that overlaps a FIGURE box (riff/hook/solo/pulse) gets
    `on_figure` = that figure's `figure_id`, best overlap by duration. Only
    fills an empty link (never overwrites a human's) and never invents a
    figure name. Returns how many boxes were linked."""
    from .schema import FIGURE_ROLES, FUNCTION_ROLES, canonical_role

    figures = [s for s in sections
               if canonical_role(s.get("role")) in FIGURE_ROLES and s.get("figure_id")]
    linked = 0
    for s in sections:
        if canonical_role(s.get("role")) not in FUNCTION_ROLES:
            continue
        if (s.get("on_figure") or "").strip():
            continue
        try:
            a0, a1 = float(s.get("start")), float(s.get("end"))
        except (TypeError, ValueError):
            continue
        best_id, best_ov = None, 0.0
        for f in figures:
            try:
                f0, f1 = float(f.get("start")), float(f.get("end"))
            except (TypeError, ValueError):
                continue
            ov = _overlap(a0, a1, f0, f1)
            if ov > best_ov:
                best_id, best_ov = f.get("figure_id"), ov
        if best_id:
            s["on_figure"] = best_id
            linked += 1
    return linked


def estimate_hybrid(
    flac: Path | None,
    gp: Path | None,
    track: str = "",
    cache: Path | None = None,
    album: str = "",
) -> dict:
    notes: list[str] = []
    sections: list[dict] = []
    bpm = None
    beats: list[float] = []
    lab_root = Path(cache).parent.parent if cache else None
    lookup_album, lookup_track = album, track
    if lab_root is not None:
        lookup_album, lookup_track = _resolve_names(lab_root, album, track)

    gp_use = _prefer_tab(gp, track)
    sync_rec = _sync_for(lab_root, lookup_album, lookup_track)

    from .precedence import tab_plan

    plan = tab_plan(lab_root, lookup_album, lookup_track, gp_path=gp)

    key = _norm(track) or _norm(gp.stem if gp else "")
    seen = 0
    roots = _gp5_roots()
    root0 = roots[0] if roots else Path(".")
    if roots and root0.exists():
        seen = sum(1 for _ in root0.rglob("*.gp5"))
    notes.append("key=%s gp5=%s files=%s" % (key or "?", root0 if roots else "(no BOO_GP_ROOT)", seen))
    if gp_use:
        notes.append("tab " + str(gp_use))
        try:
            if Path(gp_use).suffix.lower() in GP7_EXTS:
                # GP7/GP6 (.gp/.gpx): GPIF is the reader sync already uses.
                from .extract import estimate_from_gpif

                g = estimate_from_gpif(gp_use)
            else:
                from .extract import estimate_from_gp

                g = estimate_from_gp(gp_use)
            bpm = g.get("bpm") or bpm
            if g.get("sections"):
                if plan["spine"] != "gp-marker":
                    # Gate: don't propose times from a tab measured as misaligned.
                    lag = sync_rec.get("lag_sec")
                    notes.append(
                        "tab markers dropped: sync not ok%s — paint by hand (`boo-lab sync`)"
                        % ("" if lag is None else " (lag %.2fs)" % lag)
                    )
                else:
                    # A rate-aligned tab is notated off by a fixed ratio: apply
                    # that stretch before the rest of the pipeline (audio-only
                    # drafts already live on the FLAC clock and are untouched).
                    markers = g["sections"]
                    ratio = None
                    if sync_rec is not None and sync_rec.get("sync_ok") is True:
                        try:
                            ratio = float(sync_rec.get("clock_ratio"))
                        except (TypeError, ValueError):
                            ratio = None
                    if ratio is not None and abs(ratio - 1.0) >= 0.002:
                        for s in markers:
                            s["start"] = round(float(s["start"]) * ratio, 3)
                            s["end"] = round(float(s["end"]) * ratio, 3)
                        print("guess: clock_ratio=%.3f stretched %d markers"
                              % (ratio, len(markers)))
                        notes.append("clock_ratio=%.3f stretched %d markers"
                                     % (ratio, len(markers)))
                    sections.extend(markers)
                    notes.append("gp markers" + (" (sync ok)" if sync_rec is not None else ""))
            else:
                notes.append(g.get("reason") or "tab has no markers")
        except Exception as e:
            notes.append("gp parse: %s" % e)
    else:
        notes.append("no tab")

    real_duration = None
    if flac and Path(flac).exists():
        try:
            import soundfile as sf

            info = sf.info(str(flac))
            real_duration = info.frames / info.samplerate
        except Exception:
            pass

    if flac and Path(flac).exists():
        src = Path(flac)
        if cache:
            from .stems import ensure_drums

            drum, why = ensure_drums(Path(flac), cache)
            notes.append(why)
            if drum:
                src = drum
        else:
            drum = _drum_stem(Path(flac))
            if drum:
                src = drum
                notes.append("drums " + drum.name)
        try:
            m = _librosa_beats(src)
            beats = m.get("beats") or []
            if m.get("bpm"):
                bpm = m["bpm"]
            ht = _half_time_spans(beats)
            sections.extend(ht)
            if ht:
                notes.append("librosa half-time x%s" % len(ht))
            else:
                notes.append("librosa beats, no half-time")
        except ImportError:
            notes.append("pip install librosa soundfile")
        except Exception as e:
            notes.append("beats: %s" % e)
        # A tab-notes pack's own kick notation beats a spectral guess, same
        # "human/tab data outranks an audio heuristic" precedent as GP
        # markers -- only when the audio clock actually matched (sync_ok),
        # since the spans are seconds off that pack's own clock.
        tab_kicks: list[dict] = []
        if plan["kicks"]:
            try:
                from .tabnotes import discover_pack, load_pack

                pack_path = discover_pack(lab_root, lookup_album, lookup_track)
                if pack_path is not None:
                    tab_kicks = _tab_kick_spans(load_pack(pack_path))
            except Exception:
                tab_kicks = []
        if tab_kicks:
            sections.extend(tab_kicks)
            notes.append("kick notation x%s (tab)" % len(tab_kicks))
        else:
            try:
                kicks = _kick_spans(src)
                if kicks:
                    sections.extend(kicks)
                    notes.append("kick IOI x%s" % len(kicks))
            except ImportError:
                pass
            except Exception as e:
                notes.append("kick: %s" % e)
        # Blast hint: the strict opposite of the half-time breakdown -- a
        # stretch whose kick+snare onsets (engine classifier, not a second
        # one) are far denser than the song's average. On the FLAC clock, so
        # no sync gate, exactly like the audio kick/half-time breakdowns;
        # only a real isolated drum stem is trusted. Drafts only.
        blast_drafts = _blast_spans(drum) if drum else []
        if blast_drafts:
            sections.extend(blast_drafts)
            notes.append("blast hint x%d" % len(blast_drafts))

    if cache:
        try:
            from .learn import preferred_source

            if preferred_source(cache.parent.parent) == "guess":
                notes.append("prefer=guess")
        except Exception:
            pass

    # Snap the audio-derived spans (halftime/kick/blast) to the recorded grid.
    grid = _beats_for(lab_root, lookup_album, lookup_track)
    if grid and grid.get("beats"):
        snapped = 0
        for s in sections:
            if s.get("source") in {"halftime", "kick", "blast-hint"}:
                for key in ("start", "end"):
                    nt = _snap_to_grid(float(s[key]), grid.get("downbeats"), grid.get("beats"))
                    if abs(nt - s[key]) > 1e-6:
                        s[key] = round(nt, 3)
                        snapped += 1
        if snapped:
            notes.append("snapped %d audio boundary/ies to the beat grid" % snapped)

    # Per-album calibration blob (load once; used by the gate and apply below).
    adapt_blob = None
    try:
        from .adapt import load_adapt

        adapt_blob = load_adapt(lab_root, lookup_album) if lab_root is not None else None
    except Exception:
        adapt_blob = None

    # Pack structure/phrase spine eligibility is the shared tab/pack
    # precedence decision (`precedence.tab_plan`, which discovers the real
    # files): trusted sync and no GP markers -> pack may be the spine.
    pack_spine_eligible = lab_root is not None and plan["spine"] == "pack"

    # Pack structure spine: when the map has no GP markers but a tab-notes
    # pack is discovered and its clock matched (`sync_ok`), the pack's own
    # high-density guitar phrases are the spine -- the structural equal of
    # `gp-marker`, just without a GP. Roles come from the pack's real note
    # density (`riff`), figure ids are simple `riff-A/B/C` by order; no
    # GP-style A1/B letters are invented because the pack has none. Drum
    # functions already ride on top through `_tab_kick_spans`/`_blast_spans`.
    # Marker songs are untouched: markers stay the spine.
    pack_spine = 0
    if pack_spine_eligible:
        try:
            from .tabnotes_drafts import structure_drafts_for_song

            spine = structure_drafts_for_song(lab_root, lookup_album, lookup_track)
        except Exception:
            spine = []
        if spine:
            sections.extend(spine)
            pack_spine = len(spine)
            notes.append("pack structure x%d (tabnotes spine)" % pack_spine)

    # Pack phrase boxes: mid-grain structure for pack-only songs (not the
    # ~4 coverage spine, not unique 2-bar hash spam). Replaces pack spine when
    # present. GP markers still win and stay primary for figure-hash suppress.
    pack_phrases = 0
    if pack_spine_eligible:
        try:
            from .tabnotes_drafts import phrase_drafts_for_song

            phrases = phrase_drafts_for_song(lab_root, lookup_album, lookup_track)
        except Exception:
            phrases = []
        if phrases:
            sections.extend(phrases)
            pack_phrases = len(phrases)
            notes.append("pack phrases x%d (tabnotes phrase)" % pack_phrases)
            if pack_spine > 0:
                sections[:] = [s for s in sections
                               if s.get("source") != PACK_STRUCTURE_SOURCE]
                notes.append("pack spine replaced by phrases x%d" % pack_phrases)
                pack_spine = 0

    # Figure windows as unheard riff drafts -- only when the tab clock matched
    # and the occurrence seconds are trusted. Prefer repeating clusters; skip
    # unique one-shots when pack phrases already carry structure (avoids the
    # Mindful 60-box flood). GP markers still primary-cap the rest.
    figures_drafts = 0
    if plan["sync_ok"]:
        new_figs = _figure_drafts(lab_root, lookup_album, lookup_track, sections)
        # When this song already has a repeating figure (any non-unique
        # cluster), the unique one-shot hashes are noise beside it -- drop
        # them. A song with ONLY unique hashes keeps them, so Guess is not
        # empty. Pack phrases remain a separate reason to drop unique hashes.
        if pack_phrases > 0 or any(not d.get("unique") for d in new_figs):
            new_figs = [d for d in new_figs if not d.get("unique")]
        kept = _suppress_figure_flood(new_figs, sections, duration=real_duration)
        if len(kept) != len(new_figs):
            notes.append("figure drafts capped x%d (structure spine)"
                         % (len(new_figs) - len(kept)))
        sections.extend(kept)
        figures_drafts = len(kept)
        if figures_drafts > 0 and pack_spine > 0 and pack_phrases == 0:
            sections[:] = [s for s in sections
                           if s.get("source") != PACK_STRUCTURE_SOURCE]
            notes.append(
                "pack spine replaced by figure drafts x%d" % figures_drafts
            )
            pack_spine = 0

    # Pack density drafts: high guitar-onset-density spans as unheard riff
    # drafts from the pack's own audio-clock onsets. Riff only here -- the
    # pack's drum breakdowns already come through `_tab_kick_spans` above.
    # Skipped when the pack spine already supplied those phrases. Only when
    # sync_ok; never a box off an untrusted clock.
    density_drafts = 0
    if pack_spine == 0 and pack_phrases == 0 and plan["sync_ok"]:
        try:
            from .tabnotes_drafts import density_drafts_for_song

            new_density = density_drafts_for_song(
                lab_root, lookup_album, lookup_track, roles=("riff",))
        except Exception:
            new_density = []
        new_density = _suppress_figure_flood(new_density, sections, duration=real_duration)
        if new_density:
            sections.extend(new_density)
            density_drafts = len(new_density)
            notes.append("tabnotes density x%d" % density_drafts)

    # Keeper-trained structure drafts already written by `boo-lab predict` for
    # this song are merged unheard (read-only; Guess never runs the model here,
    # so it stays fast). Skipped spans already covered keep it non-destructive.
    keeper_model_drafts = 0
    if lab_root is not None:
        try:
            from .predict import load_keeper_model_drafts

            new_km = load_keeper_model_drafts(
                lab_root, lookup_album, lookup_track, sections)
            if new_km:
                sections.extend(new_km)
                keeper_model_drafts = len(new_km)
                notes.append("keeper-model drafts x%d" % len(new_km))
        except Exception:
            keeper_model_drafts = 0

    # Meter/tempo cuts: measure boundaries where the pack's time signature
    # changes or its tempo automation jumps. Soft hints -- a note for the
    # human plus an edge snap for the audio-derived/density spans, never a new
    # box. Only when the clock matched.
    meter_cuts: list[float] = []
    if plan["meter_cuts"]:
        try:
            from .tabnotes_drafts import meter_cuts_for_song, snap_sections_to_cuts

            meter_cuts = meter_cuts_for_song(
                lab_root, lookup_album, lookup_track, gp_path=gp_use)
        except Exception:
            meter_cuts = []
        if meter_cuts:
            shown = ", ".join("%.1fs" % c for c in meter_cuts[:6]) + (
                " ..." if len(meter_cuts) > 6 else "")
            notes.append("tempo/meter cuts at %s" % shown)
            snapped = snap_sections_to_cuts(sections, meter_cuts)
            if snapped:
                notes.append("snapped %d edge(s) to tempo/meter cuts" % snapped)

    # Tempo-automation boundaries: informational only, never a box -- a BPM
    # jump correlates with a section change in this genre but never implies
    # a role, so it's surfaced as a note for the human, not auto-applied.
    if lab_root is not None:
        try:
            from .tempo_hints import load_tempo_hints

            hints = load_tempo_hints(lab_root, lookup_album, lookup_track)
        except Exception:
            hints = []
        if hints:
            trusted_hint = bool(hints[0].get("times_trusted"))
            shown = ", ".join(
                "%s %g->%g" % (("%.1fs" % h["sec"]) if h.get("sec") is not None else "?s",
                               h["bpm_before"], h["bpm_after"])
                for h in hints[:6]
            ) + (" ..." if len(hints) > 6 else "")
            notes.append("tempo changes x%d%s: %s" % (
                len(hints), "" if trusted_hint else " (sec untrusted; sync not ok)", shown))

    # Breakdown/blast gates: keep audio drafts near this album's median heard
    # span for that role (n>=2). n<2 keeps the current rules.
    breakdowns_used = _gate_breakdowns(sections, adapt_blob)
    blasts_used = _gate_blasts(sections, adapt_blob)
    print("pack_spine=%d pack_phrases=%d figures_drafts=%d density_drafts=%d "
          "breakdowns_used=%d blasts_used=%d"
          % (pack_spine, pack_phrases, figures_drafts, density_drafts,
             breakdowns_used, blasts_used))

    sections = _merge_adjacent_same_figure(sections)
    sections = _clean(sections)

    # Load-draft sources belong to the Load drafts button, never to Guess.
    # Defense in depth: if a future merge ever leaks one in, drop it here.
    stray = [s for s in sections if s.get("source") in LOAD_DRAFT_SOURCES]
    if stray:
        sections = [s for s in sections if s.get("source") not in LOAD_DRAFT_SOURCES]
        notes.append("dropped %d load-draft box(es) (msa/songformer) from Guess"
                     % len(stray))

    # Per-album calibration: shift/map draft boxes from the first accepted
    # pairs on this album. Keepers are never touched; silent when no blob.
    if adapt_blob and int(adapt_blob.get("n_pairs") or 0) >= 1:
        try:
            from .adapt import apply_adapt

            sections = apply_adapt(sections, adapt_blob)
            print("adapt: album=%s n_pairs=%d shift_start=%.3f"
                  % (lookup_album, adapt_blob["n_pairs"],
                     float(adapt_blob.get("shift_start") or 0.0)))
        except Exception:
            pass

    # Light figure<->function link: a function draft (breakdown/blast/...) that
    # sits on a figure draft (riff/hook/...) carries that figure's id as
    # `on_figure`, so the pair survives into the human's review together.
    # Never overwrites a link and never invents a figure name.
    linked = _link_on_figure(sections)
    if linked:
        notes.append("on_figure links x%d" % linked)

    # Real, honest coverage report -- librosa's beat/onset detectors can
    # (and do, confirmed on a real BoO track: a quiet outro with too
    # little low-frequency onset energy) run out of signal well before
    # the real audio's own actual end, silently. Never let that look like
    # "nothing more to label" -- say exactly how much of the real
    # duration Guess actually reached.
    if real_duration:
        covered_end = max([s["end"] for s in sections], default=0.0)
        if real_duration - covered_end > 5.0:
            pct = 100.0 * covered_end / real_duration
            notes.append(
                "Guess reached %.1fs of %.1fs (%.0f%%) -- %.1fs uncovered at the end, paint it by hand"
                % (covered_end, real_duration, pct, real_duration - covered_end)
            )

    relabeled = _delab_figure_id(sections)
    if relabeled:
        notes.append("relabeled %d alias figure_id(s) (verse/chorus -> lab roles)" % relabeled)

    return {"bpm": bpm, "beats": beats[:400], "sections": sections, "notes": notes, "duration": real_duration}


def _drum_stem(flac: Path) -> Path | None:
    stem = flac.stem
    parent = flac.parent
    cands = [
        parent / "stems" / (stem + ".wav"),
        parent / "stems" / (stem + ".drums.wav"),
        parent / "stems" / "drums.wav",
        parent / (stem + ".drums.wav"),
    ]
    for c in cands:
        if c.exists():
            return c
    return None


def _scalar(x):
    try:
        import numpy as np
        a = np.asarray(x).reshape(-1)
        return float(a[0]) if a.size else None
    except Exception:
        try:
            return float(x)
        except Exception:
            return None


def _flist(x):
    try:
        import numpy as np
        return [float(v) for v in np.asarray(x).reshape(-1)]
    except Exception:
        try:
            return [float(v) for v in list(x)]
        except Exception:
            return []


def _librosa_beats(wav: Path) -> dict:
    import librosa

    y, sr = librosa.load(str(wav), sr=22050, mono=True)
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr)
    beats = _flist(librosa.frames_to_time(frames, sr=sr))
    return {"beats": beats, "bpm": _scalar(tempo)}


def _kick_spans(wav: Path) -> list[dict]:
    import librosa
    import numpy as np

    y, sr = librosa.load(str(wav), sr=22050, mono=True)
    hop = 512
    spec = np.abs(librosa.stft(y, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr)
    band = spec[freqs < 140].mean(axis=0)
    env = librosa.util.normalize(band)
    times = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, units="time")
    spans = _half_time_spans(_flist(times), min_len=5.0)
    for s in spans:
        s["source"] = "kick"
        s["role"] = "breakdown"
    return spans


def _half_time_spans(beats: list[float], min_len: float = 6.0) -> list[dict]:
    if len(beats) < 24:
        return []
    ioi = [b - a for a, b in zip(beats, beats[1:])]
    med = sorted(ioi)[len(ioi) // 2]
    if med <= 0:
        return []
    win = 8
    flags = []
    for i in range(len(ioi)):
        sl = ioi[max(0, i - win) : i + win]
        local = sorted(sl)[len(sl) // 2]
        flags.append(local > med * 1.65)
    out = []
    i = 0
    while i < len(flags):
        if not flags[i]:
            i += 1
            continue
        j = i
        while j < len(flags) and flags[j]:
            j += 1
        start = beats[i]
        end = beats[min(j, len(beats) - 1)]
        if end - start >= min_len:
            out.append(
                {
                    "role": "breakdown",
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "source": "halftime",
                }
            )
        i = j
    return out


def _tab_kick_spans(pack) -> list[dict]:
    """Half-time breakdown spans from a tab-notes pack's own kick notation
    -- GM percussion pitch 36 (Acoustic Bass Drum), verified against a real
    corpus pack (600 of 1311 drum events, the single most common pitch, on
    a real song) rather than assumed -- instead of guessing kick onsets
    from a low-frequency spectral envelope. Same `_half_time_spans`
    grouping as the audio path (`_kick_spans`), just fed real onset times.
    `[]` when the pack has no drums track or no pitch-36 events."""
    from .tabnotes import events_for

    times = sorted(pack.audio_sec(e) for e in events_for(pack, category="drums")
                   if e.pitch == 36)
    spans = _half_time_spans(times, min_len=5.0)
    for s in spans:
        s["source"] = "kick-notation"
        s["role"] = "breakdown"
    return spans



def _merge_adjacent_same_figure(sections: list[dict], *, gap: float = 0.15) -> list[dict]:
    """Collapse contiguous same-figure runs into one box.

    GP markers often emit riff-A1 / riff-D once per few bars. Adjacent
    slices with the same role + figure_id and a gap <= gap are one
    continuous pin, not three returns. Later returns after other material
    (gap > gap) stay separate boxes sharing the id.

    Function drafts (blast/breakdown without figure_id) are ignored for
    adjacency so a nested blast cannot split a continuous riff run.
    """
    if not sections:
        return []
    figs = [
        {**s, "start": float(s["start"]), "end": float(s["end"])}
        for s in sections
        if s.get("figure_id")
        and s.get("start") is not None
        and s.get("end") is not None
        and float(s["end"]) > float(s["start"])
    ]
    funcs = [
        dict(s)
        for s in sections
        if not s.get("figure_id")
        and s.get("start") is not None
        and s.get("end") is not None
        and float(s["end"]) > float(s["start"])
    ]
    if not figs:
        return list(sections)
    ordered = sorted(figs, key=lambda x: (x["start"], x["end"]))
    merged: list[dict] = []
    for s in ordered:
        fid = (s.get("figure_id") or "").strip()
        role = s.get("role")
        if merged and fid and role:
            prev = merged[-1]
            same = (
                (prev.get("figure_id") or "").strip() == fid
                and prev.get("role") == role
            )
            abut = float(s["start"]) <= float(prev["end"]) + gap
            if same and abut:
                prev["end"] = max(float(prev["end"]), float(s["end"]))
                if s.get("end_bar") is not None:
                    prev["end_bar"] = s.get("end_bar")
                if prev.get("start_bar") is None and s.get("start_bar") is not None:
                    prev["start_bar"] = s.get("start_bar")
                continue
        merged.append(dict(s))
    return sorted(
        merged + funcs,
        key=lambda x: (float(x["start"]), float(x["end"])),
    )



def _clean(sections: list[dict]) -> list[dict]:
    keep = []
    for s in sections:
        try:
            start = float(s["start"])
            end = float(s["end"])
        except Exception:
            continue
        if end <= start:
            continue
        keep.append({**s, "start": start, "end": end})
    keep.sort(key=lambda x: (x["start"], x["end"]))
    out = []
    for s in keep:
        drop = False
        for o in out:
            if s.get("role") != o.get("role"):
                continue
            a, b = max(s["start"], o["start"]), min(s["end"], o["end"])
            overlap = max(0.0, b - a)
            span = min(s["end"] - s["start"], o["end"] - o["start"])
            if span > 0 and overlap / span > 0.7:
                o["start"] = min(o["start"], s["start"])
                o["end"] = max(o["end"], s["end"])
                drop = True
                break
        if not drop:
            out.append(s)
    return out
