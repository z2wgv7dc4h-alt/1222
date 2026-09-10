"""Voice leading, dissonance shading, and the cross-section energy arc.

Ported from reference/ww-forge-prior-attempt/engine/theory.py (VoiceLeader,
shade(), ARC) per PORTS.md. See TASKS.md P1.10 for the port record.

Deviation from the port brief: shade() and ARC actually live in the
reference project's theory.py, not style_packs.py (style_packs.py only has
PACKS/VOCAB -- the mood-preset tables that fed P1.7). Noted per the port
skill's instruction to trust the file over a description that doesn't match
it.

Unlike the reference, this module does not carry its own SCALES table --
this project's `scales.py` is the single source of truth for interval sets
(see .claude/rules/anti-patterns.md: "two scale names, one interval set:
aliases only, documented"). `Scale` below resolves its intervals through
`scales.get_scale`, so an unknown scale name fails the same way it does
everywhere else in this codebase. The reference's `phrygian_dominant` was
missing here for several sessions (this note originally flagged it as a
real, deliberately-deferred gap) -- now real, ported directly into
`scales.py`'s own table (not invented).
"""
from __future__ import annotations

import random

from scales import get_scale

# Intervals that read as tension rather than rest: minor 2nd, major 2nd,
# tritone, major 7th (all mod 12).
DISSONANT = (1, 2, 6, 11)


def _weighted_choice(items: list[tuple[int, float]], rng: random.Random) -> int:
    """The one real accumulate-and-compare weighted pick, shared by
    `VoiceLeader._weighted_interval` and `motif.pick_pitch_interval` --
    previously two independent, duplicate implementations of the exact
    same algorithm (confirmed by reading both). `items` is a real,
    non-empty list of `(key, weight)` pairs; raises on an empty or
    non-positive-total list rather than fabricating a pick."""
    if not items:
        raise ValueError("items must be non-empty")
    total = sum(w for _key, w in items)
    if total <= 0:
        raise ValueError("weights must sum to a positive total")
    r = rng.random() * total
    acc = 0.0
    for key, w in items:
        acc += w
        if r <= acc:
            return int(key)
    return int(items[-1][0])


def pick_pitch_interval_markov(
    weights: dict,
    rng: random.Random,
    markov: dict[int, dict[int, float]] | None,
    prev_interval: int | None,
) -> int:
    """Real, corpus-informed sequence-aware interval pick: when `markov`
    (a real, corpus-derived first-order transition table -- see
    `reference_vocab.build_preset_from_corpus`) has a real, non-empty row
    for `prev_interval`, draws the NEXT interval from THAT context-
    dependent distribution instead of the static marginal `weights`.
    Falls back to `weights` when `markov` is `None`, `prev_interval` is
    `None` (the first pick of a phrase -- no context yet), or the corpus
    never actually observed a transition FROM this specific interval --
    never fabricates a distribution for an unseen context. Used by both
    `VoiceLeader._weighted_interval` and `motif.generate_pitch_deltas`/
    `lead.generate_sequence_line`, so a preset's real corpus-observed
    note-to-note tendencies reach every real pitch-selection surface, not
    just one."""
    if markov is not None and prev_interval is not None:
        row = markov.get(prev_interval)
        if row:
            return _weighted_choice(list(row.items()), rng)
    return _weighted_choice(list((weights or {}).items()), rng)


class Scale:
    """A root MIDI note plus a named interval set (resolved via scales.py)."""

    __slots__ = ("root", "name", "intervals")

    def __init__(self, root: int, name: str = "minor"):
        self.root = int(root)
        self.name = name
        self.intervals = get_scale(name)  # raises ValueError on unknown name

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Scale(root={self.root}, name={self.name!r})"

    @property
    def pitch_classes(self) -> set:
        return {(self.root + i) % 12 for i in self.intervals}

    def contains(self, pitch: int) -> bool:
        return int(pitch) % 12 in self.pitch_classes

    def degree(self, n: int, octave: int = 0) -> int:
        """MIDI pitch of the nth scale degree above the root (0 = root).

        n wraps past the top of the scale into the next octave; negative n
        walks below the root.
        """
        k = len(self.intervals)
        extra, idx = divmod(int(n), k)
        return self.root + self.intervals[idx] + 12 * (extra + int(octave))

    def nearest(self, pitch: int, prefer_down: bool = True) -> int:
        """Nearest in-scale MIDI pitch to an arbitrary one."""
        pitch = int(pitch)
        if self.contains(pitch):
            return pitch
        for d in range(1, 13):
            lo, hi = pitch - d, pitch + d
            first, second = (lo, hi) if prefer_down else (hi, lo)
            if self.contains(first):
                return first
            if self.contains(second):
                return second
        return pitch

    def index_of(self, pitch: int) -> int:
        """Scale-degree index of `pitch` (snapped into the scale first)."""
        p = self.nearest(pitch)
        octaves, semi = divmod(p - self.root, 12)
        try:
            i = self.intervals.index(semi)
        except ValueError:
            i = min(range(len(self.intervals)), key=lambda k: abs(self.intervals[k] - semi))
        return octaves * len(self.intervals) + i

    def step(self, pitch: int, n: int) -> int:
        """Move n scale degrees from `pitch` -- stepwise, diatonic motion."""
        return self.degree(self.index_of(pitch) + int(n))

    def transposed(self, root: int) -> "Scale":
        return Scale(root, self.name)


