# TASKS

Work only `## Next`. One checkbox per session. Paste pytest before flipping to DONE.
P1+ : open `SCOPE-INDEX.md`, then only those headings in `god-tier-metal-scope.md`.

## Next
(X.1-X.7 done. P10.1 (real MIDI export) done. Reaper + Tone3000 confirmed installed on this machine -- Phase 8 (reapy-boost) is now realistically buildable+testable, not blind. Remaining: P10.2 Song JSON, P10.3 preset calibration against the real analyzed reference track, Phase 8 Reaper wiring, Phase 9 editor UI (React/Vite/Tailwind/shadcn/Framer Motion -- see PROGRESS.md).)

---

## Cross-cutting (spans multiple phases, not one Phase N)
- [x] X.1 `engine/song.py` `compose_song(preset_id, seed)` -- full pipeline integration. Gap found on review: every phase (1-7) built and tested its own mechanism in isolation; nothing had ever taken a real `Preset` and threaded it through a real end-to-end generation run (rhythm guitar x2 double-tracked, lead, bass, drums+fills, atmosphere, judge/retry). `engine/tests/test_song.py` verifies this for every real preset -- passed first try, confirming the independently-built phases actually compose.
- [x] X.2 Consume remaining preset fields. `drums.kick_pattern_for_style` dispatches on the real style values found in the preset JSON files (bounce/lock -> exact guitar-lock; sparse -> every-other-hit; euclid -> genuine Bjorklund-equivalent even distribution, pulse count from the guitar's own hit count; two_step -> documented metalcore breakdown interpretation (kick at beat-offsets 0.0/1.5 per 2-beat cycle); blast -> every cell). `motif.generate_motif` gained `group_beats` (tiles a short cell via `rhythm.tile_cell` for djent's N-against-4 displacement) and `pedal` (via new `apply_pedal_bias`, biases delta selection toward the root proportional to `preset.pedal`). `preset.octave_stab` now adds real `VoiceLeader.stab()` leaps at accent positions when true, empty list when false. All wired into `song.py`'s real `compose_song` call path; tested with A/B comparisons on the real `djent` preset (`dataclasses.replace` to flip one field, identical seed on both sides) proving each field measurably changes output, not just RNG noise.
- [x] X.3 Wire `motif.ThemeRegistry` (P3.4) into `compose_song` -- it existed but had no caller; sections sharing a role now develop one recurring theme (rendered at each section's own arc-driven degree, `invert`-ed on alternate reuses) instead of an independently-rolled motif per section. Fixing this surfaced a real bug (`invert` can push a pitch below the guitar's lowest string) -- added `_snap_to_playable_octave`, same discipline `bass.py` already uses.
- [x] X.4 Fix `compose_song`'s dead `seed` parameter -- it called `structure.judge_and_retry`, which always tries its own `range(max_seeds)` internally, so every call silently collapsed onto whichever of seeds 0-5 judged first regardless of the caller's seed. Replaced with a local retry loop seeded `seed, seed+1, ...`.
- [x] X.5 Realistic per-role lead-guitar behavior -- was generating an active melodic line in every section all song long. Now: `solo` = dense featured line (register pushed up, more leaps), `chill`/`interlude` = harmonized doubling of the rhythm's own theme (`riff.harmonize_line`), everything else = silent (a busy independent lead would clash with a dense chug section).
- [x] X.6 Periphery-level musicianship goal (see CLAUDE.md Bar) -- three genuinely new capabilities, not just unwired data:
  - [x] X.6a Legato/technical run generator -- `engine/legato.py`: `generate_legato_run` (contiguous scale-degree walk via `scale.step`, structurally distinct from VoiceLeader's weighted-pick model; optional single mid-run direction reversal when seeded), `legato_run_rhythm` (fast even subdivisions, genuine tuplets via `rhythm.tuplet_grid` when the length fits 3/5/7), `fret_positions_for_run` (single-string-biased via `Fretboard.pitch_to_fret`'s `prev` chaining -- real hammer-on/pull-off technique stays on one string). Wired into `song.py`: every solo section splices a real legato lick onto its featured lead line (`section["legato"]`), fails closed (skips the splice) rather than fabricating a position if genuinely unplayable on that preset's tuning.
  - [x] X.6b Extended/altered chord vocabulary -- `engine/chord_vocab.py`: `CHORD_QUALITIES` (maj7/min7/dom7/sus2/sus4/add9/maj9/min9/six9, semitone-offset tuples matching `scales.py`'s `SCALES` convention), `get_chord_quality` (raises `ValueError` on unknown name, never fabricates), `voice_named_chord` (reuses `riff.voice_chord_section` -> `chords.solve_chord` for real fingering, no reimplemented solver), `quality_for_dissonance` (buckets a section's real `arc_row["dissonance"]` across `DISSONANCE_ORDER`, low->open/consonant, high->darker). Wired into `song.py`'s `chill`/`interlude` (`lead_mode == "harmony"`) branch as `section["chord_quality"]`/`section["chord_voicing"]`, alongside (not instead of) the existing `riff.harmonize_line` doubling; every other role leaves both `None`. Fails closed to `None` on a genuinely unreachable voicing rather than a fabricated shape. `engine/tests/test_chord_vocab.py`: every quality reachable on a real loaded tuning, unknown-quality/unreachable-chord rejection, monotonic dissonance bucketing, and an end-to-end `compose_song` check exercising both a real reachable voicing and a real unreachable one.
  - [x] X.6c Metric modulation as a compositional device (the pulse itself reinterpreting, e.g. a dotted-eighth becoming the new quarter) -- a step beyond the existing `tile_cell`/`metric_polyrhythm` (which stay within one fixed pulse). `engine/metric_modulation.py`: `modulation_ratio(old_subdivision, new_subdivision)` (subdivision = `(numerator, denominator)`, ratio = `value(old)/value(new)`; verified against the textbook dotted-quarter=new-quarter case, ratio 1.5) and `apply_metric_modulation(base_bpm, ratio)`; both fail closed on non-positive/malformed inputs. Wired a real `"metric_modulation"` branch into `structure.tempo_at`'s existing curve dispatch (alongside `"drop"`/`"ramp"`, same pattern). `song.py` fires a real trigger on the first `build`->`breakdown` transition in the generated sequence (straight eighth of the old pulse becomes the new quarter -- ratio 0.5, the genre's half-time breakdown treatment), producing `song["tempo_map"]` (one BPM per section, computed via `tempo_at` for every composed song, defaulting to flat `preset.bpm` when no transition occurs). `engine/tests/test_metric_modulation.py`, plus extensions to `test_structure.py`/`test_song.py` (including a direct `generate_section_sequence` seed search to guarantee a real build->breakdown transition exists before checking its tempo_map effect).
  - [x] X.6d Major-family scales (lydian, mixolydian, major/ionian, harmonic major) -- added to `scales.py` (`major`/`ionian` alias, `lydian`, `mixolydian`, `harmonic_major`). No existing preset was switched to use them yet (would need careful vocab-weight redesign, not a drop-in swap, since weights are semitone-interval based and snap onto whichever scale is active) -- the capability now exists, adopting it into a preset is a deliberate follow-up.
