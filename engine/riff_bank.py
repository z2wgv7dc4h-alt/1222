"""Verbatim GP fragments for labyrinth. Selector must pick one source_song and tile 2-4 bars.
Do not grow a second extractor in tools/boo-lab — call this.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass, field
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
    "extract_bass_fragments_from_file",
    "extract_lead_fragments_from_file",
    "build_riff_bank",
    "classify_failure_reason",
    "save_riff_bank",
    "load_riff_bank",
    "select_and_resolve_motif",
    "DEFAULT_RIFF_BANK_PATH",
    "DEFAULT_BASS_RIFF_BANK_PATH",
    "DEFAULT_LEAD_RIFF_BANK_PATH",
]

_EPS = 1e-6

_ENGINE_ROOT = Path(__file__).resolve().parent
# Same real precedent as `riff_model.DEFAULT_CHECKPOINT_PATH` -- a default
# location callers can check for existence before trying to use it.
DEFAULT_RIFF_BANK_PATH = _ENGINE_ROOT / "data" / "riff_bank.json"

# Real, separate output location for the bass-family bank -- same directory
# as the guitar bank, distinct file so `--instrument guitar` and
# `--instrument bass` over the same source_dir never overwrite each other.
DEFAULT_BASS_RIFF_BANK_PATH = _ENGINE_ROOT / "data" / "bass_riff_bank.json"

# Real, separate output location for the lead/solo-guitar bank. Distinct
# from both above: a real file with 2+ guitar-family tracks yields rhythm
# (guitar) and lead fragments from DIFFERENT real tracks, and both banks
# must survive a single `build_riff_bank` run over the same source_dir.
DEFAULT_LEAD_RIFF_BANK_PATH = _ENGINE_ROOT / "data" / "lead_riff_bank.json"

# GM guitar-family program range (nylon/steel/jazz/clean/muted/overdriven/
# distortion/harmonics) -- the same real GM-program convention this
# project already uses elsewhere (midi_export.py's own `_GUITAR_PROGRAM`)
# to identify a guitar track, reused here since real track NAMES in this
# corpus are wildly inconsistent (several files literally name tracks
# after the real band members, e.g. "Jason"/"Lee" for Follow The Signs --
# BoO's own real guitarists -- rather than "Guitar").
_GUITAR_GM_PROGRAMS = range(24, 32)

# GM bass-family program range (acoustic/electric bass finger/pick/slap/
# synth-bass variants). Same real GM-program convention as _GUITAR_GM_PROGRAMS
# above, just the other half of the same instrument-family split -- a real
# track NAME is unreliable in this corpus, so program is the one consistent
# signal for the bass track too.
_BASS_GM_PROGRAMS = range(32, 40)

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
    machinery unmodified once resolved against a target scale). A real hit
    additionally carries any present technique keys -- `"palm_mute"`,
    `"harmonic"`, `"slide"`, `"tremolo"`, `"vibrato"`, `"accent"` -- each
    written only when true, never as a `false` key; a rest never carries
    any.

    `deltas`: real SEMITONE intervals between consecutive real notes
    (first note's own delta is its interval from the fragment's own
    first pitch, i.e. 0) -- deliberately NOT a scale-degree delta yet,
    see this module's own docstring for why.

    `role`: this project's own canonical role name when the tab's nearest
    preceding real marker resolved to one, else `None` (never guessed).
    `raw_marker`: the real marker text itself when present, kept even
    when `role` is `None` (an honest, unmapped structural label like "A"
    or "III" is still real information).

    `track`: the real rhythm-guitar track's own name (`_select_rhythm_
    track`'s pick) -- kept for provenance, since a selected riff's Motif
    carries `source_song`/`measure_start`/`track` back to the caller.

    `instrument`: "guitar" (default), "bass", or "lead" -- which real
    GM-family track this fragment was extracted from (`_select_rhythm_track`,
    `_select_bass_track`, or `_select_lead_track`). Defaulted so existing
    cached bank JSON without the field still loads; a guitar fragment is
    exactly what every pre-`instrument` entry in `engine/data/riff_bank.json`
    already is.

    `source_type`: "tab_verbatim" (default) when the data came from a real
    Guitar Pro tab, or "audio_transcribed" when it was reconstructed from a
    real audio stem (no matched GP file). Defaulted so every existing cached
    entry -- all tab-derived -- loads correctly without a rebuild.
    Downstream selectors must always PREFER "tab_verbatim" over
    "audio_transcribed" for the same role; a transcribed fragment is an
    honest fallback, never an equal substitute for a real tab.

    `chord_notes`: real, COMPLETE list of every note's `realValue` in each
    HIT -- one entry per non-rest cell, same order (a rest contributes
    nothing, exactly like `deltas`). A single-note hit is a real 1-element
    list. Pure addition: `deltas` still comes from the top note only, so
    every existing consumer is unaffected.

    `chord_frets`: real tabber string/fret choice per note in the same
    hits, `(string, fret)` -- pyguitarpro exposes the fret as `Note.value`
    (there is no `.fret` attribute), and `Note.string` directly. Ground
    truth for how a real player actually VOICES a chord across strings
    (which the engine otherwise re-derives via `_snap_to_playable_octave`).
    Defaulted to empty so existing cache entries load unchanged.
    """

    source_song: str
    source_file: str
    measure_index: int
    track: str
    cell: list[dict]
    deltas: list[int]
    role: str | None
    raw_marker: str | None
    instrument: str = "guitar"
    source_type: str = "tab_verbatim"
    chord_notes: list[list[int]] = field(default_factory=list)
    chord_frets: list[list[tuple[int, int]]] = field(default_factory=list)


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


