# TASKS

Work only `## Next`. One checkbox per session. Paste pytest before flipping to DONE.
P1+ : open `SCOPE-INDEX.md`, then only those headings in `god-tier-metal-scope.md`.

## Next
(X.2 and X.6a both done. See PROGRESS.md for what's next: X.6b extended chords, X.6c metric modulation, or Phase 8/9/10.)

---

## Cross-cutting (spans multiple phases, not one Phase N)
- [x] X.1 `engine/song.py` `compose_song(preset_id, seed)` -- full pipeline integration. Gap found on review: every phase (1-7) built and tested its own mechanism in isolation; nothing had ever taken a real `Preset` and threaded it through a real end-to-end generation run (rhythm guitar x2 double-tracked, lead, bass, drums+fills, atmosphere, judge/retry). `engine/tests/test_song.py` verifies this for every real preset -- passed first try, confirming the independently-built phases actually compose.
- [x] X.2 Consume remaining preset fields. `drums.kick_pattern_for_style` dispatches on the real style values found in the preset JSON files (bounce/lock -> exact guitar-lock; sparse -> every-other-hit; euclid -> genuine Bjorklund-equivalent even distribution, pulse count from the guitar's own hit count; two_step -> documented metalcore breakdown interpretation (kick at beat-offsets 0.0/1.5 per 2-beat cycle); blast -> every cell). `motif.generate_motif` gained `group_beats` (tiles a short cell via `rhythm.tile_cell` for djent's N-against-4 displacement) and `pedal` (via new `apply_pedal_bias`, biases delta selection toward the root proportional to `preset.pedal`). `preset.octave_stab` now adds real `VoiceLeader.stab()` leaps at accent positions when true, empty list when false. All wired into `song.py`'s real `compose_song` call path; tested with A/B comparisons on the real `djent` preset (`dataclasses.replace` to flip one field, identical seed on both sides) proving each field measurably changes output, not just RNG noise.
- [x] X.3 Wire `motif.ThemeRegistry` (P3.4) into `compose_song` -- it existed but had no caller; sections sharing a role now develop one recurring theme (rendered at each section's own arc-driven degree, `invert`-ed on alternate reuses) instead of an independently-rolled motif per section. Fixing this surfaced a real bug (`invert` can push a pitch below the guitar's lowest string) -- added `_snap_to_playable_octave`, same discipline `bass.py` already uses.
- [x] X.4 Fix `compose_song`'s dead `seed` parameter -- it called `structure.judge_and_retry`, which always tries its own `range(max_seeds)` internally, so every call silently collapsed onto whichever of seeds 0-5 judged first regardless of the caller's seed. Replaced with a local retry loop seeded `seed, seed+1, ...`.
- [x] X.5 Realistic per-role lead-guitar behavior -- was generating an active melodic line in every section all song long. Now: `solo` = dense featured line (register pushed up, more leaps), `chill`/`interlude` = harmonized doubling of the rhythm's own theme (`riff.harmonize_line`), everything else = silent (a busy independent lead would clash with a dense chug section).
- [ ] X.6 Periphery-level musicianship goal (see CLAUDE.md Bar) -- three genuinely new capabilities, not just unwired data:
  - [x] X.6a Legato/technical run generator -- `engine/legato.py`: `generate_legato_run` (contiguous scale-degree walk via `scale.step`, structurally distinct from VoiceLeader's weighted-pick model; optional single mid-run direction reversal when seeded), `legato_run_rhythm` (fast even subdivisions, genuine tuplets via `rhythm.tuplet_grid` when the length fits 3/5/7), `fret_positions_for_run` (single-string-biased via `Fretboard.pitch_to_fret`'s `prev` chaining -- real hammer-on/pull-off technique stays on one string). Wired into `song.py`: every solo section splices a real legato lick onto its featured lead line (`section["legato"]`), fails closed (skips the splice) rather than fabricating a position if genuinely unplayable on that preset's tuning.
  - [ ] X.6b Extended/altered chord vocabulary -- `chords.py`'s solver only enumerates power-chord-style triads; ambient/clean sections need 9th/11th/add-tone voicings.
  - [ ] X.6c Metric modulation as a compositional device (the pulse itself reinterpreting, e.g. a dotted-eighth becoming the new quarter) -- a step beyond the existing `tile_cell`/`metric_polyrhythm` (which stay within one fixed pulse).
  - [x] X.6d Major-family scales (lydian, mixolydian, major/ionian, harmonic major) -- added to `scales.py` (`major`/`ionian` alias, `lydian`, `mixolydian`, `harmonic_major`). No existing preset was switched to use them yet (would need careful vocab-weight redesign, not a drop-in swap, since weights are semitone-interval based and snap onto whichever scale is active) -- the capability now exists, adopting it into a preset is a deliberate follow-up.
- [x] X.7 `engine/audio_vocab.py` -- real-audio structural/tonal vocabulary, the audio analogue of `midi_vocab.py`'s MIDI mining. Tempo, harmonic/percussive rhythm-density split, spectral-centroid brightness descriptor, per-section relative density curve, key/tonal-center estimate (Krumhansl-Schmuckler correlation), real structural segmentation (MFCC self-similarity, not equal slices), tempo-stability check, drum-onset role classification (KICK/SNARE/HIHAT_OR_CYMBAL by frequency band), and guitar-rhythm-pattern detection (straight/gallop/syncopated from onset timing alone, never pitch). Never transcribes notes/chords, only extracts numeric statistics -- same "reference data, not composer" boundary as the MIDI vocabulary. Optional local `demucs` pre-processing (`pip install demucs`, MIT-licensed, run locally -- never upload audio to a third-party "online demucs" site) gives real per-instrument stems. Validated against a real user-supplied track (a friend's original song): found the guitar/bass has more section-to-section dynamic range than the drums (validates `theory.arc()`'s design), the track sits in A MAJOR (a real data point that the scale library's lack of major-family modes, X.6b-adjacent, is a real gap), and the drum-role classifier's own output (implausibly few detected snares) honestly demonstrates a real ceiling -- a hand-built frequency-band heuristic isn't reliable on a dense, cymbal-heavy mix; a proper trained drum-transcription model would be needed to do better, not just more analysis code. Also added `transcribe_and_split_registers` (optional, needs `basic_pitch` -- not in requirements.txt, its own dependency pins are fragile on newer Python, install ad hoc): real polyphonic audio-to-note transcription split into rhythm-register vs lead-register layers by pitch. Cross-validated on the real track: the rhythm layer's dominant transcribed pitch class (A) independently matched `estimate_key`'s separate chroma-based key estimate (also A) -- two unrelated methods agreeing is real evidence, not proof, that this is picking up something true.

