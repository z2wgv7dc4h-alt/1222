# CURRENT

task: P1.6-P1.11, P2.1-P2.8
phase: 1-2
status: DONE
last_pytest: 159 passed in 0.24s
note: Phase 1 (tonal+presets) and Phase 2 (rhythm) both complete -- built in parallel (independent, no shared files) via two worktree agents, then merged. Phase 1: tunings.json (7 tunings), 6 mood presets enriched with real PACKS/VOCAB data from style_packs.py (bpm/bars/feel/open_chance/kick/vocab weights+motion), schema validator wired into loader, glob-discovered, VoiceLeader/shade()/ARC ported from theory.py, ground-up chord-shape solver. Phase 2: two-layer rhythm gen, cell-tile polymeter, metric_polyrhythm, real tuplet grids, blast family, shared rhythm id, seeded-RNG reproducibility. Fixed a real bug post-merge: P2.7 IRVD was initially invented (PORTS.md pointed it at style_packs.py, which doesn't have it) -- found the real source (theory.py's phrase_plan, via a riff_engine.py comment) and re-ported it exactly; the real algorithm's rounding differs from the guess (Destruction = bars//4 floor not half-up; odd remainder bar goes to Variation not Repetition). Corrected PORTS.md's IRVD/flatten+pickup/judge-retry file attributions to their real locations (theory.py, song_writer.py, riff_engine.py). Also expanded TASKS.md with previously-uncovered scope items (call-and-response, slam devices, chord-solver wiring, tempo curve, atmospheric interlude, section-level presets).
updated: 2026-09-08