def _select_bass_track(song: "guitarpro.Song") -> "guitarpro.Track | None":
    """Real bass-guitar track selection for one parsed `Song`.

    Same real GM-program signal as `_select_rhythm_track`, but the bass
    family (GM program 32-39) instead of guitar (24-31), and no
    register-cutoff tiebreak: a real tab normally carries exactly one real
    bass track, so the first real bass-family, non-percussion candidate is
    the pick. Returns `None` when no real bass-family track exists at all.
    """
    candidates = [
        t
        for t in song.tracks
        if not t.isPercussionTrack and t.channel.instrument in _BASS_GM_PROGRAMS
    ]
    if not candidates:
        return None
    return candidates[0]


def _register_fraction(track: "guitarpro.Track") -> float:
    """Real fraction of a track's own real notes that fall in the rhythm
    register (below `_RHYTHM_LEAD_PITCH_CUTOFF`) -- the exact measure
    `_select_rhythm_track` uses internally to rank guitar candidates. Kept
    as a module-level helper so `_select_lead_track` can rank the SAME way
    and simply invert the comparison. (`_select_rhythm_track`'s own nested
    copy is left untouched; this is the one shared definition new callers
    use.)"""
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


def _select_lead_track(song: "guitarpro.Song") -> "guitarpro.Track | None":
    """Real lead/solo-guitar track selection for one parsed `Song`.

    Same real GM-program filter as `_select_rhythm_track` (guitar family,
    not percussion), but picks the HIGHER-register candidate -- the one
    that least often falls below `_RHYTHM_LEAD_PITCH_CUTOFF`, i.e. `min` of
    `_register_fraction` rather than `max`. The already-selected rhythm
    track is excluded so the two banks always come from genuinely different
    real tracks even when fractions tie.

    Returns `None` unless the file has 2+ real guitar-family tracks: a
    single-guitar file has no separate real lead line to extract, and
    fabricating one by re-labelling the rhythm track is exactly the
    dishonest degrade this project forbids.
    """
    candidates = [
        t
        for t in song.tracks
        if not t.isPercussionTrack and t.channel.instrument in _GUITAR_GM_PROGRAMS
    ]
    if len(candidates) < 2:
        return None
    rhythm = _select_rhythm_track(song)
    others = [t for t in candidates if t is not rhythm]
    if not others:
        return None
    return min(others, key=_register_fraction)