---

## Phase 0 — Repo
- [x] P0.1 folders
- [x] P0.2 assets present
- [x] P0.3 pytest smoke
- [x] P0.4 gitignore / commit
- [x] P0.5 STATUS template

## Phase 1 — Tonal + presets
Scope: `## 2. Tonal/Harmonic` + `### 18.2` + `### 12.3` (chord-shape solver). Then `PORTS.md` Ww.
- [x] P1.1 `Fretboard` + MIDI↔(string,fret)
- [x] P1.2 Port `pitch_to_fret` from `reference/ww-forge-prior-attempt/engine/tab_score.py`
- [x] P1.3 TEST: unplayable MIDI rejected
- [x] P1.4 Scale library + cluster + power. Unique intervals
- [x] P1.5 TEST: no duplicate non-alias scales
- [ ] P1.6 Tuning JSON from source MIDI
- [x] P1.7 Preset ids: groovy, djent, chill, tech, melodic, metalcore, deathcore (`slam` removed per user direction -- targets djent/deathcore/metalcore/technical deathcore, not slam). Strict JSON
- [ ] P1.8 Schema validator called by loader. TEST malformed raises
- [ ] P1.9 TEST glob `*.json` loads every file
- [ ] P1.10 Port VoiceLeader, shade(), ARC
- [ ] P1.11 Chord-shape solver (ground-up, no lookup tables)

## Phase 2 — Rhythm
Scope: `## 3. Rhythm` + `### 8.1` `### 8.2` `### 8.3`.
- [x] P2.1 Two-layer `{duration, is_rest}` then pitch
- [x] P2.2 Cell-tile polymeter + TEST 7 into 16 drifts
- [x] P2.3 Separate `metric_polyrhythm()` + TEST ≠ tile
- [x] P2.4 Real tuplet grids 3/5/7
- [x] P2.5 Blasts traditional/gravity/hammer; zero weight = never
- [x] P2.6 Shared rhythm id
- [x] P2.7 IRVD
- [x] P2.8 Seeded RNG + identical bytes twice

