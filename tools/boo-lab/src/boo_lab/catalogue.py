from __future__ import annotations

import csv
import hashlib
import os
import re
import tempfile
from pathlib import Path

from .gate import is_bankable_track, is_stub_gp

FIELDS = [
    "album",
    "track",
    # Stable song id from identity.csv (`boo.discovery`, ...); "" when unknown.
    "album_id",
    "year",
    "flac",
    "gp",
    "tuning",
    "match",
    "notes",
    "flac_sha256",
]


def load_map(path: Path) -> list[dict]:
    """Keep every column present in the CSV, including unknown extras."""
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_map(path: Path, rows: list[dict]) -> None:
    """Write `FIELDS` first, then any extra columns found in the rows, so a
    load→save round-trip never drops an unknown column."""
    keys = list(FIELDS)
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in keys})


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    """Hex sha256 of a file, or "" when it can't be read."""
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as f:
            for block in iter(lambda: f.read(chunk), b""):
                digest.update(block)
        return digest.hexdigest()
    except Exception:
        return ""


_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def _write_map_atomic(path: Path, rows: list[dict]) -> None:
    """Atomic CSV write (temp + fsync + os.replace): a crash mid-write leaves
    the previous `map.csv` intact. Preserves unknown extra columns like
    `save_map`."""
    keys = list(FIELDS)
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                w.writerow({k: row.get(k, "") for k in keys})
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def fill_hashes(map_path: Path, album: str | None = None) -> dict:
    """Fill `flac_sha256` for rows whose FLAC exists on disk. A cell already
    holding a valid 64-hex digest is never rehashed; empty (or malformed) cells
    are filled. Atomic write; missing files are left empty."""
    rows = load_map(map_path) if map_path.exists() else []
    filled = 0
    for row in rows:
        if album and (row.get("album") or "").casefold() != album.casefold():
            continue
        if _HEX64.match((row.get("flac_sha256") or "").strip()):
            continue
        flac = row.get("flac") or ""
        p = Path(flac) if flac else None
        if p and p.exists():
            digest = sha256_file(p)
            if digest:
                row["flac_sha256"] = digest
                filled += 1
    _write_map_atomic(map_path, rows)
    return {"filled": filled, "rows": len(rows)}


def resolve(row: dict, flac_root: Path | None, gp_root: Path | None) -> dict:
    out = dict(row)
    if flac_root and row.get("flac"):
        p = Path(row["flac"])
        out["flac_path"] = str(p if p.is_absolute() else flac_root / p)
    if gp_root and row.get("gp"):
        p = Path(row["gp"])
        out["gp_path"] = str(p if p.is_absolute() else gp_root / p)
    return out


AUDIO_EXT = {".flac", ".wav", ".mp3", ".m4a"}
GP_EXT = {".gp3", ".gp4", ".gp5", ".gpx", ".gp"}


def _stem(p: Path) -> str:
    return p.stem.replace("_", " ").strip()