# Real per-note technique/articulation read from pyguitarpro's own
# `NoteEffect`, verified against `inspect.signature(guitarpro.NoteEffect.
# __init__)`. Each tuple is (real NoteEffect attribute, output cell key).
# A hit is tagged when ANY note in the beat carries the technique (GP
# chords can articulate individual notes); only true tags are ever written,
# never a `false` key, so existing JSON diffs stay minimal.
_TECHNIQUE_EFFECTS: list[tuple[str, str]] = [
    ("palmMute", "palm_mute"),
    ("vibrato", "vibrato"),
    ("accentuatedNote", "accent"),
    ("heavyAccentuatedNote", "accent"),
]


def _beat_techniques(notes: list) -> dict:
    """Real technique keys for one non-rest beat's notes -- `{}` when no
    note carries any. Object-valued effects (`harmonic`, `tremoloPicking`)
    tag when present; a non-empty `slides` list tags `slide`. Reads via
    `getattr` so pyguitarpro's `NOTHING` effect sentinel or a version
    difference can never raise."""
    out: dict = {}
    for note in notes:
        effect = getattr(note, "effect", None)
        if effect is None:
            continue
        for attr, key in _TECHNIQUE_EFFECTS:
            if getattr(effect, attr, False):
                out[key] = True
        if getattr(effect, "harmonic", None) is not None:
            out["harmonic"] = True
        if getattr(effect, "tremoloPicking", None) is not None:
            out["tremolo"] = True
        if getattr(effect, "slides", None):
            out["slide"] = True
    return out


def _measure_cell_and_deltas(
    measure: "guitarpro.Measure",
) -> tuple[list[dict], list[int], list[list[int]], list[list[tuple[int, int]]]]:
    """The real per-measure cell/delta-building inner loop, shared by all
    three real instrument extractors (`extract_fragments_from_file`,
    `extract_bass_fragments_from_file`, `extract_lead_fragments_from_file`)
    rather than copy-pasted. Real rhythm content lives in the first voice;
    GP's second voice is a rare alt-notation layer.

    Each hit dict is `{"duration", "is_rest"}` plus real technique keys
    (`palm_mute`/`harmonic`/`slide`/`tremolo`/`vibrato`/`accent`) only when
    that technique is actually present. A rest carries no technique keys --
    there is nothing to articulate.

    Returns `(cell, deltas, chord_notes, chord_frets)`. `chord_notes` and
    `chord_frets` each hold one real entry per HIT (never per rest), in the
    same order -- the complete real note list per hit and the tabber's own
    `(string, fret)` choice per note. `deltas` still comes from the top
    note only, unchanged."""
    cell: list[dict] = []
    deltas: list[int] = []
    chord_notes: list[list[int]] = []
    chord_frets: list[list[tuple[int, int]]] = []
    prev_pitch: int | None = None
    for voice in measure.voices:
        for beat in voice.beats:
            beats_val = 4.0 / beat.duration.value
            if beat.duration.isDotted:
                beats_val *= 1.5
            is_rest = not beat.notes
            hit = {"duration": beats_val, "is_rest": is_rest}
            if not is_rest:
                hit.update(_beat_techniques(beat.notes))
                chord_notes.append([int(n.realValue) for n in beat.notes])
                chord_frets.append([(int(n.string), int(n.value)) for n in beat.notes])
                pitch = max(n.realValue for n in beat.notes)
                if prev_pitch is None:
                    deltas.append(0)
                else:
                    deltas.append(pitch - prev_pitch)
                prev_pitch = pitch
            cell.append(hit)
        break  # real rhythm content lives in the first voice
    return cell, deltas, chord_notes, chord_frets


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
        raise ValueError("no real guitar-family track found (no GM-program 24-31 track)")
    if not track.measures:
        raise ValueError("track has no measures")

    fragments: list[RiffFragment] = []
    current_role: str | None = None
    current_raw_marker: str | None = None

    for measure_index, measure in enumerate(track.measures):
        header = song.measureHeaders[measure_index] if measure_index < len(song.measureHeaders) else None
        if header is not None and header.marker is not None:
            role, raw_marker = _resolve_role(header.marker.title, title)
            if role is not None or raw_marker is not None:
                current_role, current_raw_marker = role, raw_marker

        cell, deltas, chord_notes, chord_frets = _measure_cell_and_deltas(measure)
        if not cell or not deltas:
            continue
        fragments.append(
            RiffFragment(
                source_song=title,
                source_file=path.name,
                measure_index=measure_index,
                track=track.name,
                cell=cell,
                deltas=deltas,
                chord_notes=chord_notes,
                chord_frets=chord_frets,
                role=current_role,
                raw_marker=current_raw_marker,
            )
        )

    return fragments