def shade(weights: dict, dissonance: float = 0.4) -> dict:
    """Re-weight a style's interval vocabulary for one section's appetite for
    tension. High dissonance pushes m2/M2/tritone/M7 forward and pulls the
    consonances back; low dissonance does the reverse. Nothing already in
    `weights` is ever zeroed out, so a style never loses its own character --
    only its balance shifts. An interval absent from the input never appears
    in the output either -- shading rebalances a vocabulary, it doesn't
    invent new intervals.
    """
    d = max(0.0, min(1.0, float(dissonance)))
    out = {}
    for iv, w in (weights or {0: 1}).items():
        if int(iv) % 12 in DISSONANT:
            w = float(w) * (0.15 + 1.85 * d)
        else:
            w = float(w) * (1.25 - 0.35 * d)
        out[int(iv)] = max(0.01, round(w, 4))
    return out


class VoiceLeader:
    """Turns a weighted interval vocabulary into actual MIDI pitches.

    `pick` chooses an interval above the section's anchor by weight, snaps it
    into the key, then places it in whichever octave sits closest to the note
    just played. `walk` is pure stepwise motion to the neighbouring scale
    tone. Both stay inside [low, high] so nothing wanders off the fretboard.
    """

    def __init__(
        self,
        scale: Scale,
        weights: dict | None = None,
        rng=None,
        low: int | None = None,
        high: int | None = None,
        anchor: int | None = None,
        motion: float = 0.3,
        markov: dict[int, dict[int, float]] | None = None,
    ):
        self.scale = scale
        self.weights = {
            int(k): float(v) for k, v in (weights or {0: 1.0}).items() if float(v) > 0
        }
        self.rng = rng or random.Random(0)
        self.anchor = int(scale.root if anchor is None else anchor)
        self.low = int(self.anchor - 5 if low is None else low)
        self.high = int(self.anchor + 19 if high is None else high)
        if self.high < self.low:
            self.low, self.high = self.high, self.low
        self.motion = max(0.0, min(1.0, float(motion)))
        self.last = None
        # Real, corpus-derived first-order transition table (see
        # `reference_vocab.build_preset_from_corpus`) -- `None` for any
        # preset not calibrated with real sequence data, matching the
        # rest of this project's optional-field-with-real-fallback
        # discipline. `last_interval` tracks the PREVIOUS interval-from-
        # anchor pick (distinct from `self.last`, which tracks the actual
        # PITCH) -- the real context `pick_pitch_interval_markov` needs.
        self.markov = markov
        self.last_interval: int | None = None

    # -- internals ---------------------------------------------------------
    def _weighted_interval(self, exclude_root: bool = False) -> int:
        weights = self.weights
        markov = self.markov
        if exclude_root:
            filtered = {iv: w for iv, w in weights.items() if iv % 12 != 0}
            weights = filtered or weights
            if markov is not None:
                markov = {
                    prev: ({iv: w for iv, w in row.items() if iv % 12 != 0} or row)
                    for prev, row in markov.items()
                }
        if not weights:
            weights = {0: 1.0}
        iv = pick_pitch_interval_markov(weights, self.rng, markov, self.last_interval)
        self.last_interval = iv
        return iv

    def _place(self, pitch: int, prev: int | None) -> int:
        """Nearest register of `pitch`'s pitch class to `prev`, inside span."""
        pc = int(pitch) % 12
        # The anchor is the riff's pedal note, not just a pitch class: coming
        # home always means the anchor's own register. Deliberate octave
        # displacement is stab(), not this.
        if pc == self.anchor % 12 and self.low <= self.anchor <= self.high:
            return self.anchor
        cands = [p for p in range(self.low, self.high + 1) if p % 12 == pc]
        if not cands:
            return max(self.low, min(self.high, int(pitch)))
        if prev is None:
            return min(cands, key=lambda p: (abs(p - self.anchor), p))
        return min(cands, key=lambda p: (abs(p - prev), p))

    def _remember(self, pitch: int) -> int:
        self.last = int(pitch)
        return self.last

    # -- public ------------------------------------------------------------
    def pick(self, prev: int | None = None, exclude_root: bool = False) -> int:
        """Next pitch: interval by weight, register by proximity."""
        prev = self.last if prev is None else prev
        iv = self._weighted_interval(exclude_root)
        target = self.scale.nearest(self.anchor + iv)
        return self._remember(self._place(target, prev))

    def walk(self, prev: int | None = None, direction: int = 0) -> int:
        """One scale step from the previous note. Reflects off the edges of
        the span instead of leaving it."""
        prev = self.last if prev is None else prev
        if prev is None:
            return self.pick()
        d = int(direction) or self.rng.choice((-1, 1))
        p = self.scale.step(prev, d)
        if not (self.low <= p <= self.high):
            p = self.scale.step(prev, -d)
        if not (self.low <= p <= self.high):
            p = self.scale.nearest(max(self.low, min(self.high, prev)))
        return self._remember(p)

    def move(self, prev: int | None = None, exclude_root: bool = False) -> int:
        """`motion` decides stepwise walk vs. a fresh weighted pick. Active
        styles (melodic, chill) walk the scale; anchored styles (deathcore,
        groovy) mostly re-pick and land back on the pedal note."""
        if self.rng.random() < self.motion:
            return self.walk(prev)
        return self.pick(prev, exclude_root=exclude_root)

    def stab(self, prev: int | None = None, interval: int = 12) -> int:
        """A deliberate interval leap (e.g. the octave stab). Not voice
        leading -- explicitly exempt from the smoothing logic above."""
        prev = self.anchor if prev is None else prev
        return self._remember(max(self.low, min(self.high + 12, int(prev) + int(interval))))


