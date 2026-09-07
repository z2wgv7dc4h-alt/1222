# PROGRESS

## 2026-09-08 — knowledge-chat close
Decisions:
- Discard `123/` as foundation. Keep only as cautionary reference + `RHYTHM_ENGINE_FIXES.md` pattern.
- metalerator superseded. djent-master: port algorithms only. Anvil/react-chords: ignore except optional WAV preview / VexFlow not react-chords.
- Ww/Forge: port named symbols in PORTS.md; do not run Ww.
- Engine is writer. No Suno/ACE-Step as composer.
- New FCC loop: short CLAUDE.md + atomic TASKS + hooks + one task per /clear.
- Completed P0.1: Created folder structure (engine/, engine/tests/, editor/, docs/, reference/, assets/drums/, assets/nam/)
- Completed P0.2: Confirmed assets/drums/ has .sfz and assets/nam/ has .nam files
- Completed P0.3: Set up pytest with test_smoke.py asserting True (1 passed in 0.01s)
- Completed P0.4: Verified .gitignore from kit is present (no assets/, no reference/)
- Completed P0.5: Confirmed docs/STATUS.md template exists with no Working claims

Phase 0 complete. Ready for P1.1: Fretboard + MIDI↔(string,fret)

## 2026-09-08 — P1.1-P1.5
- P1.1: `engine/fretboard.py` `Fretboard` class, MIDI<->(string,fret).
- P1.2: ported `pitch_to_fret` from `reference/ww-forge-prior-attempt/engine/tab_score.py` onto `Fretboard` (lowest-string, then cost `abs(fret_diff)+abs(string_diff)*2`).
- P1.3: `pitch_to_fret` raises `ValueError` on an unplayable pitch instead of the source's fake-position fallback; tested.
- P1.4/P1.5: `engine/scales.py` — `SCALES` table incl. `cluster`/`power`, `ALIASES` for shared-interval names (aeolian==minor); `test_no_duplicate_non_alias_scales` checks uniqueness.
- Fix: had created a nested `engine/engine/` package by mistake; flattened back to the single `engine/` folder (the one with `pyproject.toml`). Added `.claude/rules/anti-patterns.md` rule + `test_no_nested_engine_folder` so this fails loudly if repeated.
- Scope-index cleanup after a full read of `god-tier-metal-scope.md`: `PORTS.md` tunings row was missing `drop_e_8` (8-string); `SCOPE-INDEX.md`/`TASKS.md` P5 pointed at `## 6` (no bass content there) instead of `### 14.2` item 2; P8/P10 were missing `### 14.1`/`### 14.2` respectively. All corrected.
- 15 passed in 0.03s. Next: P1.6 tuning JSON from source MIDI.

## 2026-09-08 — Phase 1 + Phase 2 complete (parallel build)
- User directed a faster pace for this session: multiple worktree-isolated agents, still wired+tested per box, no shortcuts on rigor.
- Phase 1 (P1.6-P1.11) and Phase 2 (P2.1-P2.8) built concurrently by two agents in separate git worktrees (genuinely independent -- rhythm is pitch-agnostic), merged cleanly, no file conflicts.
- P1.6-P1.9: `engine/presets.py` + `engine/presets/*.json` -- 7 tunings, 6 mood presets, schema validator wired into the loader, glob-discovered.
- P1.10: `engine/theory.py` -- VoiceLeader (pick/walk/move/stab), shade(), ARC (density = 0.28+0.62*energy, derived not settable).
- P1.11: `engine/chords.py` -- ground-up chord-shape solver, no lookup tables.
- P2.1-P2.8: `engine/rhythm.py` -- generate_rhythm, tile_cell, metric_polyrhythm, tuplet_grid, pick_blast_type, RhythmRegistry, phrase_plan (IRVD), seeded-RNG reproducibility test.
- Enriched the 6 presets post-merge with the real `PACKS`/`VOCAB` data from `style_packs.py` (bpm, bars, feel, open_chance, octave_stab, kick style, per-style weighted interval vocab + motion, plus an ALIASES table for old band ids) -- the first pass used an invented minimal schema; the real, already-tuned data serves the Born-of-Osiris/Infant-Annihilator/Veil-of-Maya quality bar directly.
- Found and fixed a real correctness bug: P2.7's IRVD was implemented from PORTS.md's prose description because style_packs.py (the file PORTS.md named) doesn't contain IRVD logic. Located the real source (theory.py's `phrase_plan`, via a `riff_engine.py` comment) and re-ported verbatim -- the real rounding rule differs from the guess. Corrected PORTS.md's file attributions for IRVD, flatten+pickup (song_writer.py), and judge/retry (riff_engine.py's real `judge()` algorithm, now documented exactly).
- Expanded TASKS.md against a full re-read of god-tier-metal-scope.md: added P3.9-P3.12 (call-and-response, slam devices, chord-solver wiring, optional 2nd guitar), P6.6-P6.7 (atmospheric interlude section type, tempo curve), P9.7 (section-level presets) -- all real scope items that had no task box.
- Deleted stray empty "New Text Document.txt".
- 159 passed in 0.24s. Next: Phase 3 (Motif/riff), Phase 4 (Drums), Phase 5 (Bass) -- dispatching as parallel agents next.