def extract_bass_fragments_from_file(
    path: str | Path, song_title: str | None = None,
) -> list[RiffFragment]:
    """Real, per-bar bass fragment extraction from one real Guitar Pro file
    -- the bass-family mirror of `extract_fragments_from_file`.

    Uses `_select_bass_track` (GM program 32-39) and the shared
    `_measure_cell_and_deltas` inner loop, and tags every fragment
    `instrument="bass"`. Raises `ValueError` on a file with no real usable
    bass-family track (fails closed, never fabricates a fragment) or an
    empty measure list -- same real contract as the guitar extractor.
    """
    if guitarpro is None:
        raise ImportError(
            "riff_bank requires the 'pyguitarpro' package. It is listed in "
            "engine/requirements.txt -- install with `pip install pyguitarpro`."
        )
    path = Path(path)
    song = guitarpro.parse(str(path))
    title = song_title if song_title is not None else (song.title or path.stem)

    track = _select_bass_track(song)
    if track is None:
        raise ValueError("no real bass-family track found (no GM-program 32-39 track)")
    if not track.measures:
        raise ValueError("track has no measures")

    fragments: list[RiffFragment] = []
    current_role: str | None = None
    current_raw_marker: str | None = None

    for measure_index, measure in enumerate(track.measures):
        header = song.measureHeaders[measure_index] if measure_index < len(song.measureHeaders) else None
        if header is not None and header.marker is not None:
            role, raw_marker = _resolve_role(header.marker.title, title)
            if role is not None or raw_marker is not None:
                current_role, current_raw_marker = role, raw_marker

        cell, deltas, chord_notes, chord_frets = _measure_cell_and_deltas(measure)
        if not cell or not deltas:
            continue
        fragments.append(
            RiffFragment(
                source_song=title,
                source_file=path.name,
                measure_index=measure_index,
                track=track.name,
                cell=cell,
                deltas=deltas,
                chord_notes=chord_notes,
                chord_frets=chord_frets,
                role=current_role,
                raw_marker=current_raw_marker,
                instrument="bass",
            )
        )

    return fragments


def extract_lead_fragments_from_file(
    path: str | Path, song_title: str | None = None,
) -> list[RiffFragment]:
    """Real, per-bar lead/solo fragment extraction from one real Guitar Pro
    file -- the lead-guitar mirror of `extract_fragments_from_file`.

    Uses `_select_lead_track` (the higher-register guitar-family track,
    only when 2+ exist) and the shared `_measure_cell_and_deltas` inner
    loop, and tags every fragment `instrument="lead"`. Raises `ValueError`
    on a file with no real distinct lead track (fails closed, never
    fabricates a lead line from a single-guitar file) or an empty measure
    list -- same real contract as the other two extractors. This is the
    real extracted lead-line data `lead.generate_lead_line` currently has
    none of.
    """
    if guitarpro is None:
        raise ImportError(
            "riff_bank requires the 'pyguitarpro' package. It is listed in "
            "engine/requirements.txt -- install with `pip install pyguitarpro`."
        )
    path = Path(path)
    song = guitarpro.parse(str(path))
    title = song_title if song_title is not None else (song.title or path.stem)

    track = _select_lead_track(song)
    if track is None:
        raise ValueError("no distinct real lead-guitar track found (needs 2+ guitar-family tracks)")
    if not track.measures:
        raise ValueError("track has no measures")

    fragments: list[RiffFragment] = []
    current_role: str | None = None
    current_raw_marker: str | None = None

    for measure_index, measure in enumerate(track.measures):
        header = song.measureHeaders[measure_index] if measure_index < len(song.measureHeaders) else None
        if header is not None and header.marker is not None:
            role, raw_marker = _resolve_role(header.marker.title, title)
            if role is not None or raw_marker is not None:
                current_role, current_raw_marker = role, raw_marker

        cell, deltas, chord_notes, chord_frets = _measure_cell_and_deltas(measure)
        if not cell or not deltas:
            continue
        fragments.append(
            RiffFragment(
                source_song=title,
                source_file=path.name,
                measure_index=measure_index,
                track=track.name,
                cell=cell,
                deltas=deltas,
                chord_notes=chord_notes,
                chord_frets=chord_frets,
                role=current_role,
                raw_marker=current_raw_marker,
                instrument="lead",
            )
        )

    return fragments


