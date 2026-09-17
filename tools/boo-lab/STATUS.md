# Status — 2026-09-17

Canonical detail: **CURRENT.md**.

## What works

- Studio at `:8765`: album list, mix + 6-stem lane (drums/bass/guitar/piano/other/vocals), overlapping regions, lyrics click-to-seek, Pack, ingest drop zone.
- Pin schema: rows carry `role`, `figure` (`figure_id`), `start`, `end`, `source`, `heard`. Save uses `schema.stamp_box` and writes **keepers only** (`human`/`guess-accepted` + `heard`); drops unheard, `guess`, `msa-draft`; a heard draft becomes `guess-accepted`; same-role overlap >50 ms is a 400 that lists the pair and writes nothing; `drafts.jsonl` is never touched.
- **Load drafts** pulls `msa-draft`/`songformer-draft`/`guess` from `data/drafts.jsonl` unheard; `GET /api/drafts`.
- Old pins predate `heard`: `boo-lab hear --album X --track Y` flips one track's keepers (single track only).
- Save reads the **table** (`harvestTable`). Refuses a save if every box is under 1s (the old `0.00–0.25` wipe).
- Play box loops the selected region (`_playUntil`).
- Guess: GP5 markers + Demucs drums (cached) + librosa half-time / kick IOI. BPM uses `_scalar` (numpy 2 safe). Beats and kicks are separate try-blocks.
- Ingest copies FLAC, art (`jpg/png/webp`), GP5/GP7. Infers `Veil Of Maya - Matriarch - 2015`. Hoists new bands out of `born_of_osiris`.
- Scan: unique GP↔FLAC assignment, short-title floor, junk-token strip.
- 6-stem Demucs default (`htdemucs_6s`); Pack slices guitar/piano too. Stems serve over `GET /api/stem/{id}/{name}`; drum `low_confidence` over `GET /api/analysis/{id}`.
- Audio fallback for songs with no GP (`source_type=audio_transcribed`); CREPE vocal melody; WhisperX force-aligned plain lyrics.
- Research outputs: `boo-lab agree` (two-pass keeper diff), `boo-lab compare` (drafts vs keepers per source, marks holdout), `boo-lab export-jams` (JAMS 0.3 figure/function), `boo-lab beats` (beat_this/allin1), `boo-lab audit`, `boo-lab holdout`, `boo-lab report`.
- Tests: `python -m pytest` under `tools/boo-lab` (**136 passing**), synthetic fixtures, no real FLAC/GP.
- Git: `1222` remote. Labels + source under `tools/boo-lab/src` and `data`. `work/` is gitignored.

## Known sharp edges

- UI **Push git** fails if the server cannot talk to Git Credential Manager, or if it tries to add ignored `work/`. Prefer cmd: `git add` / `commit` / `push` from `god-tier-metal`.
- Guess does not know BoO slams. No GP marker text `breakdown` + no half-time island = no Breakdown draft.
- RAR not ingested. Unzip first.
- `BOO_FLAC_ROOT=...\born_of_osiris` nests new bands inside BoO. Use `audio-corpus`.
- Disk folder names for some BoO rips are wrong — see `data/CATALOG.md`.
- AlphaTab is not the point; tabs are not a product surface. GP is for notes at Pack time and Guess markers.

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

Figure roles (`riff`, `hook`, `solo`, `pulse`) may overlap function roles (`intro`, `build`,
`breakdown`, `chill`, `outro`); two boxes of the same role may not overlap.

Rebirth (AHP, 86.6s): intro 0–86.63; pulse 13–27.8, 33–41.5, 46.2–51; build 52.8–66.5; outro 69.5–86.63.

## After labels

Pack writes clips under `work/` (gitignored): mix + drums/bass/guitar/piano/other/vocals/no-vox
per keeper box + `meta.json` (times, role, `figure_id`, source, split). Research outputs
(`agree`/`compare`/`export-jams`/`beats`) are read-only side files; `drafts.jsonl` is machine-only
and never promoted to `sections.jsonl` unless a human ticks `heard`.
