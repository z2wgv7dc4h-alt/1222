# STATUS

Listen is not a row you may tick from pytest.

- labyrinth seed-1 demo: user rejected (medley / GM). 2026-09-12
- bank wired + ThemeRegistry.seed: WIRED+TESTED (803 engine)
- P8.2-P8.8: MISSING

Wiring table below is historical pytest evidence. Counts differ by day. Do not treat a higher count as a better song.


Legend: MISSING | SCAFFOLD | WIRED+TESTED

Update only after grep or pytest. No memory claims.

| Area | State | Evidence |
|---|---|---|
| Repo layout | WIRED+TESTED | 159 passed in 0.24s (incl. test_repo_structure.py) |
| pytest smoke | WIRED+TESTED | 1 passed in 0.01s |
| Fretboard + pitch_to_fret | WIRED+TESTED | 159 passed (full suite) |
| Scale library | WIRED+TESTED | 159 passed (full suite) |
| Preset loader+schema (P1.6-P1.9) | WIRED+TESTED | 159 passed (full suite) |
| VoiceLeader/shade/ARC (P1.10) | WIRED+TESTED | 159 passed (full suite) |
| Chord-shape solver (P1.11) | WIRED+TESTED | 159 passed (full suite) |
| Rhythm two-layer + polymeter/tuplets/blasts/IRVD (Phase 2) | WIRED+TESTED | 159 passed (full suite) |
| Motif (P3.1-P3.12, incl. optional P3.12) | WIRED+TESTED | 236 passed in 0.50s |
| Drums + MIDI-vocab mining (P4.1-P4.4) | WIRED+TESTED | 256 passed in 4.48s |
| Bass | WIRED+TESTED | 189 passed in 0.30s |
| Structure (P6.1-P6.7) | WIRED+TESTED | 287 passed in 2.33s |
| Atmosphere (P7.1-P7.3) | WIRED+TESTED | 302 passed in 2.28s |
| Full pipeline integration (song.py), incl. ThemeRegistry + realistic lead behavior | WIRED+TESTED | 314 passed in 2.39s |
| Real-audio structural/tonal/drum-role/transcription analysis (audio_vocab.py) | WIRED+TESTED | 335 passed in 12.93s |
| Major-family scales (major/lydian/mixolydian/harmonic_major) | WIRED+TESTED | 335 passed in 10.42s |
| Preset kick/group/pedal/octave_stab wiring (X.2) | WIRED+TESTED | 382 passed in 10.24s |
| Legato/technical run generator (X.6a) | WIRED+TESTED | 382 passed in 10.24s |
| Extended chord vocabulary, chill/interlude sections (X.6b) | WIRED+TESTED | 428 passed in 12.19s |
| Metric modulation, real tempo_map (X.6c) | WIRED+TESTED | 428 passed in 12.19s |
| Preset lineup: djent/tech/metalcore/deathcore/melodic/chill/groovy/progressive (no slam) | WIRED+TESTED | 482 passed in 13.03s |
| Real MIDI export, Reaper-importable (P10.1) | WIRED+TESTED | 443 passed in 11.19s |
| preset.feel wiring, real ported breakdown duration-weighting (X.8) | WIRED+TESTED | 450 passed in 10.76s |
| Snare backbeat, wired for every preset (X.9) | WIRED+TESTED | 464 passed in 10.96s |
| Real Reaper .rpp project generation (P8.1) | WIRED+TESTED | 477 passed in 22.27s; verified opening in the user's real installed Reaper (screenshot confirmed) |
| Hihat/cymbal layer + varied kick overlay, wired for every preset (X.11) | WIRED+TESTED | 500 passed in 12.59s |
| Tempo-map half-time reversion fix (X.12) | WIRED+TESTED | 499 passed in 13.18s |
| Hihat variation: open-hat accents + transition crashes (X.13) | WIRED+TESTED | 504 passed, 1 skipped in 12.75s |
| Real 4-state theme-development rotation (X.14) | WIRED+TESTED | 506 passed, 1 skipped in 12.73s |
| Real triplet + chug feel generation (X.15) | WIRED+TESTED | 513 passed, 1 skipped in 13.52s |
| Real "bounce" density fix + minor-third vocab (X.16) | WIRED+TESTED | 515 passed, 1 skipped in 13.80s |
| Cross-preset audit + real "airy" feel for chill (X.17); doc/hook cleanup | WIRED+TESTED | 516 passed, 1 skipped in 13.47s |
| Real mid-section tempo/half-time drops (X.18) + scope gaps tracker | WIRED+TESTED | 520 passed, 1 skipped in 13.94s |
| Real IRVD phrase development, wired for the first time (X.19) | WIRED+TESTED | 525 passed, 1 skipped in 13.94s |
| Fixed severe density bug: open_chance was misapplied as hit_chance (X.20) | WIRED+TESTED | 528 passed, 1 skipped in 16.45s |
| Real open-string-vs-muted velocity articulation (X.21) | WIRED+TESTED | 533 passed, 1 skipped in 12.58s |
| Fixed kick never going silent for chill/interlude (X.22) | WIRED+TESTED | 535 passed, 1 skipped in 11.44s |
| Real power chords on the main rhythm guitar (X.23) | WIRED+TESTED | 539 passed, 1 skipped in 11.62s |
| Real cross-section blending -- guitar, bass, guitar-locking kick (X.24) | WIRED+TESTED | 550 passed, 1 skipped in 12.05s |
| Real kick "burst" device (X.25) | WIRED+TESTED | 553 passed, 1 skipped in 11.96s |
| Real pinch-harmonic accent, every preset (X.27; X.26 cancelled, see PORTS/TASKS) | WIRED+TESTED | 556 passed, 1 skipped in 12.14s |
| Fixed real cross-section blend desync bug -- guitar/bass/kick vs snare/hihat (X.28) | WIRED+TESTED | 560 passed, 1 skipped |
| Real verse/chorus structure-graph roles (X.29) | WIRED+TESTED | 562 passed, 1 skipped |
| Real per-bar tonal-center progression, verse/chorus (X.30) | WIRED+TESTED | 569 passed, 1 skipped |
| Real verse pedal bias, chorus power chords + chorus lead (X.31) | WIRED+TESTED | 572 passed, 1 skipped in 12.50s |
| Real gallop/stutter-chug + per-role feel system (X.32) | WIRED+TESTED | 579 passed, 1 skipped in 12.58s |
| Real song-pacing rebalance -- occasional half-time, less atmospheric filler (X.33) | WIRED+TESTED | 581 passed, 1 skipped in 12.86s |
| Real blast beats wired into the actual drum track (X.34) | WIRED+TESTED | 589 passed, 1 skipped in 13.77s |
| Real riff-repetition bias correction (X.35) + real melodic sequence generator for solos (X.36) | WIRED+TESTED | 596 passed, 1 skipped |
| Reaper full render pipeline (P8.2-P8.8: separate buses, FX-chain splice, sfizz drums, Surge/Supermassive, orchestra, adaptive mix) | MISSING | only P8.1 (.rpp project generation) is done -- see row above; P8.2-P8.8 all unchecked in TASKS.md |
| Atmosphere/synth pad + octave-stab EXPORT (distinct from generation) | WIRED+TESTED | engine/ 620 passed, 1 skipped (up from 613); real "Pad"/"Accents" MIDI+`.rpp` tracks, `MidiPlayer.tsx` real synth voices; verified live -- see TASKS.md tracker, 2026-09-10 |
| Synth-doubles-the-riff for dense-chug sections (`atmosphere.synth_double` wired into `song.py`, real "Synth" MIDI+`.rpp` track) | WIRED+TESTED | engine/ 627 passed, 1 skipped (up from 620); real demo song went from 3/10 to 10/10 sections with melodic content; verified live -- see TASKS.md tracker, 2026-09-10 |
| Real second guitar part -- pedal/chug doubler distinct from double-tracked `guitar_take_a`/`take_b` (`section["guitar_pedal"]`, calibrated against a real measured Born-of-Osiris reference MIDI, new "Guitar (Pedal)" MIDI+`.rpp` track) | WIRED+TESTED | engine/ 637 passed, 1 skipped (up from 627); real per-section root-heavy pedal content verified; verified live -- see TASKS.md's §17.1 tracker entry, 2026-09-10 |
| Real reference-corpus analysis + preset calibration (`engine/reference_vocab.py` -- MIDI/Guitar-Pro/audio input, real Krumhansl-Schmuckler key correlation, accumulating corpus cache, real preset-writing, real drum-role + rhythm-pattern capture, real separate lead-guitar vocab calibration, real corpus-derived Markov riff-pattern sequence model) | WIRED+TESTED | engine/ 699 passed, 1 skipped; real 31-song corpus (22 Born of Osiris + 6 Periphery + 3 Veil of Maya) -> `labyrinth.json` preset (139bpm, minor, pedal=0.95, real separate lead_vocab, real non-empty vocab.markov/lead_vocab.markov); `"boo"` alias updated; verified live -- see TASKS.md's §17.6 tracker entry, 2026-09-10/11 |
| Real corpus-derived Markov riff-pattern model (`theory._weighted_choice`/`pick_pitch_interval_markov`, `VoiceLeader.markov`, `motif.generate_pitch_deltas`/`generate_motif`/`ThemeRegistry`, `lead.generate_lead_line`/`generate_sequence_line`, `Preset.Vocab.markov`) -- sequence-aware pitch generation replacing independent marginal-frequency picks | WIRED+TESTED | engine/ 699 passed, 1 skipped (up from 668); every real pitch-selection site in `song.py` (rhythm riff, solo phrase, solo sequence, chorus lead) wired; `markov=None` byte-identical regression-tested across every shipped preset; verified live -- see TASKS.md's §17.6 tracker entry, 2026-09-11 |
| Editor -- P9.1 timeline scaffold (FastAPI + React/TS, real generate/mute/solo/duplicate/delete/reorder + Tone.js MIDI playback) | WIRED+TESTED | engine/ 596 passed, 1 skipped; editor/backend/ 8 passed; verified live in browser |
| Editor -- P9.3 real single-section regeneration (`regenerate_section`: full/pitch/rhythm modes, role override, density nudge, neighbor re-blend) + edit-history replay | WIRED+TESTED | engine/ 610 passed; editor/backend/ 12 passed; verified live in browser |
| Editor -- P9.4 accept/reroll/undo (snapshot-stack undo, capped at 20) | WIRED+TESTED | verified live in browser |
| Editor -- P9.5 Preview vs Render (`POST /api/export-rpp`, real `.rpp` download) | WIRED+TESTED | editor/backend/ 19 passed; verified live in browser |
| Editor -- P9.2 Pro + Guided modes (`blend_presets` reused for a real blend slider, `blast_fill_chance` override, both modes same live params per CLAUDE.md's law) | WIRED+TESTED | engine/ 613 passed, 1 skipped; editor/backend/ 21 passed; verified live in browser |
| Editor -- P9.6 VexFlow tab notation (real `(string, fret)` per cell via `Fretboard.pitch_to_fret`, `POST /api/section-tab`, `TabView.tsx`) | WIRED+TESTED | engine/ 613 passed, 1 skipped; editor/backend/ 25 passed; verified live in browser |
| Editor -- P9.7 section-level save/load presets (real local JSON persistence, `EditFields`/`RegenEdit` split, `SectionPresetPanel.tsx`) | WIRED+TESTED | engine/ 613 passed, 1 skipped; editor/backend/ 34 passed; verified live in browser (byte-identical reproduction on load) |
| Phase 9 editor (P9.1-P9.7) | COMPLETE | all seven sub-parts DONE, "All of them" authorization fully discharged |

Next: TASKS.md ## Next
