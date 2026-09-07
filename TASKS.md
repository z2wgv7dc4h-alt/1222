# TASKS

Work only `## Next`. One checkbox per session. Paste pytest before flipping to DONE.
P1+ : open `SCOPE-INDEX.md`, then only those headings in `god-tier-metal-scope.md`.

## Next
1. [x] P0.1 Create folders: `engine/`, `engine/tests/`, `editor/`, `docs/`, `reference/`, `assets/drums/`, `assets/nam/`
2. [x] P0.2 Confirm `assets/drums/` has `.sfz` and `assets/nam/` has `.nam`. If missing, copy from the reference bundle. Stop if empty.
3. [x] P0.3 `engine/pyproject.toml` or `engine/requirements.txt` + pytest. `engine/tests/test_smoke.py` asserts `True`. `python -m pytest -q` passes.
4. [x] P0.4 Confirm `.gitignore` from the kit is present. First commit of docs + kit. No `assets/`, no `reference/`.
5. [x] P0.5 Confirm `docs/STATUS.md` template. No Working claims.

---

## Phase 0 — Repo
- [ ] P0.1 folders
- [ ] P0.2 assets present
- [ ] P0.3 pytest smoke
- [ ] P0.4 gitignore / commit
- [ ] P0.5 STATUS template

## Phase 1 — Tonal + presets
Scope: `## 2. Tonal/Harmonic` + `### 18.2`. Then `PORTS.md` Ww.
- [ ] P1.1 `Fretboard` + MIDI↔(string,fret)
- [ ] P1.2 Port `pitch_to_fret` from `reference/ww-forge-prior-attempt/engine/tab_score.py`
- [ ] P1.3 TEST: unplayable MIDI rejected
- [ ] P1.4 Scale library + cluster + power. Unique intervals
- [ ] P1.5 TEST: no duplicate non-alias scales
- [ ] P1.6 Tuning JSON from source MIDI
- [ ] P1.7 Preset ids: groovy, djent, chill, tech, slam, melodic. Strict JSON
- [ ] P1.8 Schema validator called by loader. TEST malformed raises
- [ ] P1.9 TEST glob `*.json` loads every file
- [ ] P1.10 Port VoiceLeader, shade(), ARC

## Phase 2 — Rhythm
Scope: `## 3. Rhythm` + `### 8.1` `### 8.2` `### 8.3`.
- [ ] P2.1 Two-layer `{duration, is_rest}` then pitch
- [ ] P2.2 Cell-tile polymeter + TEST 7 into 16 drifts
- [ ] P2.3 Separate `metric_polyrhythm()` + TEST ≠ tile
- [ ] P2.4 Real tuplet grids 3/5/7
- [ ] P2.5 Blasts traditional/gravity/hammer; zero weight = never
- [ ] P2.6 Shared rhythm id
- [ ] P2.7 IRVD
- [ ] P2.8 Seeded RNG + identical bytes twice

## Phase 3 — Motif / riff
Scope: `## 4. Riff-writing` + `### 17.1`.
- [ ] P3.1 Motif = rhythm_cell + pitch deltas
- [ ] P3.2 TEST same shape two roots
- [ ] P3.3 Develop ops; lengths stay paired
- [ ] P3.4 Cross-section theme id reused
- [ ] P3.5 Gallop / stutter-chug change output
- [ ] P3.6 Chromatic flags change output
- [ ] P3.7 VoiceLeader leads
- [ ] P3.8 Double-track two humanized takes

## Phase 4 — Drums
Scope: `### 11.6` `### 11.7`.
- [ ] P4.1 Role → kit MIDI + fallback
- [ ] P4.2 Kick follows guitar accents on breakdown
- [ ] P4.3 Fills/blasts use shared-sequence

## Phase 5 — Bass
Scope: `## 6. New instrument layer`.
- [ ] P5.1 Own 4/5-string fretboard
- [ ] P5.2 Follows guitar rhythm; own playability

## Phase 6 — Structure
Scope: `## 5. Song-structure` + `### 10.3`.
- [ ] P6.1 Weighted section graph
- [ ] P6.2 flatten+pickup
- [ ] P6.3 Half-time inside a section
- [ ] P6.4 Modulation called from generation
- [ ] P6.5 Judge/retry

## Phase 7 — Atmosphere
Scope: `## 16. Atmospheric`.
- [ ] P7.1 GM 90 pad / 56 hit
- [ ] P7.2 Synth doubles motif
- [ ] P7.3 Accent-synced hits

## Phase 8 — Reaper
Scope: `## 11. Audio rendering`.
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

## Phase 10 — Export
Scope: `### 17.6`.
- [ ] P10.1 MIDI stems, mix, tab, .rpp
- [ ] P10.2 Song JSON
- [ ] P10.3 Preset calibration

## Deferred
Vocals. Extra ML. Playability beyond pitch_to_fret.
