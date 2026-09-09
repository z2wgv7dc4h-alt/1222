# CURRENT

task: P9.1
phase: 9 (Editor)
status: DONE
last_pytest: engine/ 596 passed, 1 skipped; editor/backend/ 8 passed
note: First real editor work -- "let's build the ui and other items." Opened SCOPE-INDEX.md's P9 heading (`## 10. Application / Editor`) per CLAUDE.md's own rule before designing anything: real architecture is a local Python backend (FastAPI) + local React/TS frontend over localhost (scope sec.10.5), section-timeline layout per sec.10.1. User explicitly scoped this build to the timeline scaffold (P9.1) only -- not the full 7-part editor -- and chose a local dev server + browser tab over Electron/Tauri.

Built `editor/backend/` (FastAPI wrapping the real engine: `/api/presets`, `/api/compose`, `/api/export-midi`; `app/serialize.py` for real JSON-safe summaries, `app/arrange.py` for a real reorder/duplicate/mute/solo mechanism over an already-composed song) and `editor/frontend/` (Vite+React+TS+Tailwind v4, `@dnd-kit` drag-reorder timeline, Tone.js+`@tonejs/midi` real in-browser playback -- switched away from `html-midi-player` after `npm audit` found unpatched critical vulnerabilities in its Magenta.js dependency chain, ended at 0 vulnerabilities). Documented a real, honest scope boundary throughout: the engine can't yet regenerate a single section or blend a freshly-edited boundary (scope sec.10.3 is a real, separate, not-yet-built requirement), so this scaffold's CRUD rearranges already-generated sections rather than faking regeneration.

Verified end-to-end in a real browser (mcp Browser tool, not just built): generated a real metalcore song, confirmed mute/duplicate/delete all correctly change the real section arrangement and re-trigger MIDI export (58.8s -> 52.6s on mute), and real Tone.js audio playback starts/stops cleanly with no console errors. `.claude/launch.json` added for both dev servers.
updated: 2026-09-09

P9.2-P9.7 (Pro/Guided modes, real regen primitives, accept/reroll/undo, preview/render, VexFlow tab notation, section-level presets) remain real, separate, larger follow-up builds -- not attempted this pass, per the user's own explicit scoping choice.