def _key(s: str) -> str:
    import re
    s = (s or "").replace("∆", "A").replace("Δ", "A").replace("δ", "a").lower()
    # strip a leading track number whether or not a separator follows
    # ("07 - Exist" and "07 Exist" both -> "exist").
    s = re.sub(r"^\d+\s*[-_.]\s*|^\d+\s+", "", s)
    # strip a leading band prefix however it is punctuated
    s = re.sub(r"^born[\s._-]*of[\s._-]*osiris", "", s)
    s = re.sub(r"s\d+$", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def _lead_num(s: str) -> str:
    """The leading track number of a title, if any (`02 Singularity` -> `02`)."""
    import re
    m = re.match(r"\s*(\d{1,3})", s or "")
    return m.group(1) if m else ""


def _album_of(p: Path) -> str:
    d = p.parent
    if d.name.lower() in {"tracks", "track"}:
        d = d.parent
    return d.name


def _looks_like_disc_image(p: Path) -> bool:
    if p.parent.name.lower() in {"tracks", "track"}:
        return False
    if (p.parent / "tracks").is_dir():
        return True
    if list(p.parent.glob("*.cue")) and list(p.parent.glob("tracks/*")):
        return True
    return False


# Aliases shorter than this are too generic to key a GP by (e.g. the last
# `_` segment of "..._Half_Of_Me-s123" is "me", which is a substring of many
# unrelated titles) and caused one tab to match several songs.
_MIN_GP_KEY = 3
_MIN_SUBSTRING = 5


def _gp_candidates(stem: str, gp_files: list[tuple[set, Path]]) -> list[Path]:
    """GP files that could be `stem`, best first. Exact key match beats a
    meaningful substring; a filename whose leading track number matches the
    song's is preferred, then the shorter/more-specific name."""
    k = _key(stem)
    if not k:
        return []
    num = _lead_num(stem)
    scored: list[tuple[float, Path]] = []
    for keys, path in gp_files:
        score = 0.0
        if k in keys:
            score = 1000.0
        else:
            for nk in keys:
                if nk and min(len(k), len(nk)) >= _MIN_SUBSTRING and (k in nk or nk in k):
                    score = max(score, 500.0 + min(len(k), len(nk)) - abs(len(k) - len(nk)))
        if not score:
            continue
        if num and _lead_num(path.stem) == num:
            score += 100.0
        # A GP7 `.gp`/`.gpx` beats an equally-scored `.gp5` (GP7-native law).
        if path.suffix.lower() in (".gp", ".gpx"):
            score += 1.0
        score -= len(path.stem) / 1000.0
        scored.append((score, path))
    scored.sort(key=lambda x: (-x[0], str(x[1])))
    return [p for _s, p in scored]


def _find_gp(stem: str, gps: dict[str, Path]) -> Path | None:
    """First (best) candidate from a normalized-key dict -- the single-GP
    convenience form of `_gp_candidates`."""
    cands = _gp_candidates(stem, [({k}, p) for k, p in gps.items() if k])
    return cands[0] if cands else None


# GP7/GP6 zip containers vs legacy GP3/4/5 binaries. `.gp`/`.gpx` are treated
# as GP7 only when the existing GPIF sniffer says so; otherwise they fall back
# with the legacy extensions.
_GP7_EXTS = (".gp", ".gpx")
_GP5_EXTS = (".gp3", ".gp4", ".gp5")
_GP_EXTS = _GP7_EXTS + _GP5_EXTS


def _is_gpif_zip(path: Path) -> bool:
    """True when the real GPIF reader can open this file (a zip with a
    `Content/score.gpif` entry). Reuses `gpif.open_gp` -- no second sniffer."""
    try:
        from .gpif import open_gp

        with open_gp(path):
            return True
    except Exception:
        return False


def _largest(paths: list[Path]) -> Path:
    """Largest file; a size tie keeps input order (so `_gp_candidates`'
    match-quality order is the final tiebreak)."""
    best = paths[0]
    best_size = best.stat().st_size
    for p in paths[1:]:
        size = p.stat().st_size
        if size > best_size:
            best, best_size = p, size
    return best


def pick_gp(candidates: list[Path]) -> Path | None:
    """Choose ONE tab from several GP candidates for one track.

    Priority: readable GP7 `.gp`/`.gpx` (GPIF sniffer) > readable GP3/4/5
    (by extension) > never a stub (solo/bass/cover/intro, or < 10 KB) >
    largest wins > GP7 beats GP5. `None` when no candidate is usable (a stub
    is never returned). Never copies or deletes a loser."""
    valid = [Path(p) for p in (candidates or []) if not is_stub_gp(p)]
    if not valid:
        return None
    gpif = [p for p in valid if p.suffix.lower() in _GP7_EXTS and _is_gpif_zip(p)]
    if gpif:
        return _largest(gpif)
    legacy = [p for p in valid if p.suffix.lower() in _GP_EXTS]
    if legacy:
        return _largest(legacy)
    return None


def scan_roots(flac_root: Path | None, gp_root: Path | None) -> list[dict]:
    """One row per track FLAC. Album = album folder, not 'tracks'."""
    gp_files: list[tuple[set, Path]] = []
    if gp_root and gp_root.exists():
        for p in gp_root.rglob("*"):
            if p.suffix.lower() not in GP_EXT:
                continue
            keys = {_key(p.stem), _key(_stem(p))}
            # "07 Exist" (track number + space, no separator) -> also key "exist"
            keys.add(_key(re.sub(r"^\d+\s+", "", p.stem)))
            # Born_Of_Osiris-Elimination -> elimination
            if "-" in p.stem:
                keys.add(_key(p.stem.split("-")[-1]))
            if "_" in p.stem:
                keys.add(_key(p.stem.split("_")[-1]))
            keys = {k for k in keys if k and len(k) >= _MIN_GP_KEY}
            gp_files.append((keys, p))
    rows = []
    if flac_root and flac_root.exists():
        flacs = sorted(
            p for p in flac_root.rglob("*")
            if p.suffix.lower() in AUDIO_EXT and not _looks_like_disc_image(p)
        )
        # Stable album ids come from the shipped identity.csv (never folder
        # names); "" when the song has no identity row.
        try:
            from .identity import album_id_for as _album_id_for
            from .identity import load_identity as _load_identity

            identity_rows = _load_identity()
        except Exception:
            _album_id_for, identity_rows = None, None
        used_gp: set[Path] = set()
        for fp in flacs:
            album = _album_of(fp)
            track = fp.stem
            cands = [c for c in _gp_candidates(_stem(fp), gp_files)
                     if c not in used_gp]  # one GP file -> one FLAC
            gp = pick_gp(cands)
            losers = [c for c in cands if c != gp]
            # A stub candidate (tiny / *_solo* / Misha mix / cover / bass-only)
            # is never picked: `gp` stays empty and `match` is "stub", never
            # "yes", so extract/figures/holdout all skip it. No file is copied
            # or deleted; the runners-up are only listed in `notes`.
            if not is_bankable_track(track, fp.name):
                # The TRACK itself is a Misha mix / solo / cover / bass-only
                # request -- never a real tab match, even if a big GP exists.
                # Keep any picked path only as a note (do not claim it).
                match = "stub"
            elif gp is not None:
                used_gp.add(gp)
                match = "yes"
            elif cands:
                match = "stub"
            else:
                match = "unknown"
            album_id = ""
            if _album_id_for is not None:
                try:
                    album_id = _album_id_for(album, track, rows=identity_rows) or ""
                except Exception:
                    album_id = ""
            rows.append(
                {
                    "album": album,
                    "track": track,
                    "album_id": album_id,
                    "year": "",
                    "flac": str(fp),
                    "gp": str(gp) if gp else "",
                    "tuning": "drop_g_7",
                    "match": match,
                    "notes": "also: " + ", ".join(p.name for p in losers) if losers else "",
                    "flac_sha256": sha256_file(fp),
                }
            )
    rows.sort(key=lambda r: ((r.get("album") or ""), r.get("track") or ""))
    return rows


def filter_album(rows: list[dict], album: str | None) -> list[dict]:
    if not album:
        return rows
    key = album.casefold()
    return [r for r in rows if (r.get("album") or "").casefold() == key]


# --- resolve_row -------------------------------------------------------------
#
# Humans type album/track the way the studio shows them ("A Higher Place",
# "07 - Exist"); `map.csv` often stores the folder name ("2009 - A Higher
# Place"). Exact `==` therefore reported "no-gp" for tabs that exist. This is
# the single catalogue-side resolver; never a second map.

_YEAR_PREFIX = re.compile(r"^\d{4}\s*[-._]?\s*")
_TRACK_NUM_PREFIX = re.compile(r"^\d{1,3}[\s._-]+")


def _album_core(s: str | None) -> str:
    """Album key with a leading `YYYY` / `YYYY - ` / `YYYY.` prefix removed."""
    return _key(_YEAR_PREFIX.sub("", (s or "").strip()))


def _track_key(s: str | None) -> str:
    """Track key so `07 - Exist` == `07 Exist` == `Exist`."""
    return _key(_TRACK_NUM_PREFIX.sub("", (s or "").strip()))


def _album_tightness(row_album: str | None, query: str, query_cf: str) -> int:
    raw = (row_album or "").strip()
    if raw == query:
        return 3
    if raw.casefold() == query_cf:
        return 2
    if _YEAR_PREFIX.sub("", raw).casefold() == _YEAR_PREFIX.sub("", query).casefold():
        return 1
    return 0


def _loose_resolve(rows: list[dict], album: str | None, track: str | None) -> dict | None:
    """Last-resort comparable-key match (normalize.album_key/track_key): the
    separator / `∆` / parenthetical spellings the exact and normalized steps
    miss. Never beats an exact/casefold/normalized hit -- called only after
    those fail."""
    from .normalize import album_key, track_key

    a_key = album_key(album)
    t_key = track_key(track)
    if not a_key or not t_key:
        return None
    for r in rows:
        if album_key(r.get("album")) == a_key and track_key(r.get("track")) == t_key:
            return r
    return None


def resolve_row(rows: list[dict], album: str | None, track: str | None) -> dict | None:
    """The one map-row resolver: exact → casefold → year-prefix album +
    normalized track. Returns the real row (or `None`), never a fabricated one.

    A different album title that merely shares a year never matches, because
    the album core key must be equal. When several rows reduce to the same
    track (e.g. `07 - Exist` vs `05 - Exist`), the one whose raw track still
    carries the queried digit token wins; otherwise exact/casefold album wins;
    ties keep map order."""
    if not album or not track:
        return None
    query = album.strip()
    track_q = track.strip()

    # (a) exact
    for r in rows:
        if (r.get("album") or "") == query and (r.get("track") or "") == track_q:
            return r
    # (b) casefold
    query_cf = query.casefold()
    track_cf = track_q.casefold()
    for r in rows:
        if ((r.get("album") or "").casefold() == query_cf
                and (r.get("track") or "").casefold() == track_cf):
            return r
    # (c) + (d) album core key AND normalized track key
    a_core = _album_core(query)
    t_key = _track_key(track_q)
    if not a_core or not t_key:
        # (e) last-resort comparable keys (normalize.track_key) before giving up
        return _loose_resolve(rows, query, track_q)
    cands = [r for r in rows
             if _album_core(r.get("album")) == a_core
             and _track_key(r.get("track")) == t_key]
    if not cands:
        return _loose_resolve(rows, query, track_q)
    # Prefer a row whose raw track still carries the queried number.
    q_digits = re.findall(r"\d+", track_q)
    if q_digits:
        digit_hits = [r for r in cands if q_digits[0] in (r.get("track") or "")]
        if digit_hits:
            cands = digit_hits
    cands.sort(key=lambda r: _album_tightness(r.get("album"), query, query_cf),
               reverse=True)  # stable: ties keep original order
    return cands[0]
