"""Real, verbatim riff-fragment extraction from real Guitar Pro tab files.

Born of Osiris only, per the real Metalerator-style architectural pivot
(see docs/CURRENT.md's own writeup of why the statistical/ML riff-content
approach was abandoned for `labyrinth`). Unlike `reference_vocab.analyze_
gp_reference` (which immediately collapses a file's real, ordered note
sequence into interval-frequency/Markov aggregates), this module keeps
real per-note pitch, duration, and bar position -- genuinely bar-segmented,
never a flat tape -- and real section-role labels lifted from the tab
author's own measure markers where present.

Deliberately does NOT resolve fragments against a target `theory.Scale`
or snap pitches to a specific `Fretboard` -- both are generation-time
concerns (the target scale/tuning is only known inside `song.py`, once a
preset is chosen), kept as a later, separate wiring step. `RiffFragment.
deltas` are real, source-faithful SEMITONE intervals between consecutive
notes (not scale-degree deltas), resolved into scale-degree space only
when a fragment is actually rendered against a real target scale.

Real, freely-downloaded source files (gtptabs.com, gprotab.net,
musicnoteslib.com -- all openly downloadable, no paywall/login) live
under `reference/gp-tabs-born-of-osiris/` (gitignored, same as every
other `reference/` subdirectory). The extracted bank itself is cached to
`engine/data/riff_bank.json` (also gitignored -- this is genuinely closer
to the source songs' own melodic content than even the ML corpus was,
so it gets at least the same "local-only, never redistributed" posture
already applied to `engine/data/ml_corpus/`).
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from motif import Motif, degree_delta_for_interval, degree_delta_for_interval_downward
from theory import Scale

try:
    import guitarpro
except ImportError:  # pragma: no cover - exercised only when pyguitarpro is missing
    guitarpro = None

__all__ = [
    "RiffFragment",
    "extract_fragments_from_file",
    "build_riff_bank",
    "save_riff_bank",
    "load_riff_bank",
    "select_and_resolve_motif",
    "DEFAULT_RIFF_BANK_PATH",
]

_EPS = 1e-6

_ENGINE_ROOT = Path(__file__).resolve().parent
# Same real precedent as `riff_model.DEFAULT_CHECKPOINT_PATH` -- a default
# location callers can check for existence before trying to use it.
DEFAULT_RIFF_BANK_PATH = _ENGINE_ROOT / "data" / "riff_bank.json"

# GM guitar-family program range (nylon/steel/jazz/clean/muted/overdriven/
# distortion/harmonics) -- the same real GM-program convention this
# project already uses elsewhere (midi_export.py's own `_GUITAR_PROGRAM`)
# to identify a guitar track, reused here since real track NAMES in this
# corpus are wildly inconsistent (several files literally name tracks
# after the real band members, e.g. "Jason"/"Lee" for Follow The Signs --
# BoO's own real guitarists -- rather than "Guitar").
_GUITAR_GM_PROGRAMS = range(24, 32)

# Reuses `audio_vocab.transcribe_and_split_registers`'s own already-
# established real rhythm/lead register split convention (its
# `rhythm_cutoff_midi` default) rather than inventing a second, competing
# cutoff -- a guitar track whose notes mostly fall below this pitch reads
# as the real rhythm part, at/above it reads as lead/solo.
_RHYTHM_LEAD_PITCH_CUTOFF = 52

# Real fragment length: one bar per fragment. Matches `labyrinth.json`'s
# own real `bars=8`-per-section scale (several real fragments tile one
# generated section, the same kind of bar-by-bar composition `motif.
# _generate_irvd_motif` already does) and keeps each fragment's own real
# section-marker association unambiguous (a marker applies to a specific
# measure, not a multi-measure span that might straddle two real
# sections).
_FRAGMENT_BARS = 1

# Real section markers, ordered longest/most-specific match first so
# "Pre-Chorus" doesn't get caught by a plain "chorus" substring check.
# Maps directly onto this project's own real role vocabulary
# (`structure.py`'s `intro/build/breakdown/solo/interlude/chill/verse/
# chorus/outro`) -- "bridge" maps to "interlude" (a real, distinct,
# non-repeating section in this project's own graph, the closest match
# to a tab's own "bridge" convention) and "pre-chorus" maps to "build" (a
# real rising-tension section leading into the chorus). Any marker text
# that doesn't match a keyword here is kept as `raw_marker` on the
# fragment (real, honest partial information) but leaves `role=None`
# rather than guessing -- e.g. the real "A"/"B"/"C"/"D" and "I"/"II"/
# "III"/"IV" structural labels several of these real tabs use, which mark
# DISTINCT riff sections without naming a semantic role.
_MARKER_ROLE_KEYWORDS: list[tuple[str, str]] = [
    ("pre chorus", "build"),
    ("pre-chorus", "build"),
    ("prechorus", "build"),
    ("intro", "intro"),
    ("verse", "verse"),
    ("chorus", "chorus"),
    ("bridge", "interlude"),
    ("breakdown", "breakdown"),
    ("solo", "solo"),
    ("outro", "outro"),
]

# Real junk-marker filter: a marker whose own text is clearly not a
# section label at all (a credit, a URL, a placeholder) -- confirmed
# real examples found in this exact corpus: "Live Demonstration at
# youtube.com/MrFeistyFingers" (behold_outro_solo.gp5), "FOLLOW THE
# SIGNS" (the song's own title, follow_the_signs.gp5), and bare "."
# placeholders. Filtered out entirely (never stored as `raw_marker`
# either) rather than mapped to a role.
_JUNK_MARKER_PATTERN = re.compile(r"https?://|www\.|youtube|\bdemonstration\b", re.IGNORECASE)


def _resolve_role(marker_title: str, song_title: str) -> tuple[str | None, str | None]:
    """Real `(role, raw_marker)` pair for one marker's title text.

    `role` is `None` when the marker doesn't match this project's own
    role vocabulary (kept honest, never guessed); `raw_marker` is `None`
    additionally when the marker is real junk (a credit/URL/placeholder,
    or the song's own title used as a marker) -- real junk is discarded
    entirely, not preserved as unlabeled data.
    """
    text = marker_title.strip()
    if not text or text == ".":
        return None, None
    if _JUNK_MARKER_PATTERN.search(text):
        return None, None
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    if normalized == re.sub(r"\s+", " ", song_title).strip().lower():
        return None, None
    for keyword, role in _MARKER_ROLE_KEYWORDS:
        if keyword in normalized:
            return role, text
    return None, text


@dataclass(frozen=True)
class RiffFragment:
    """One real, verbatim bar-length riff fragment.

    `cell`: real `{"duration": float, "is_rest": bool}` per hit, beats
    measured in this project's own quarter-note-beat convention (matches
    `motif.Motif.cell`'s own shape exactly, so a fragment slots into that
    machinery unmodified once resolved against a target scale).

    `deltas`: real SEMITONE intervals between consecutive real notes
    (first note's own delta is its interval from the fragment's own
    first pitch, i.e. 0) -- deliberately NOT a scale-degree delta yet,
    see this module's own docstring for why.

    `role`: this project's own canonical role name when the tab's nearest
    preceding real marker resolved to one, else `None` (never guessed).
    `raw_marker`: the real marker text itself when present, kept even
    when `role` is `None` (an honest, unmapped structural label like "A"
    or "III" is still real information).
    """

    source_song: str
    source_file: str
    measure_index: int
    cell: list[dict]
    deltas: list[int]
    role: str | None
    raw_marker: str | None


def _select_rhythm_track(song: "guitarpro.Song") -> "guitarpro.Track | None":
    """Real rhythm-guitar track selection for one parsed `Song`.

    Filters to real guitar-family tracks (GM program 24-31, not a
    percussion track) -- track NAMES are unreliable in this real corpus
    (see this module's own docstring), so instrument program is the one
    real, consistent signal. Among candidates, picks the track whose
    real notes most often fall in the rhythm register (below
    `_RHYTHM_LEAD_PITCH_CUTOFF`), reusing `audio_vocab.transcribe_and_
    split_registers`'s own already-established real cutoff convention.
    Returns `None` when no real guitar-family track exists at all.
    """
    candidates = [
        t
        for t in song.tracks
        if not t.isPercussionTrack and t.channel.instrument in _GUITAR_GM_PROGRAMS
    ]
    if not candidates:
        return None

    def _rhythm_register_fraction(track: "guitarpro.Track") -> float:
        pitches = [
            n.realValue
            for m in track.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
        ]
        if not pitches:
            return 0.0
        below = sum(1 for p in pitches if p < _RHYTHM_LEAD_PITCH_CUTOFF)
        return below / len(pitches)

    return max(candidates, key=_rhythm_register_fraction)


def extract_fragments_from_file(path: str | Path, song_title: str | None = None) -> list[RiffFragment]:
    """Real, per-bar fragment extraction from one real Guitar Pro file.

    Raises `ValueError` on a file with no real usable rhythm-guitar track
    (fails closed, never fabricates a fragment) or an empty measure list.
    """
    if guitarpro is None:
        raise ImportError(
            "riff_bank requires the 'pyguitarpro' package. It is listed in "
            "engine/requirements.txt -- install with `pip install pyguitarpro`."
        )
    path = Path(path)
    song = guitarpro.parse(str(path))
    title = song_title if song_title is not None else (song.title or path.stem)

    track = _select_rhythm_track(song)
    if track is None:
        raise ValueError(f"{path}: no real guitar-family track found")
    if not track.measures:
        raise ValueError(f"{path}: track has no measures")

    fragments: list[RiffFragment] = []
    current_role: str | None = None
    current_raw_marker: str | None = None

    for measure_index, measure in enumerate(track.measures):
        header = song.measureHeaders[measure_index] if measure_index < len(song.measureHeaders) else None
        if header is not None and header.marker is not None:
            role, raw_marker = _resolve_role(header.marker.title, title)
            if role is not None or raw_marker is not None:
                current_role, current_raw_marker = role, raw_marker

        cell: list[dict] = []
        deltas: list[int] = []
        prev_pitch: int | None = None
        for voice in measure.voices:
            for beat in voice.beats:
                beats_val = 4.0 / beat.duration.value
                if beat.duration.isDotted:
                    beats_val *= 1.5
                is_rest = not beat.notes
                cell.append({"duration": beats_val, "is_rest": is_rest})
                if not is_rest:
                    pitch = max(n.realValue for n in beat.notes)
                    if prev_pitch is None:
                        deltas.append(0)
                    else:
                        deltas.append(pitch - prev_pitch)
                    prev_pitch = pitch
            break  # real rhythm content lives in the first voice; GP's second voice is a rare alt-notation layer

        if not cell or not deltas:
            continue
        fragments.append(
            RiffFragment(
                source_song=title,
                source_file=path.name,
                measure_index=measure_index,
                cell=cell,
                deltas=deltas,
                role=current_role,
                raw_marker=current_raw_marker,
            )
        )

    return fragments


def build_riff_bank(source_dir: str | Path) -> tuple[list[RiffFragment], list[tuple[str, str]]]:
    """Real bank build across every `*.gp[3-5]`/`*.gp4` file under
    `source_dir` (recursive). Returns `(fragments, failures)` -- failures
    is a real, honest `(filename, reason)` list, never silently dropped.
    Deduplicates by `(source_song lowercased, measure_index)` isn't
    attempted here -- the same real song appears multiple times across
    sources with different transcriptions, and keeping every real
    transcription's own fragments is deliberate (more real coverage per
    role, not redundant noise -- generation-time selection can weight or
    dedupe further once actually wired in).
    """
    source_dir = Path(source_dir)
    fragments: list[RiffFragment] = []
    failures: list[tuple[str, str]] = []
    for path in sorted(source_dir.glob("**/*.gp*")):
        if path.suffix.lower() == ".gpx":
            failures.append((str(path), "gpx sub-format not decodable by this pyguitarpro version"))
            continue
        try:
            fragments.extend(extract_fragments_from_file(path))
        except Exception as e:  # noqa: BLE001 - real, honest per-file failure capture
            failures.append((str(path), str(e)))
    return fragments, failures


def save_riff_bank(fragments: list[RiffFragment], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(f) for f in fragments], indent=2), encoding="utf-8")


def load_riff_bank(path: str | Path) -> list[RiffFragment]:
    data: list[dict[str, Any]] = json.loads(Path(path).read_text(encoding="utf-8"))
    return [RiffFragment(**d) for d in data]


# Real register bound for a chained fragment sequence -- same real, already-
# proven value as `motif._PITCH_REGISTER_SPAN_SEMITONES` and `riff_model.
# _RIFF_REGISTER_SPAN_SEMITONES` (one real octave each way from the chain's
# own anchor). Kept as this module's own constant rather than importing
# motif's private one, matching `riff_model.py`'s own existing precedent of
# each generator module declaring the same real value independently.
_FRAGMENT_REGISTER_SPAN_SEMITONES = 12


def _trim_fragment_cell(fragment: RiffFragment, max_beats: float) -> tuple[list[dict], list[int]]:
    """Real cell/delta trim so a chained fragment never overshoots the
    section's own remaining beat budget -- same "final cell corrected to
    land exactly on total_beats" discipline `rhythm.generate_rhythm`
    already uses, applied per-fragment here since a real fragment's own
    beat-sum isn't guaranteed to be a clean 4.0 (a real tab bar can be a
    non-4/4 measure or carry a transcription-quirky partial beat)."""
    cells: list[dict] = []
    deltas: list[int] = []
    used = 0.0
    delta_i = 0
    for c in fragment.cell:
        is_hit = not c["is_rest"]
        if used + c["duration"] > max_beats + _EPS:
            remaining = max_beats - used
            if remaining > _EPS:
                cells.append({"duration": remaining, "is_rest": c["is_rest"]})
                if is_hit:
                    deltas.append(fragment.deltas[delta_i])
            break
        cells.append(dict(c))
        if is_hit:
            deltas.append(fragment.deltas[delta_i])
            delta_i += 1
        used += c["duration"]
    return cells, deltas


def select_and_resolve_motif(
    fragments: list[RiffFragment],
    role: str,
    total_beats: float,
    scale: Scale,
    base_degree: int,
    rng: random.Random,
) -> Motif | None:
    """Real, section-length `Motif` chained from real bank fragments
    matching `role`. Returns `None` when the bank has zero real coverage
    for this role -- an honest "no bank data" case, never a fabricated
    substitute; the caller falls back to the existing Markov path exactly
    as it already does for any other `None` real-generator result (same
    contract `_try_riff_model_motif` already established).

    Chains real 1-bar fragments (drawn with replacement -- a role with
    sparse real coverage legitimately reuses its own fragments rather
    than falling back) until `total_beats` is filled, trimming the final
    fragment to land exactly on it. Each fragment's own real semitone-
    interval shape is resolved into scale-degree deltas via `motif.
    degree_delta_for_interval`/`_downward` -- the same already-proven,
    already-tested primitives `motif.generate_pitch_deltas` and `riff_
    model.generate_riff_motif` both use. The real SOURCE direction (was
    this interval originally up or down in the actual tab) is preserved
    by default -- genuine verbatim shape -- and only reflected (the same
    real technique proven at both of those other call sites) when it
    would carry the chain outside `_FRAGMENT_REGISTER_SPAN_SEMITONES` of
    `base_degree`, so chaining many real fragments together can never
    reproduce the same unbounded-register-walk bug fixed earlier this
    session.
    """
    candidates = [f for f in fragments if f.role == role]
    if not candidates:
        return None

    anchor_pitch = scale.degree(int(base_degree))
    low_pitch = anchor_pitch - _FRAGMENT_REGISTER_SPAN_SEMITONES
    high_pitch = anchor_pitch + _FRAGMENT_REGISTER_SPAN_SEMITONES

    cell: list[dict] = []
    deltas: list[int] = []
    degree_index = int(base_degree)
    accumulated_beats = 0.0

    while accumulated_beats < total_beats - _EPS:
        fragment = rng.choice(candidates)
        remaining = total_beats - accumulated_beats
        frag_beats = sum(c["duration"] for c in fragment.cell)
        if frag_beats > remaining + _EPS:
            take_cells, take_deltas = _trim_fragment_cell(fragment, remaining)
        else:
            take_cells, take_deltas = [dict(c) for c in fragment.cell], list(fragment.deltas)

        if not take_cells:
            break

        delta_i = 0
        for c in take_cells:
            cell.append(c)
            if c["is_rest"]:
                continue
            semitone_delta = take_deltas[delta_i]
            delta_i += 1
            if semitone_delta == 0:
                d = 0
            else:
                iv = abs(semitone_delta)
                source_upward = semitone_delta > 0
                d = (
                    degree_delta_for_interval(scale, degree_index, iv)
                    if source_upward
                    else degree_delta_for_interval_downward(scale, degree_index, iv)
                )
                candidate_pitch = scale.degree(degree_index + d)
                if not (low_pitch <= candidate_pitch <= high_pitch):
                    d = (
                        degree_delta_for_interval_downward(scale, degree_index, iv)
                        if source_upward
                        else degree_delta_for_interval(scale, degree_index, iv)
                    )
            deltas.append(d)
            degree_index += d

        accumulated_beats += sum(c["duration"] for c in take_cells)

    return Motif(cell=cell, deltas=deltas)
