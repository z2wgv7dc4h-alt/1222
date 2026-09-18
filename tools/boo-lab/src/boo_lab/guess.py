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


def _norm(s: str) -> str:
    s = (s or "").replace("∆", "A").replace("Δ", "A").replace("δ", "a").lower()
    s = re.sub(r"^\d+\s*[-_.]\s*", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def _prefer_gp5(gp: Path | None, track: str) -> Path | None:
    cands: list[Path] = []
    if gp:
        p = Path(gp)
        if p.suffix.lower() == ".gp5" and p.exists():
            return p
        sib = p.with_suffix(".gp5")
        if sib.exists():
            cands.append(sib)
        if p.exists() and p.suffix.lower() == ".gp5":
            cands.append(p)
    key = _norm(track)
    if not key and gp:
        # "Born_Of_Osiris-Recreate-s77727" -> recreate
        raw = _norm(Path(gp).stem)
        raw = re.sub(r"^bornofosiris", "", raw)
        raw = re.sub(r"s\d+$", "", raw)
        key = raw
    if key:
        for root in _gp5_roots():
            if not root.exists():
                continue
            try:
                hits = list(root.rglob("*.gp5"))
            except Exception:
                continue
            for hit in hits:
                n = _norm(hit.stem)
                if n == key or key in n or n in key:
                    cands.append(hit)
    for c in cands:
        if c.exists() and c.suffix.lower() == ".gp5":
            return c
    return None


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

    gp_use = _prefer_gp5(gp, track)
    key = _norm(track) or _norm(gp.stem if gp else "")
    seen = 0
    root0 = _gp5_roots()[0]
    if root0.exists():
        seen = sum(1 for _ in root0.rglob("*.gp5"))
    notes.append("key=%s gp5=%s files=%s" % (key or "?", root0, seen))
    if gp_use:
        notes.append("tab " + str(gp_use))
        try:
            from .extract import estimate_from_gp

            g = estimate_from_gp(gp_use)
            bpm = g.get("bpm") or bpm
            if g.get("sections"):
                sync_rec = _sync_for(lab_root, lookup_album, lookup_track)
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

    sections = _clean(sections)

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
