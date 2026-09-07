# TASKS

Work only `## Next`. One checkbox per session. Paste pytest before flipping to DONE.
P1+ : open `SCOPE-INDEX.md`, then only those headings in `god-tier-metal-scope.md`.

## Next
1. [ ] P4.4 Mine reference MIDI packs for drum-fill vocabulary (§18.6)
2. [ ] P6.1 Weighted section graph
3. [ ] P6.2 flatten+pickup
4. [ ] P6.3 Half-time inside a section
5. [ ] P6.4 Modulation called from generation
6. [ ] P6.5 Judge/retry
7. [ ] P6.6 Tech/atmospheric interlude section type
8. [ ] P6.7 Tempo curve: mid-song ramps/drops

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
- [ ] P1.7 Preset ids: groovy, djent, chill, tech, slam, melodic. Strict JSON
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
- [ ] P4.4 Mine `reference/ww-forge-prior-attempt/user/midi/{whack_breakdown,jj_lakeside,jj_lamb,jj_dreaming,forge_grooves}` (63 real, legally-clean groove/breakdown MIDIs) for drum-fill density/placement vocabulary per §18.6 -- reference data only, never copied riffs; the symbolic engine (P4.1-P4.3) stays the actual writer. Queued after P4.1-P4.3 land to avoid touching drums.py while it's mid-build.

## Phase 5 — Bass
Scope: `### 14.2` (item 2, bass fretboard).
- [x] P5.1 Own 4/5-string fretboard
- [x] P5.2 Follows guitar rhythm; own playability

## Phase 6 — Structure
Scope: `## 5. Song-structure` + `### 10.3` + `## 3. Rhythm` (tempo-automation paragraph, P6.7 only).
- [ ] P6.1 Weighted section graph
- [ ] P6.2 flatten+pickup
- [ ] P6.3 Half-time inside a section
- [ ] P6.4 Modulation called from generation
- [ ] P6.5 Judge/retry
- [ ] P6.6 Tech/atmospheric interlude section type -- "not present at all currently" per §5
- [ ] P6.7 Tempo curve: mid-song ramps/drops per §3. Reaper export still uses one constant tempo (§17.5) -- this is an internal song-data property, not a Reaper tempo-map change

## Phase 7 — Atmosphere
Scope: `## 16. Atmospheric`.
- [ ] P7.1 GM 90 pad / 56 hit
- [ ] P7.2 Synth doubles motif
- [ ] P7.3 Accent-synced hits

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