def _is_zip_container(path: Path) -> bool:
    """Real, content-based check for a ZIP-container file (the real
    internal format of `.gpx`) regardless of its own extension -- a real
    corpus scan found files with a `.gp3`/`.gp4`/`.gp5` extension that are
    actually mislabeled `.gpx` content, which the suffix-only check
    misses entirely."""
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"PK"
    except OSError:
        return False


def build_riff_bank(
    source_dir: str | Path, instrument: str = "guitar",
) -> tuple[list[RiffFragment], list[tuple[str, str]]]:
    """Real bank build across every `*.gp[3-5]`/`*.gp4` file under
    `source_dir` (recursive). Returns `(fragments, failures)` -- failures
    is a real, honest `(filename, reason)` list, never silently dropped.
    Deduplicates by `(source_song lowercased, measure_index)` isn't
    attempted here -- the same real song appears multiple times across
    sources with different transcriptions, and keeping every real
    transcription's own fragments is deliberate (more real coverage per
    role, not redundant noise -- generation-time selection can weight or
    dedupe further once actually wired in).

    `instrument` selects which real instrument family to extract from every
    file: `"guitar"` (default, `extract_fragments_from_file`, the existing
    behaviour), `"bass"` (`extract_bass_fragments_from_file`), or `"lead"`
    (`extract_lead_fragments_from_file`, the higher-register track of a
    2+-guitar file). The same `source_dir` can therefore be walked three
    times into three separate banks.
    """
    extractors = {
        "guitar": extract_fragments_from_file,
        "bass": extract_bass_fragments_from_file,
        "lead": extract_lead_fragments_from_file,
    }
    if instrument not in extractors:
        raise ValueError(f"instrument must be one of {sorted(extractors)}, got {instrument!r}")
    extract = extractors[instrument]

    source_dir = Path(source_dir)
    fragments: list[RiffFragment] = []
    failures: list[tuple[str, str]] = []
    for path in sorted(source_dir.glob("**/*.gp*")):
        if path.suffix.lower() == ".gpx" or _is_zip_container(path):
            # Real content-based check, not just the .gpx extension: found
            # via a real corpus scan that 53 of 54 "parse_error" failures
            # were actually mislabeled .gpx content (a ZIP container --
            # `PK\x03\x04` signature) wearing a .gp3/.gp4/.gp5 extension,
            # slipping past the suffix-only check and landing in the
            # generic parse_error bucket instead of the already-understood
            # gpx_unsupported one.
            failures.append((str(path), "gpx sub-format not decodable by this pyguitarpro version"))
            continue
        try:
            fragments.extend(extract(path))
        except Exception as e:  # noqa: BLE001 - real, honest per-file failure capture
            failures.append((str(path), str(e)))
    return fragments, failures


def classify_failure_reason(reason: str) -> str:
    """Real, stable category for one `build_riff_bank` failure reason string
    -- lets a caller count distinct real failure kinds without string-
    matching volatile parse-error detail (a `GPException` embeds raw file
    bytes). Categories:

      `gpx_unsupported`      -- .gpx sub-format this pyguitarpro can't read
      `no_guitar_track`      -- no GM-program 24-31 track in the file
      `no_bass_track`        -- no GM-program 32-39 track in the file
      `no_lead_track`        -- fewer than 2 guitar-family tracks (nothing
                                distinct to call the lead)
      `track_has_no_measures`-- selected track has an empty measure list
      `parse_error`          -- anything else (real pyguitarpro parse or
                                decoding failure)
    """
    if reason.startswith("gpx sub-format"):
        return "gpx_unsupported"
    if reason.startswith("no real guitar-family track"):
        return "no_guitar_track"
    if reason.startswith("no real bass-family track"):
        return "no_bass_track"
    if reason.startswith("no distinct real lead-guitar track"):
        return "no_lead_track"
    if reason == "track has no measures":
        return "track_has_no_measures"
    return "parse_error"


