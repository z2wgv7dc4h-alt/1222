# Status — 2026-09-14

Canonical detail: **CURRENT.md**.

## What works

- Studio at `:8765`: album list, mix + drums lanes, overlapping regions, lyrics click-to-seek, Pack, ingest drop zone.
- Save reads the **table** (`harvestTable`). Refuses a save if every box is under 1s (the old `0.00–0.25` wipe).
- Play box loops the selected region (`_playUntil`).
- Guess: GP5 markers + Demucs drums (cached) + librosa half-time / kick IOI. BPM uses `_scalar` (numpy 2 safe). Beats and kicks are separate try-blocks.
- Ingest copies FLAC, art (`jpg/png/webp`), GP5/GP7. Infers `Veil Of Maya - Matriarch - 2015`. Hoists new bands out of `born_of_osiris`.
- Scan: unique GP↔FLAC assignment, short-title floor, junk-token strip.
- Git: `1222` remote. Labels + source under `tools/boo-lab/src` and `data`. `work/` is gitignored.

## Known sharp edges

- UI **Push git** fails if the server cannot talk to Git Credential Manager, or if it tries to add ignored `work/`. Prefer cmd: `git add` / `commit` / `push` from `god-tier-metal`.
- Guess does not know BoO slams. No GP marker text `breakdown` + no half-time island = no Breakdown draft.
- RAR not ingested. Unzip first.
- `BOO_FLAC_ROOT=...\born_of_osiris` nests new bands inside BoO. Use `audio-corpus`.
- Disk folder names for some BoO rips are wrong — see `data/CATALOG.md`.
- AlphaTab is not the point; tabs are not read. GP is for notes at Pack time and Guess markers.

## Roles (how to mark)

| role | use |
|---|---|
| intro | album/song door |
| pulse | new named synth loop only |
| riff | guitar figure |
| breakdown | pit / half-time function (may overlap riff) |
| build | energy climb, not another pulse |
| hook | singable chorus figure |
| solo | lead |
| chill | energy drop |
| outro | tail |

Rebirth (AHP, 86.6s): intro 0–86.63; pulse 13–27.8, 33–41.5, 46.2–51; build 52.8–66.5; outro 69.5–86.63.

## After labels

Pack writes clips under `work/` (gitignored). That is the learning pack: mix + stems per box + meta.
