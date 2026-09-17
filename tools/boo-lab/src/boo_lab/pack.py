from __future__ import annotations

import json
from pathlib import Path


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in (s or ""))[:80]


def _load_sections(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("source") == "human" or rec.get("role"):
            out.append(rec)
    return out


def _slice(src: Path, dest: Path, start: float, end: float) -> bool:
    if not src.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        import soundfile as sf

        data, sr = sf.read(str(src), always_2d=True)
        a = max(0, int(start * sr))
        b = min(len(data), int(end * sr))
        if b <= a:
            return False
        sf.write(str(dest), data[a:b], sr)
        return True
    except Exception:
        try:
            import librosa
            import soundfile as sf

            y, sr = librosa.load(str(src), sr=None, mono=False)
            if y.ndim == 1:
                y = y.reshape(1, -1)
            a = max(0, int(start * sr))
            b = min(y.shape[-1], int(end * sr))
            if b <= a:
                return False
            clip = y[:, a:b].T
            sf.write(str(dest), clip, sr)
            return True
        except Exception:
            return False


def _sum_no_vox(parts: list[Path], dest: Path) -> bool:
    try:
        import numpy as np
        import soundfile as sf
    except Exception:
        return False
    waves = []
    sr0 = None
    for p in parts:
        if not p.exists():
            continue
        y, sr = sf.read(str(p), always_2d=True)
        if sr0 is None:
            sr0 = sr
        if sr != sr0:
            continue
        waves.append(y)
    if not waves or sr0 is None:
        return False
    n = min(w.shape[0] for w in waves)
    c = max(w.shape[1] for w in waves)
    acc = None
    for w in waves:
        w = w[:n]
        if w.shape[1] < c:
            pad = np.zeros((n, c - w.shape[1]))
            w = np.concatenate([w, pad], axis=1)
        acc = w if acc is None else acc + w
    dest.parent.mkdir(parents=True, exist_ok=True)
    peak = float(abs(acc).max()) if acc is not None else 0
    if peak > 1.0:
        acc = acc / peak * 0.95
    sf.write(str(dest), acc, sr0)
    return True


def build_pack(lab_root: Path, rows: list[dict], cache: Path) -> dict:
    from .holdout import ensure_holdout, split_for
    from .stems import find_stem, run_demucs

    holdout = ensure_holdout(lab_root, rows)
    sec_path = lab_root / "data" / "sections.jsonl"
    sections = _load_sections(sec_path)
    by_song: dict[tuple[str, str], list[dict]] = {}
    for s in sections:
        by_song.setdefault((s.get("album") or "", s.get("track") or ""), []).append(s)

    pack_root = lab_root / "work" / "pack"
    pack_root.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    index = []

    row_by = {}
    for r in rows:
        row_by[(r.get("album") or "", r.get("track") or "")] = r

    for (album, track), segs in sorted(by_song.items()):
        r = row_by.get((album, track))
        if not r:
            hits = [row for (a, t), row in row_by.items() if t == track]
            r = hits[0] if len(hits) == 1 else None
        if not r:
            skipped += len(segs)
            continue
        flac = Path(r.get("flac_path") or r.get("flac") or "")
        if not flac.exists():
            skipped += len(segs)
            continue
        # Real 4-stem fallback: only the four core stems gate a re-run, so a
        # track cached solely under the old `htdemucs` model still packs from
        # that cache (no forced re-separation). guitar/piano are best-effort
        # additions, present only when the 6-stem cache has them.
        need = any(not find_stem(flac, cache, n) for n in ("drums", "bass", "other", "vocals"))
        if need:
            try:
                run_demucs(flac, cache, two_stems=None)
            except Exception as e:
                print("demucs fail", track, e)
        drums = find_stem(flac, cache, "drums")
        bass = find_stem(flac, cache, "bass")
        other = find_stem(flac, cache, "other")
        vocals = find_stem(flac, cache, "vocals")
        guitar = find_stem(flac, cache, "guitar")
        piano = find_stem(flac, cache, "piano")
        # Derived no-vocals lives beside whichever real cache was used.
        folder = drums.parent if drums else cache / "htdemucs_6s" / flac.stem
        no_vox = folder / "no_vocals.wav"
        if not no_vox.exists():
            # 6-stem "other" no longer contains guitar/piano, so a real
            # no-vocals mix must add them back (absent ones are filtered).
            _sum_no_vox([p for p in (drums, bass, guitar, piano, other) if p], no_vox)

        for i, seg in enumerate(segs):
            start, end = float(seg["start"]), float(seg["end"])
            role = _safe(seg.get("role") or "part")
            slug = "%s_%s_%02d_%s" % (_safe(album), _safe(track), i, role)
            dest = pack_root / slug
            dest.mkdir(parents=True, exist_ok=True)
            files = {}
            for label, src in (
                ("mix", flac),
                ("drums", drums),
                ("bass", bass),
                ("other", other),
                ("guitar", guitar),
                ("piano", piano),
                ("vocals", vocals),
                ("no_vocals", no_vox if no_vox.exists() else None),
            ):
                if not src:
                    continue
                out = dest / f"{label}.wav"
                if _slice(Path(src), out, start, end):
                    files[label] = str(out)
            gp_path = r.get("gp_path") or r.get("gp") or ""
            names = []
            if gp_path:
                try:
                    from .extract import gp_track_names

                    names = gp_track_names(Path(gp_path))
                except Exception:
                    names = []
            meta = {
                "album": album,
                "track": track,
                "role": seg.get("role"),
                "start": start,
                "end": end,
                "split": split_for(album, track, holdout),
                "flac": str(flac),
                "gp": gp_path,
                "gp_tracks": names,
                "files": files,
            }
            (dest / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            index.append(meta)
            written += 1
            print("PACK", slug, list(files))

    (pack_root / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return {"written": written, "skipped": skipped, "out": str(pack_root)}
