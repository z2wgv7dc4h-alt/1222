from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


def _key(track: str) -> str:
    s = re.sub(r"^\d+\s*[-_.]\s*", "", track or "")
    return re.sub(r"[^a-z0-9]+", "", s.lower()) or "track"


def parse_lrc(text: str) -> list[dict]:
    lines = []
    for raw in (text or "").splitlines():
        m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", raw.strip())
        if not m:
            continue
        t = int(m.group(1)) * 60 + float(m.group(2))
        words = m.group(3).strip()
        if words:
            lines.append({"start": round(t, 3), "text": words})
    for i, row in enumerate(lines):
        nxt = lines[i + 1]["start"] if i + 1 < len(lines) else row["start"] + 4
        row["end"] = round(max(nxt, row["start"] + 0.4), 3)
    return lines


def fetch_lrclib(track: str, artist: str = "Born of Osiris", duration: float | None = None) -> dict:
    title = re.sub(r"^\d+\s*[-_.]\s*", "", track or "")
    q = {"track_name": title, "artist_name": artist}
    if duration:
        q["duration"] = str(int(duration))
    url = "https://lrclib.net/api/get?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "boo-lab/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        url = "https://lrclib.net/api/search?" + urllib.parse.urlencode(
            {"q": artist + " " + title}
        )
        req = urllib.request.Request(url, headers={"User-Agent": "boo-lab/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                hits = json.loads(r.read().decode("utf-8"))
            data = hits[0] if hits else {}
        except Exception as e:
            return {"ok": False, "error": str(e), "lines": []}
    synced = data.get("syncedLyrics") or ""
    plain = data.get("plainLyrics") or ""
    lines = parse_lrc(synced)
    return {
        "ok": True,
        "source": "lrclib",
        "instrumental": bool(data.get("instrumental")),
        "plain": plain,
        "synced": synced,
        "lines": lines,
    }


def align_whisperx(vocals: Path, plain: str) -> list[dict] | None:
    try:
        import whisperx
    except Exception:
        return None
    if not vocals.exists() or not (plain or "").strip():
        return None
    try:
        device = "cuda"
        model = whisperx.load_model("small", device, compute_type="float16")
    except Exception:
        device = "cpu"
        model = whisperx.load_model("small", device, compute_type="int8")
    audio = whisperx.load_audio(str(vocals))
    result = model.transcribe(audio, batch_size=8)
    try:
        align_model, meta = whisperx.load_align_model(language_code=result.get("language") or "en", device=device)
        result = whisperx.align(result["segments"], align_model, meta, audio, device)
    except Exception:
        pass
    lines = []
    for seg in result.get("segments") or []:
        lines.append(
            {
                "start": round(float(seg.get("start") or 0), 3),
                "end": round(float(seg.get("end") or 0), 3),
                "text": (seg.get("text") or "").strip(),
            }
        )
    return lines


def to_lrc(lines: list[dict]) -> str:
    out = []
    for row in lines:
        t = float(row.get("start") or 0)
        m, s = divmod(t, 60)
        out.append("[%02d:%05.2f] %s" % (int(m), s, row.get("text") or ""))
    return "\n".join(out) + "\n"


def build_lyrics(lab_root: Path, track: str, flac: Path | None, vocals: Path | None) -> dict:
    out_dir = lab_root / "work" / "lyrics"
    out_dir.mkdir(parents=True, exist_ok=True)
    dur = None
    if flac and flac.exists():
        try:
            import soundfile as sf

            info = sf.info(str(flac))
            dur = float(info.duration)
        except Exception:
            dur = None
    hit = fetch_lrclib(track, duration=dur)
    lines = list(hit.get("lines") or [])
    note = "lrclib synced" if lines else "lrclib plain" if hit.get("plain") else hit.get("error") or "no lyrics"
    if (not lines) and vocals and vocals.exists() and hit.get("plain"):
        aligned = align_whisperx(vocals, hit["plain"])
        if aligned:
            lines = aligned
            note = "whisperx on vocals stem"
    key = _key(track)
    payload = {**hit, "lines": lines, "note": note, "track": track}
    (out_dir / f"{key}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if lines:
        (out_dir / f"{key}.lrc").write_text(to_lrc(lines), encoding="utf-8")
    return payload


def save_lyrics(lab_root: Path, track: str, lines: list[dict]) -> dict:
    out_dir = lab_root / "work" / "lyrics"
    out_dir.mkdir(parents=True, exist_ok=True)
    cleaned = []
    for row in lines:
        try:
            start = round(float(row.get("start") or 0), 3)
        except Exception:
            continue
        text = (row.get("text") or "").strip()
        if not text:
            continue
        cleaned.append({"start": max(0.0, start), "text": text})
    cleaned.sort(key=lambda r: r["start"])
    for i, row in enumerate(cleaned):
        nxt = cleaned[i + 1]["start"] if i + 1 < len(cleaned) else row["start"] + 4
        row["end"] = round(max(nxt, row["start"] + 0.4), 3)
    key = _key(track)
    prev = load_lyrics(lab_root, track)
    payload = {**prev, "lines": cleaned, "note": "edited in ui", "track": track}
    (out_dir / f"{key}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / f"{key}.lrc").write_text(to_lrc(cleaned), encoding="utf-8")
    return payload


def load_lyrics(lab_root: Path, track: str) -> dict:
    p = lab_root / "work" / "lyrics" / f"{_key(track)}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"lines": [], "note": "press Lyrics to fetch"}