def save_riff_bank(fragments: list[RiffFragment], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(f) for f in fragments], indent=2), encoding="utf-8")


def load_riff_bank(path: str | Path) -> list[RiffFragment]:
    data: list[dict[str, Any]] = json.loads(Path(path).read_text(encoding="utf-8"))
    return [RiffFragment(**d) for d in data]


# Real register bound for resolving ONE selected riff's own pitch shape --
# same real, already-proven value as `motif._PITCH_REGISTER_SPAN_SEMITONES`
# and `riff_model._RIFF_REGISTER_SPAN_SEMITONES` (one real octave each way
# from the riff's own anchor). Kept as this module's own constant rather
# than importing motif's private one, matching `riff_model.py`'s own
# existing precedent of each generator module declaring the same real
# value independently.
_RIFF_REGISTER_SPAN_SEMITONES = 12

# A real riff is 2-4 contiguous real bars from ONE song's own rhythm-guitar
# track -- NOT a bag of unrelated 1-bar fragments stitched from many songs
# (that "role-bag collage" was tried, demoed, and killed -- see docs/
# DECISIONS.md's "Kill / ghetto" list: "sounds like shit," a medley, not a
# riff). Fragments are still extracted one bar at a time (`_FRAGMENT_BARS`
# above), but a real riff is a maximal run of CONSECUTIVE same-role bars
# from the SAME `(source_song, source_file, track)`, 2-4 of them.
_MIN_RIFF_BARS = 2
_MAX_RIFF_BARS = 4


def _candidate_riff_runs(fragments: list[RiffFragment], role: str) -> list[list[RiffFragment]]:
    """Every real 2-4-bar contiguous same-role run, grouped by the ONE
    real `(source_song, source_file, track)` it comes from. A run is
    "contiguous" when consecutive fragments have consecutive real
    `measure_index` values AND the same `role` -- never bars stitched
    across a role boundary or across two different real songs."""
    groups: dict[tuple[str, str, str], list[RiffFragment]] = {}
    for f in fragments:
        groups.setdefault((f.source_song, f.source_file, f.track), []).append(f)

    runs: list[list[RiffFragment]] = []
    for group in groups.values():
        group.sort(key=lambda f: f.measure_index)
        n = len(group)
        for start in range(n):
            if group[start].role != role:
                continue
            for length in range(_MIN_RIFF_BARS, _MAX_RIFF_BARS + 1):
                end = start + length
                if end > n:
                    break
                window = group[start:end]
                contiguous = all(
                    window[i + 1].measure_index == window[i].measure_index + 1
                    for i in range(len(window) - 1)
                )
                same_role = all(w.role == role for w in window)
                if not (contiguous and same_role):
                    break  # a longer window from this same start can't work either
                runs.append(window)
    return runs


def _resolve_run(
    run: list[RiffFragment], scale: Scale, base_degree: int,
) -> tuple[list[dict], list[int]]:
    """Real scale-degree resolution of one contiguous run's own real
    semitone-interval shape -- same already-proven primitives (`motif.
    degree_delta_for_interval`/`_downward`, real register-bound reflection)
    this project already uses everywhere else pitch content gets resolved,
    just scoped to a real 2-4 bar run instead of an ever-growing chain."""
    anchor_pitch = scale.degree(int(base_degree))
    low_pitch = anchor_pitch - _RIFF_REGISTER_SPAN_SEMITONES
    high_pitch = anchor_pitch + _RIFF_REGISTER_SPAN_SEMITONES

    cell: list[dict] = []
    deltas: list[int] = []
    degree_index = int(base_degree)

    for fragment in run:
        delta_i = 0
        for c in fragment.cell:
            cell.append(dict(c))
            if c["is_rest"]:
                continue
            semitone_delta = fragment.deltas[delta_i]
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

    return cell, deltas


