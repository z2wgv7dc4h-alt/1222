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

## 2026-09-08 — Phase 4 (Drums) + Phase 5 (Bass) complete; Phase 3 (Motif) in progress
- Both merged cleanly from separate worktrees, no conflicts (distinct new files: drums.py, bass.py).
- P4.1-P4.3: `engine/drums.py` -- role->MIDI map for the real SFZ kit (god-tier-metal-scope.md sec.11.7), wired CHINA->CRASH_2 fallback (this kit has no china sample), kick_follows_guitar (exact hit-position match), generate_blast_fill using the shared RhythmRegistry + pick_blast_type, three blast renderers (traditional/gravity/hammer).
- P5.1-P5.2: `engine/bass.py` -- derive_bass_tuning anchors the bass's TOP string an octave below the guitar's lowest open string then descends in perfect 4ths (guarantees the bass stays below the guitar even for wide extended-range tunings, unlike naively copying the guitar's lowest 4 strings down an octave); follow_guitar_rhythm locks to the guitar's hit/rest pattern but resolves every hit to the bass's own playable position, searching every octave of the target pitch class and falling back to the nearest reachable one.
- User supplied a much larger real MIDI corpus (`C:\Forge\user\midi\MIDIS.zip`, 1967 files) -- extracted into `reference/midi-corpus/` (gitignored) for P4.4, superseding the sparse ~63-file sample that shipped in the original reference bundle.
- 189 passed in 0.30s. Next: Phase 3 (Motif) landing shortly, then P4.4 (MIDI vocab mining), then Phase 6 (Structure).

## 2026-09-08 — Phase 3 (Motif/riff) complete -- Phases 1-5 all done
- `engine/motif.py`+6 supporting modules (groove/lead/performance/interplay/slam/riff), 47 new tests, 236 passed total.
- All 12 items done including the optional P3.12 (harmonized second guitar).
- P3.11 is the standout: wired `chords.solve_chord` (built in Phase 1, P1.11) into a real riff-generation call path via `riff.voice_chord_section` -- it had no caller anywhere until this.
- P3.8's double-tracking has an explicit regression test against the exact historical mistake documented in god-tier-metal-scope.md §18.3 (an earlier attempt's "double-tracking" was one performance time-shifted +8 ticks, not two independent takes).
- Caught a bookkeeping gap while ticking boxes: TASKS.md's `## Next` section had been recording progress, but the underlying per-phase sections (Phase 2, Phase 3) were never ticked when `## Next` moved on to the next wave -- fixed now; will keep both in sync going forward.
- 236 passed in 0.50s. Next: P4.4 (MIDI vocabulary mining, unblocked now that drums.py exists), then Phase 6 (Structure).

## 2026-09-08 — P4.4 complete: MIDI corpus density vocabulary
- `engine/midi_vocab.py`: parses the 1967-file real corpus with `mido` (new dependency, already installed), extracts hits-per-beat/fill-length/distinct-note stats per file, aggregates into 20-BPM-wide buckets + per-pack summaries, caches to `engine/data/midi_vocab.json`. `vocabulary_informed_hit_chance(bpm)` maps a target BPM to a density-informed `hit_chance`, wired into `drums.py` via `generate_vocabulary_informed_blast_fill` (a real call path, not a dead function).
- Real finding worth remembering for preset tuning later: density clearly falls as BPM rises across the whole corpus (80-100 BPM: 6.4 hits/beat -> 220-240 BPM: 2.8 hits/beat) -- faster sections are rhythmically sparser in real reference material, not busier.
- Honest deviations the agent flagged: this corpus has no tempo meta events (BPM comes from folder/file names via regex) and uses channel 0 for drums, not channel 9/10 as initially assumed.
- 256 passed in 4.48s (main's full corpus is present, unlike the isolated worktree which correctly skipped the corpus-dependent test). Next: Phase 6 (Structure) landing shortly.

## 2026-09-08 — Phase 6 (Structure) complete -- Phases 1-6 + P4.4 all done
- `engine/structure.py`: weighted section graph, flatten+bridge+pickup (ported from song_writer.py -- pickup was unused dead code in the source, this port wires it in for real, an improvement over the original), half-time-in-a-section, arc()-driven modulation (P6.4 finally calls theory.arc(), which existed since Phase 1 but had no caller), interlude section type, judge/retry (ported from riff_engine.judge's real thresholds), and internal tempo curves.
- 287 passed in 2.33s. The full pure-Python, pytest-verifiable generation engine (Phases 1-6) is now complete. Remaining work (Phase 7 Atmosphere is still pure-Python; Phases 8 Reaper, 9 Editor, 10 Export need real external tools/human verification and can't be honestly marked WIRED+TESTED without the user present to run/listen/click).
- Next: Phase 7 (Atmosphere), then a status report before attempting Phase 8+.
