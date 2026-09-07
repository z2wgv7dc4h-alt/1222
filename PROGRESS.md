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

## 2026-09-08 — Phase 7 (Atmosphere) complete + a full review pass found and closed the biggest gap
- `engine/atmosphere.py`: GM 90 pad / GM 56 orch-hit voicings, synth doubling (reuses motif.render_motif directly), accent-synced stabs. 302 passed.
- User asked for a full review + gap analysis. Biggest finding: Phases 1-7 each built and pytest-verified their OWN mechanism in isolation (rhythm, motif, drums, bass, structure, atmosphere), but nothing had ever taken a real `Preset` and run it through one real end-to-end generation pass. Confirmed via grep: no generation code anywhere read `preset.bpm`/`.bars`/`.open_chance`/`.kick`/`.group`/`.pedal`/`.octave_stab`, and `lead.py` (VoiceLeader-driven lead lines, built in Phase 3) had no caller anywhere.
- Closed this with `engine/song.py::compose_song(preset_id, seed)` -- a real four-piece band per section (two independently-humanized rhythm-guitar takes, a VoiceLeader lead line, bass locked to the guitar's rhythm) plus drums (kick + vocabulary-informed fills) and atmosphere (pad + accent stabs), judged/retried via the real Phase 6 `judge()`. `engine/tests/test_song.py` runs this against every real preset and passed on the FIRST attempt -- strong evidence the independently-built phases genuinely compose, not just individually correct.
- Also fixed: `pyproject.toml` still declared `dependencies = []` even though `drums.py` (imported almost everywhere downstream) now hard-imports `midi_vocab` -> `mido` at module level. Added `mido>=1.3.0` to match `requirements.txt`.
- Remaining honest gap (tracked as X.2 in TASKS.md): `preset.kick`/`.group`/`.pedal`/`.octave_stab` are validated in Phase 1 but no generation code branches on them yet -- `kick_follows_guitar` is one fixed algorithm regardless of a preset's declared kick style, and djent's signature 3-against-4 displacement/pedal behavior isn't implemented.
- 313 passed in 2.95s.

## 2026-09-08 — Wired ThemeRegistry, fixed 2 real bugs, added realistic lead behavior
- While discussing song.py with the user, walked through the code together and found `motif.ThemeRegistry` (built in Phase 3) had no caller anywhere -- every section was getting an independently-rolled motif instead of a developed recurring theme, which the scope doc calls "the single highest-leverage change for making songs sound composed rather than generated." Wired it into `compose_song`, keyed per section role, with `invert()` applied on alternate reuses.
- That surfaced a real bug: `invert()` can push a rendered pitch below the guitar's lowest open string (confirmed via the integration test suite, which failed loudly and correctly rather than silently). Fixed with `_snap_to_playable_octave`, mirroring the discipline `bass.py` already applies to the bass voice.
- User asked for real solos -- added role-aware lead generation: `solo` sections get a genuinely denser, higher, more active featured line; `chill`/`interlude` get a harmonized doubling of the rhythm's own theme (`riff.harmonize_line`); everything else is silent, since a busy independent lead would clash with a dense chug section (per the user's own sharp observation that the two guitars should be doing different things at different points, not the same generic thing everywhere).
- While testing the solo feature, found a second real bug: `compose_song`'s `seed` parameter was completely dead -- it delegated to `structure.judge_and_retry`, which always tries its own `range(max_seeds)` (0, 1, 2...) internally regardless of the caller's seed, so every call for a given preset silently collapsed onto whichever of seeds 0-5 happened to judge `ok` first. Replaced with a local retry loop seeded `seed, seed+1, ...` -- confirmed different seeds now produce genuinely different song structures (verified: seeds 0-4 on the djent preset now produce 5 distinct section sequences, and "solo" sections actually appear, which they never did before the fix).
- User named Periphery as a specific, standing musicianship goal (odd-grouping displacement, legato/technical lead lines, extended-chord ambient sections, metric modulation) -- added to CLAUDE.md's Bar line and tracked as TASKS.md X.6a/b/c (legato-run generator, extended chord vocabulary, metric modulation) since these are genuinely new capabilities, not just unwired existing data.
- 314 passed in 2.39s.