def _tile_cell_and_deltas(
    cell: list[dict], deltas: list[int], total_beats: float,
) -> tuple[list[dict], list[int]]:
    """Real repeat of ONE riff's own `(cell, deltas)` to fill
    `total_beats` -- same real truncate-the-final-repeat discipline as
    `rhythm.tile_cell` (never overshoots), extended to keep `deltas` in
    lockstep so a repeated hit gets the exact same real pitch every time
    the riff repeats (a genuine, verbatim tile -- not `rhythm.tile_cell`
    itself, since that helper only tiles durations, but the same proven
    real technique)."""
    if not cell:
        raise ValueError("cell must be non-empty")
    if total_beats <= 0:
        raise ValueError("total_beats must be > 0")
    cell_sum = sum(c["duration"] for c in cell)
    if cell_sum <= 0:
        raise ValueError("cell must have positive total duration")

    out_cell: list[dict] = []
    out_deltas: list[int] = []
    remaining = total_beats
    delta_i = 0
    while remaining > _EPS:
        for sub in cell:
            if remaining <= _EPS:
                break
            dur = min(sub["duration"], remaining)
            out_cell.append({"duration": dur, "is_rest": sub["is_rest"]})
            if not sub["is_rest"]:
                out_deltas.append(deltas[delta_i % len(deltas)])
                delta_i += 1
            remaining -= dur
    return out_cell, out_deltas


def select_and_resolve_motif(
    fragments: list[RiffFragment],
    role: str,
    total_beats: float,
    scale: Scale,
    base_degree: int,
    rng: random.Random,
) -> Motif | None:
    """Real `Motif` built from ONE real 2-4 bar contiguous riff, tiled to
    fill `total_beats`. Returns `None` when the bank has zero real 2-4
    bar contiguous same-role run for `role` -- an honest "no bank data"
    case; the caller (`song._try_riff_bank_motif`) must NOT silently fall
    back to Markov for this (see docs/DECISIONS.md: "Silent Markov...
    must become hard-fail or drop the role").

    `select`: real candidate runs (`_candidate_riff_runs`) are picked via
    `rng.choice` -- same seeded rng the whole project already requires,
    same real seed always picks the same real run. The returned `Motif`
    carries real provenance as plain instance attributes (`source_song`,
    `measure_start`, `track`) -- `Motif` itself (motif.py) is out of this
    ticket's scope, so these are set directly on the instance rather than
    added as a new dataclass field.
    """
    runs = _candidate_riff_runs(fragments, role)
    if not runs:
        return None

    run = rng.choice(runs)
    riff_cell, riff_deltas = _resolve_run(run, scale, base_degree)
    cell, deltas = _tile_cell_and_deltas(riff_cell, riff_deltas, total_beats)

    motif = Motif(cell=cell, deltas=deltas)
    motif.source_song = run[0].source_song
    motif.measure_start = run[0].measure_index
    motif.track = run[0].track
    return motif


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a real GP riff bank.")
    parser.add_argument("--source", required=True, help="directory of .gp/.gp3-.gp5 files (recursive)")
    parser.add_argument("--instrument", choices=["guitar", "bass", "lead"], default="guitar")
    parser.add_argument("--out", type=Path, default=None, help="defaults per instrument")
    args = parser.parse_args()

    default_out = {
        "guitar": DEFAULT_RIFF_BANK_PATH,
        "bass": DEFAULT_BASS_RIFF_BANK_PATH,
        "lead": DEFAULT_LEAD_RIFF_BANK_PATH,
    }
    out = args.out or default_out[args.instrument]
    fragments, failures = build_riff_bank(args.source, instrument=args.instrument)
    save_riff_bank(fragments, out)
    print(
        f"{args.instrument}: {len(fragments)} fragments from "
        f"{len(failures)} real failure(s) -> {out}"
    )
    for filename, reason in failures:
        print("  FAIL", filename, "-", reason)
