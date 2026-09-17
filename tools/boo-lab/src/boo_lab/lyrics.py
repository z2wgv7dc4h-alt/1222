from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


def _key(track: str) -> str:
    # Strip a leading track number whether it's "01 - Song" or "01 Song".
    s = re.sub(r"^\d+[\s._-]+", "", track or "")
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


def _http_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": "boo-lab/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _fetch_with_retry(url: str, attempts: int = 3):
    last = None
    for i in range(attempts):
        try:
            return _http_json(url)
        except Exception as e:  # transient 503s happen
            last = e
            time.sleep(0.5 * (i + 1))
    raise last


def fetch_lrclib(track: str, artist: str = "Born of Osiris", duration: float | None = None) -> dict:
    """Real LRCLIB lookup, preferring synced lyrics without trusting the
    local rip's duration: `/api/get` with duration, then without, then a
    search that picks the best lyric-bearing hit. Retries transient 503s."""
    title = re.sub(r"^\d+[\s._-]+", "", track or "")
    base = {"track_name": title, "artist_name": artist}

    data = None
    last_err: Exception | None = None
    queries = []
    if duration:
        queries.append({**base, "duration": str(int(duration))})
    queries.append(dict(base))
    for q in queries:
        try:
            hit = _fetch_with_retry("https://lrclib.net/api/get?" + urllib.parse.urlencode(q))
            if isinstance(hit, dict) and hit.get("trackName"):
                data = hit
                break
        except Exception as e:
            last_err = e

    if data is None:
        try:
            hits = _fetch_with_retry(
                "https://lrclib.net/api/search?" + urllib.parse.urlencode({"q": artist + " " + title})
            )
            if isinstance(hits, list) and hits:
                def _score(h: dict):
                    has_synced = 1 if h.get("syncedLyrics") else 0
                    has_plain = 1 if h.get("plainLyrics") else 0
                    delta = abs((h.get("duration") or 0) - duration) if duration else 0.0
                    return (has_synced, has_plain, -delta)

                data = sorted(hits, key=_score, reverse=True)[0]
        except Exception as e:
            last_err = e

    if data is None:
        return {"ok": False, "error": str(last_err) if last_err else "not found", "lines": []}

    synced = data.get("syncedLyrics") or ""
    plain = data.get("plainLyrics") or ""
    return {
        "ok": True,
        "source": "lrclib",
        "instrumental": bool(data.get("instrumental")),
        "plain": plain,
        "synced": synced,
        "lines": parse_lrc(synced),
    }


def align_whisperx(vocals: Path, plain: str) -> list[dict] | None:
    """Force-align the PROVIDED plain lyrics to the vocals stem using
    WhisperX's wav2vec2 aligner -- places the REAL words in time, rather
    than running ASR and returning whatever Whisper hallucinated (which is
    gibberish on screamed vocals). Returns timed lines, or `None` when
    whisperx isn't installed, nothing aligned, or there is no plain text.
    """
    try:
        import whisperx
    except Exception:
        return None
    if not vocals.exists() or not (plain or "").strip():
        return None

    audio = whisperx.load_audio(str(vocals))
    sample_rate = float(getattr(whisperx.audio, "SAMPLE_RATE", 16000))
    duration = len(audio) / sample_rate

    align_model = meta = None
    for device in ("cuda", "cpu"):
        try:
            align_model, meta = whisperx.load_align_model(language_code="en", device=device)
            break
        except Exception:
            continue
    if align_model is None:
        return None

    try:
        result = whisperx.align(
            [{"text": " ".join(plain.split()), "start": 0.0, "end": float(duration)}],
            align_model, meta, audio, device, return_char_alignments=False,
        )
    except Exception:
        return None

    words: list[tuple[float, float]] = []
    for seg in result.get("segments") or []:
        for w in seg.get("words") or []:
            if w.get("start") is not None:
                start = float(w["start"])
                end = float(w.get("end") or start)
                words.append((start, max(end, start)))
    if not words:
        return None

    line_texts = [ln.strip() for ln in plain.splitlines() if ln.strip()]
    counts = [len(ln.split()) for ln in line_texts]
    total = sum(counts)
    if total != len(words):
        # aligner merged/dropped tokens -- rescale line boundaries.
        counts = [max(1, round(c * len(words) / total)) for c in counts]

    lines: list[dict] = []
    i = 0
    for text, count in zip(line_texts, counts):
        chunk = words[i:i + count]
        i += count
        if not chunk:
            continue
        start = chunk[0][0]
        end = max(chunk[-1][1], start + 0.4)
        lines.append({"start": round(start, 3), "end": round(end, 3), "text": text})
    return lines or None


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
    plain = hit.get("plain") or ""
    plain_lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
    note = (
        "lrclib synced"
        if lines
        else "lrclib plain — untimed, no synced version at LRCLIB"
        if plain_lines
        else (hit.get("error") or "no lyrics")
    )
    if (not lines) and vocals and vocals.exists() and plain:
        aligned = align_whisperx(vocals, plain)
        if aligned:
            lines = aligned
            note = "whisperx force-aligned plain lyrics"
    key = _key(track)
    payload = {**hit, "lines": lines, "plain_lines": plain_lines, "note": note, "track": track}
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
        data = json.loads(p.read_text(encoding="utf-8"))
        # Normalize caches written before `plain_lines` existed.
        if "plain_lines" not in data:
            data["plain_lines"] = [
                ln.strip() for ln in (data.get("plain") or "").splitlines() if ln.strip()
            ]
        return data
    return {"lines": [], "note": "press Lyrics to fetch"}