# ---------------------------------------------------------------------------
# Cross-section energy arc
# ---------------------------------------------------------------------------
# One row per song letter. `energy` is the master dial -- density is derived
# from it below so the two can never drift apart. `register` is a semitone
# offset for where the section sits on the neck; `dissonance` feeds shade();
# `start_degree` is the scale degree the section anchors on.
ARC = {
    "I": {"energy": 0.30, "register": 12, "dissonance": 0.15, "start_degree": 0},
    "A": {"energy": 0.60, "register": 0, "dissonance": 0.35, "start_degree": 0},
    "B": {"energy": 0.70, "register": 0, "dissonance": 0.40, "start_degree": 2},
    "K": {"energy": 0.20, "register": 12, "dissonance": 0.10, "start_degree": 4},
    "U": {"energy": 0.85, "register": 0, "dissonance": 0.55, "start_degree": 0},
    "C": {"energy": 1.00, "register": 0, "dissonance": 0.85, "start_degree": 0},
    "S": {"energy": 0.80, "register": 12, "dissonance": 0.60, "start_degree": 4},
    "O": {"energy": 0.40, "register": 0, "dissonance": 0.30, "start_degree": 0},
}

_ARC_DEFAULT = {"energy": 0.60, "register": 0, "dissonance": 0.35, "start_degree": 0}

ROLE_LETTER = {
    "intro": "I", "i": "I",
    "build": "U", "buildup": "U", "u": "U",
    "solo": "S", "s": "S",
    "outro": "O", "o": "O",
    "breakdown": "C", "c": "C",
    "chill": "K", "synth": "K", "k": "K",
    # X.28 -- "A"/"B" were real, tested ARC rows with no role ever mapped to
    # them (only reachable via arc(letter="A"/"B") directly). Verse/chorus
    # are the real destination for them: "A" (energy 0.60) vs "B" (energy
    # 0.70) is exactly the real verse-vs-chorus energy contrast Metalerator's
    # own verse/chorus riff generators show (sparse pedal-tone verse, denser
    # power-chord chorus) -- see PORTS.md/TASKS.md X.28.
    "verse": "A", "v": "A",
    "chorus": "B", "ch": "B",
}


def arc(letter: str | None = None, role: str | None = None) -> dict:
    """Energy/register/dissonance/anchor for one song letter.

    Density is not a free field: it is always `0.28 + 0.62 * energy`,
    computed fresh on every call, so "C hits hardest" and "K is a comedown"
    can't be edited out of agreement with each other by touching only one of
    several redundant knobs.
    """
    key = (letter or "").strip().upper()[:1]
    if key not in ARC:
        key = ROLE_LETTER.get((role or "").strip().lower(), "")
    row = dict(ARC.get(key) or _ARC_DEFAULT)
    row["letter"] = key or "A"
    row["density"] = round(0.28 + 0.62 * row["energy"], 4)
    return row
