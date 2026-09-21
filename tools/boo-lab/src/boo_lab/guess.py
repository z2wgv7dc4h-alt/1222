from __future__ import annotations

import json
import os
import re
from pathlib import Path


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
    """Unheard riff drafts from `figures.jsonl` trusted occurrences. Skips a
    span a marker already covers within `tol` with the same `figure_id`."""
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
    key = _norm(track) or _norm(gp.stem if gp else "")
    seen = 0
    root0 = _gp5_roots()[0]
    if root0.exists():
        seen = sum(1 for _ in root0.rglob("*.gp5"))
    notes.append("key=%s gp5=%s files=%s" % (key or "?", root0, seen))
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
                if sync_rec is not None and sync_rec.get("sync_ok") is False:
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
        if lab_root is not None and sync_rec is not None and sync_rec.get("sync_ok") is True:
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

    if cache:
        try:
            from .learn import preferred_source

            if preferred_source(cache.parent.parent) == "guess":
                notes.append("prefer=guess")
        except Exception:
            pass

    # Snap the audio-derived spans (halftime/kick) to the recorded beat grid.
    grid = _beats_for(lab_root, lookup_album, lookup_track)
    if grid and grid.get("beats"):
        snapped = 0
        for s in sections:
            if s.get("source") in {"halftime", "kick"}:
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

    # Figure windows as unheard riff drafts -- only when the tab clock matched
    # and the occurrence seconds are trusted.
    figures_drafts = 0
    if lab_root is not None and sync_rec is not None and sync_rec.get("sync_ok") is True:
        new_figs = _figure_drafts(lab_root, lookup_album, lookup_track, sections)
        sections.extend(new_figs)
        figures_drafts = len(new_figs)

    # Pack density drafts: high guitar-onset-density spans as unheard riff
    # drafts from the pack's own audio-clock onsets. Riff only here -- the
    # pack's drum breakdowns already come through `_tab_kick_spans` above.
    # Only when sync_ok; never a box off an untrusted clock.
    density_drafts = 0
    if lab_root is not None and sync_rec is not None and sync_rec.get("sync_ok") is True:
        try:
            from .tabnotes_drafts import density_drafts_for_song

            new_density = density_drafts_for_song(
                lab_root, lookup_album, lookup_track, roles=("riff",))
        except Exception:
            new_density = []
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
    if lab_root is not None and sync_rec is not None and sync_rec.get("sync_ok") is True:
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

    # Breakdown gate: keep audio breakdown drafts near this album's median
    # heard breakdown span (n>=2). n<2 keeps the current rules.
    breakdowns_used = _gate_breakdowns(sections, adapt_blob)
    print("figures_drafts=%d density_drafts=%d breakdowns_used=%d"
          % (figures_drafts, density_drafts, breakdowns_used))

    sections = _clean(sections)

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
