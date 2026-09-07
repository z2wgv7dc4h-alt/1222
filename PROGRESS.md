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