## Phase 3 — Motif / riff
Scope: `## 4. Riff-writing` + `### 17.1` + `## 6. New instrument layer` (P3.12 only).
- [x] P3.1 Motif = rhythm_cell + pitch deltas
- [x] P3.2 TEST same shape two roots
- [x] P3.3 Develop ops; lengths stay paired
- [x] P3.4 Cross-section theme id reused
- [x] P3.5 Gallop / stutter-chug change output
- [x] P3.6 Chromatic flags change output
- [x] P3.7 VoiceLeader leads
- [x] P3.8 Double-track two humanized takes
- [x] P3.9 Call-and-response: guitar reacts to drums/lead, not generated in isolation (§4)
- [x] P3.10 Slam devices: pinch-harmonic accent sim, low open-string chromatic creep (§4)
- [x] P3.11 Wire chord-shape solver (P1.11) into the pitch layer for chord-voiced sections -- a solver nobody calls is not done
- [x] P3.12 (optional, scope hedges with "possibly") second rhythm guitar harmonizing/doubling the lead (§6)

## Phase 4 — Drums
Scope: `### 11.6` `### 11.7`.
- [x] P4.1 Role → kit MIDI + fallback
- [x] P4.2 Kick follows guitar accents on breakdown
- [x] P4.3 Fills/blasts use shared-sequence
- [x] P4.4 Mine `reference/midi-corpus/` (1967 real, legally-clean groove/breakdown MIDIs, user-supplied superset of the original 63-file sample) for drum-fill density/placement vocabulary per §18.6 -- reference data only, never copied riffs; the symbolic engine (P4.1-P4.3) stays the actual writer. Queued after P4.1-P4.3 land to avoid touching drums.py while it's mid-build.

## Phase 5 — Bass
Scope: `### 14.2` (item 2, bass fretboard).
- [x] P5.1 Own 4/5-string fretboard
- [x] P5.2 Follows guitar rhythm; own playability

## Phase 6 — Structure
Scope: `## 5. Song-structure` + `### 10.3` + `## 3. Rhythm` (tempo-automation paragraph, P6.7 only).
- [x] P6.1 Weighted section graph
- [x] P6.2 flatten+pickup
- [x] P6.3 Half-time inside a section
- [x] P6.4 Modulation called from generation
- [x] P6.5 Judge/retry
- [x] P6.6 Tech/atmospheric interlude section type -- "not present at all currently" per §5
- [x] P6.7 Tempo curve: mid-song ramps/drops per §3. Reaper export still uses one constant tempo (§17.5) -- this is an internal song-data property, not a Reaper tempo-map change

## Phase 7 — Atmosphere
Scope: `## 16. Atmospheric`.
- [x] P7.1 GM 90 pad / 56 hit
- [x] P7.2 Synth doubles motif
- [x] P7.3 Accent-synced hits

## Phase 8 — Reaper
Scope: `## 11. Audio rendering` + `### 14.1` (reapy-boost, Surge XT, Supermassive).
- [ ] P8.1 reapy-boost
- [ ] P8.2 Separate buses
- [ ] P8.3 .RfxChain per track
- [ ] P8.4 sfizz + role map
- [ ] P8.5 Surge + Supermassive
- [ ] P8.6 Orchestra
- [ ] P8.7 Adaptive mix
- [ ] P8.8 Constant tempo map

## Phase 9 — Editor
Scope: `## 10. Application / Editor`.
- [ ] P9.1 Timeline CRUD
- [ ] P9.2 Pro + Guided
- [ ] P9.3 Regen primitives
- [ ] P9.4 Accept/reroll/undo
- [ ] P9.5 Preview vs Render
- [ ] P9.6 VexFlow tab
- [ ] P9.7 Section-level save/load presets, distinct from song-level style presets (§10.2)

## Phase 10 — Export
Scope: `### 17.6` + `### 14.2` (items 10-11, project format + export matrix). JSON skeleton already in `### 18.2`.
- [ ] P10.1 MIDI stems, mix, tab, .rpp
- [ ] P10.2 Song JSON
- [ ] P10.3 Preset calibration

## Deferred
Vocals. Extra ML. Playability beyond pitch_to_fret.
