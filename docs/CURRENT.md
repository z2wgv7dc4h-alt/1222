# CURRENT

updated: 2026-09-12
pytest: engine 803 passed, 1 skipped; editor/backend 34 passed (bank wire 1988d22)

## Now

Labyrinth bank is wired (`song._try_riff_bank_motif`, `ThemeRegistry.seed`).
Demo `phase2_riffbank_demo.mp3` (labyrinth seed 1) **user: sounds like shit.**

Instrumented: bank ran for intro/build/solo/breakdown/verse; `build` reused once.
The medley is the **selector** (role-bag of 1-bar fragments from many songs), not "bank never ran."

Do not write more X devices. Do not train. Do not `/next` the old queue.

1. `tools/boo-lab` — pin riffs on FLACs you own (`START.bat`).
2. Engine — one `source_song`, 2-4 bar riff, tile. Hard-fail empty labyrinth roles (no silent Markov).
3. Listen in **tab view** first. NAM/P8 only after that riff survives.

## Local only (gitignored; missing on a fresh clone)

| What | Path |
|---|---|
| Bank 2328 bars / 23 songs | `engine/data/riff_bank.json` |
| GP sources | `reference/gp-tabs-born-of-osiris/` |
| FluidSynth | `tools/fluidsynth/bin/fluidsynth.exe` |
| Soundfont | `tools/soundfonts/GeneralUser-GS.sf2` |
| ffmpeg | `tools/ffmpeg.exe` |
| Demo | Desktop `phase2_riffbank_demo.mp3` |

No bank file → labyrinth falls back to Markov. That is degradation, not a pass.

## Gaps that are real

- Bank: zero `chill` / `outro` fragments.
- P8.2-P8.8 (buses, NAM, sfizz, mix): MISSING. P8.1 `.rpp` exists.
- `riff_model.py` exists, unused for labyrinth. Do not import it.
- Twin APIs still live (`structure.pickup` vs `_pickup_cells`; pinch). One winner later, not now.

## History

Session novels: `docs/archive/` (FCC Read denied). Pre-cleanup TASKS/CURRENT: git `ac047fd`. Do not resurrect them into the queue.