- [x] X.8 Wire `preset.feel` (was validated at load time, never consumed by generation -- same class of gap as X.2's kick/group/pedal/octave_stab). Investigated the real reference implementation ("Metalerator", `reference/metalerator/` -- confirmed via its own README to be a real, dedicated metalcore generator, not a generic engine with metalcore bolted on) for what a genuinely portable, non-invented `feel`-driven technique looks like: its breakdown generator (`rhythm_guitar/breakdown/default_melodic.py`) draws durations from a real weighted table (biased toward 8th/quarter chugging over rapid 16ths) and enforces "no isolated single 16th note" (pairs them). Ported both, adapted to this engine's duration vocabulary (half notes dropped, ratio preserved): `rhythm.FEEL_DURATION_WEIGHTS`/`FEEL_NO_SINGULAR_SHORT`/`duration_bias_for_feel`, new opt-in `weights`/`no_singular_short` params on `rhythm.generate_rhythm` (default `None` = byte-identical old uniform behavior, verified by test), threaded through `motif.generate_motif`/`ThemeRegistry.get_or_create` and wired at `song.py`'s `preset.feel` call site. Only `"breakdown"` (metalcore's real feel) has ported reference data; other feel names stay uniform rather than inventing weight tables with no real source, per this project's own "port, don't invent" discipline. `engine/tests/test_rhythm.py`: weights=None is byte-identical to pre-existing behavior (zero regression risk), the real breakdown weights measurably shift the duration distribution, the no-singular-short rule eliminates every isolated occurrence across 50 seeds, bad-input rejection (all-zero-weight). `engine/tests/test_song.py`: a real A/B compose_song comparison (metalcore vs. the same preset with an unmapped feel) proves the 16th-note share measurably drops in real generated output, not just in rhythm.py isolation. 450 passed in 10.76s.
- [x] X.9 Real snare backbeat, wired for every preset -- closes a real, previously-unaddressed gap: this engine had a kick (P4.2/X.2) and blast/fill patterns (P4.3) but NO snare/hihat layer at all. Ported from the same real reference implementation as X.8 (`reference/metalerator/metalerator/drums/snare/snare.py`, `Snare.snare_step`/`snare_half_step`/`snare_double_time`): `"step"` is a half-time hit on beat 3 of every bar (checked the real source rather than assuming the generic "2 and 4"), `"half_step"` once per 2-bar cycle, `"double_time"` every beat except the section's first. Built on the same real cell-timeline mechanism `_kick_two_step` already used (`_cell_starts`/`_time_to_cell_index`/`_cyclic_hit_indices`, extracted as shared helpers -- `_kick_two_step` itself refactored onto them, no duplicated logic). Wired for EVERY preset via a real per-ROLE dispatch (`drums.snare_pattern_for_role`, `song.py`'s `section["snare"]`), not gated to one genre -- breakdown/intro/outro get the half-time backbeat, build/solo get the denser double_time, chill/interlude stay silent (same judgment call `lead_mode` already makes for those roles). Wired into `midi_export.py`'s Drums track alongside the kick (real GM notes 36/38, standard single-drum-track convention). Ghost notes (Metalerator's quiet grace-note hits around the main snare) documented as a real, deliberately deferred follow-up -- don't fit the fixed-cell-array model without a larger rework. `engine/tests/test_drums.py`: exact hit-position checks for all three styles against a hand-built cell grid (not trusting the mechanism blindly), role-dispatch table coverage, bad-input rejection. `engine/tests/test_song.py`: every real preset gets a real snare layer with chill/interlude silent. `engine/tests/test_midi_export.py`: real GM kick(36)/snare(38) note counts cross-checked against actual generated song data. 464 passed in 10.96s.
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
- [x] P8.1 (superseded) Real Reaper project generation -- `engine/reaper_project.py`: `song_to_rpp(song, path)` writes a complete, directly-openable `.rpp` project file entirely offline, no live Reaper connection at any point. Investigated the scope doc's originally-chosen `reapy`/`reapy-boost` live-bridge approach first: got real, substantial progress (installed reapy-boost, MIT-licensed; automated the ENTIRE one-time bridge setup headlessly via config-file editing + HTTP-triggering Reaper's own built-in web control surface, no GUI clicks needed; found and fixed two real upstream bugs -- a socket-timeout bug causing `WinError 10053` on the first `send()` after `accept()`, and the activation script's `if __name__ == "__main__":` guard never firing under Reaper's script-execution model) but the connection remained unreliable in this environment even after both fixes, with no way to get further diagnostic visibility. Verified directly with the user that nothing Phase 8 actually needs requires a live connection: real REAPER project assembly, FX chains, and tempo automation are all expressible as a static file, and REAPER has a real, documented headless render flag (`-renderproject file.rpp`, confirmed via ReaTeam/Doc's REAPER-CLI.md) for the render step. Pivoted to `.rpp` generation, built against REAL ground truth rather than a guessed format: had REAPER itself (v7.79, already installed) import this project's own `midi_export.song_to_midi` output and save as `.rpp`, then reverse-engineered every field from that real file -- including base64-decoding the `<X>` track-name block to confirm it's the exact standard MIDI `0xFF 0x03 <name>` meta-event, not assumed. Reuses `midi_export`'s real event-extraction functions (one source of truth for per-track note/timing data, two serializers on top). **Verified end-to-end for real**: generated a project, had the user's actual installed Reaper open it, confirmed via screenshot -- 5 correctly-named tracks, real visible note content in every track, correct tempo, no error dialog. `engine/tests/test_reaper_project.py`: structural bracket-balance check across every real preset, the `<X>` block's base64 decoded and checked against the real MIDI meta-event format, guitar/drum note counts cross-checked against actual generated song data, real tempo-envelope values checked against `tempo_map`, reproducibility (same song -> same content, GUIDs excluded), bad-input rejection. 477 passed.
- [ ] P8.2 Separate buses (tracks already separate per-instrument; bus/send routing not yet added)
- [ ] P8.3 .RfxChain per track -- needs a small hand-built library of real FX-chain presets (NAM captures + cab IR, dialed in once by the user in Reaper's own GUI, per the scope doc's own §11.5 design) to splice into the generated `.rpp`; the splice mechanism itself is straightforward once real `.RfxChain` files exist
- [ ] P8.4 sfizz + role map
- [ ] P8.5 Surge + Supermassive
- [ ] P8.6 Orchestra
- [ ] P8.7 Adaptive mix -- real per-section automation envelopes, bakeable into the `.rpp` directly (no live connection needed) once a concrete automation target is scoped
- [ ] P8.8 Constant tempo map (already true: the generated `.rpp`'s `TEMPO`/`TEMPOENVEX` fields are the ONLY tempo data Reaper sees, per scope sec.17.5 -- nothing further needed here)

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
- [x] P10.1 MIDI stems (real, playable, Reaper-importable) -- `engine/midi_export.py`: `song_to_midi(song, path, ppq=480)` writes a real Standard MIDI File (type 1) with a genuine per-section tempo track (X.6c's `tempo_map`, not flat), guitar take A/B, bass (its own fretboard's real positions), lead (harmony-mode notes timed hit-for-hit against the rhythm motif's own cells; solo-mode notes timed at the exact even 8th-note spacing `song.py`'s own note-count math implies, plus the legato tail's real per-note durations), and drums (the kick pattern actually assembled into the song, via `drums.note_for_role` for the real GM note number). Deliberately does NOT invent a fill/kick blend, since `song.py` itself never blends `section["fill"]` into the assembled drum track -- exporting one would be new arrangement logic, not wiring. `engine/tests/test_midi_export.py`: every real preset round-trips to a parseable file; guitar/bass pitches and hit counts cross-checked against the actual `pitches_per_cell`/bass-cell data (not just "a file was written"); tempo track values checked against real `tempo_map`; drum notes checked against the real GM kick value; solo-section note count checked against real `lead` data; bad-input rejection (non-positive ppq, mismatched tempo_map/sections length). .RPP project-file generation and mix/tab export remain open (mix audio and tab notation need real Reaper/VexFlow work respectively -- tracked separately, not folded into this box).
- [ ] P10.2 Song JSON
- [ ] P10.3 Preset calibration

## Deferred
Vocals. Extra ML. Playability beyond pitch_to_fret.
