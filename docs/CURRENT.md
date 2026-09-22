# CURRENT

updated: 2026-09-22

The lab is the active work. Its contract is **`tools/boo-lab/CURRENT.md`**. If this file disagrees with that one, that one wins; then fix this file.

pytest: see `tools/boo-lab/STATUS.md` (lab) and `engine` suite locally. Do not keep a remembered test count here.

## Now

- Live lab gold (`tools/boo-lab/data/sections.jsonl`) is **empty** until a human Saves a heard box.
- The six Rebirth placeholder rows were deleted. Rebirth stays VAL in `holdout.csv`. Do not restore the old windows.
- Engine work is paused. `extract` may import `engine/riff_bank.py`; generation does not consume new lab pins yet.
- Do not train. Do not import `riff_model.py`. Do not edit Ww from this repo.

Operator start: `tools/boo-lab/USER.md`, then `START.bat`.

## Do

1. Pin by ear on FLACs you own. Heard + Save is gold.
2. Engine labyrinth stays one song, one 2–4 bar cell, tile. Hard-fail an uncovered role (no silent Markov).
3. Listen in tab view first.

## Do not

- Write more X devices.
- Treat `data/rebirth-sections.jsonl` as keepers.
- Treat compare scores on VAL as `prefer=`.
- Commit FLACs, GP files, stems, tokens, `map.csv`.

## Local only (gitignored)

| What | Path |
|---|---|
| Bank | `engine/data/riff_bank.json` |
| GP sources | `reference/gp-tabs/` |
| Corpus | `reference/audio-corpus/` |
| Lab map / drafts / stems | `tools/boo-lab/data/map.csv`, `drafts.jsonl`, `work/` |

Old novels live in git, not this tree. Lab notes: `tools/boo-lab/CHANGELOG.md`.
