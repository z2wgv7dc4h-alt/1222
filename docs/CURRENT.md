# CURRENT

task: P9.2
phase: 9 (Editor)
status: DONE
last_pytest: engine/ 613 passed, 1 skipped; editor/backend/ 21 passed
note: "All of them" -- user authorized all remaining Phase 9 sub-parts in one go (P9.2-P9.7). P9.3 (real single-section regeneration) landed first as the real foundation every other sub-part builds on -- see its own TASKS.md entry. This entry covers P9.2 (Pro + Guided modes), built after P9.3.

Per CLAUDE.md's own law ("Guided = sliders on the same params as Pro"), Guided is NOT a separate data model -- both modes drive the exact same two real engine knobs: `blend_with`/`blend_t` (nudge toward a second real preset via `presets.blend_presets`'s real linear interpolation of continuous character knobs only) and `blast_fill_chance` (overrides the module-default blast-beat coin-flip). `engine/song.py` gained `compose_song_from_preset` (extracted from `compose_song`'s retry loop, accepts a real `Preset` object directly since a blended preset has no id of its own) and threaded `blast_fill_chance` as a real optional override through the full call chain, defaulting to the existing constant when omitted (zero behavior change for existing callers). `editor/backend/app/main.py`'s `_compose` branches on whether a blend was requested, both paths going through the same real order/edits pipeline. `editor/frontend/`'s new `GuidedControls.tsx` shows the SAME live blend/blast controls in both modes, just relabeled (Pro shows raw param names, Guided shows friendly ones) -- toggling never resets a value.

Verified live in the browser: blending toward djent at t=0.5 measurably changed a real generated song (pm 0.55->0.56, kick-lock 0.77->0.78, preview 58.8s->55.7s); maxing blast_fill_chance changed it further (hits 295->300, kick-lock 0.78->0.69). `npx tsc --noEmit` clean.
updated: 2026-09-10

P9.6-P9.7 (VexFlow tab notation, section-level save/load presets) remain, per the same "All of them" authorization -- next up.
