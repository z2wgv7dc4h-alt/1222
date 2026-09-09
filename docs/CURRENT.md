# CURRENT

task: P9.7
phase: 9 (Editor)
status: DONE
last_pytest: engine/ 613 passed, 1 skipped; editor/backend/ 34 passed
note: "All of them" -- user authorized all remaining Phase 9 sub-parts in one go (P9.2-P9.7). Full sequence: P9.3 (real single-section regeneration, the foundation) -> P9.4 (reroll/undo) -> P9.5 (Render .rpp) -> P9.2 (Pro + Guided modes) -> P9.6 (VexFlow tab notation) -> P9.7 (this entry, section-level save/load presets). ALL SEVEN Phase 9 sub-parts are now DONE -- the "All of them" authorization is fully discharged.

P9.7: a section preset IS a real, complete, reproducible `EditFields` (mode/role/hit_chance_bias/regen_seed, no position of its own) under a user-given name. `editor/backend/app/main.py`'s `RegenEdit` split into a new base `EditFields` (the reproducible part, reused by a saved preset) plus `RegenEdit(EditFields)` adding `section_position`. New `editor/backend/app/section_presets.py`: real local-only JSON persistence at `editor/backend/data/section_presets.json` (gitignored, user session state). Three new routes (`GET`/`POST /api/section-presets`, `DELETE /api/section-presets/{name}`). `editor/frontend/`: new `SectionPresetPanel.tsx` -- Save disabled until the section has a real edit applied; loading a preset applies it via the same `handleApplyEdit` path any regen action uses.

Verified live in the browser: regenerated a real Intro section (26->16 guitar hits), saved it as "heavy intro", reset back to base, then loaded "heavy intro" and confirmed it reproduced the EXACT same edited state byte-for-byte (16 hits, identical tab fret sequence) -- real proof "same seed + edit = same bytes" extends to saved presets. Deleted it and confirmed removal from both the UI list and the real local JSON file. `npx tsc --noEmit` clean.
updated: 2026-09-10

Phase 9 (the editor) is complete. Next real work: whatever the user directs next -- see TASKS.md's own remaining open items (P8 audio-render pipeline, P10.2 Song JSON, P10.3 preset calibration) for candidates.
