# Status — 2026-09-18

Canonical detail: **CURRENT.md**; commands in **README.md**.

Works: studio keeps pins (`human`/`guess-accepted` + `heard`) in `sections.jsonl`; mel
spectrogram under the WaveSurfer waveform; 6-stem picker; drafts; `hear`/`sync`/`hash`;
`agree`/`compare`/`export-jams`/`beats`/`audit`/`report`; **174 tests pass**.
Interns (allin1 structure, beat_this, torchcrepe) run on **CUDA** when present
(RTX 5080, `torch 2.8.0+cu128`); `boo-lab doctor` reports the build. allin1 works
without an old natten build via `_natten_compat` (legacy NATTEN API + madmom
py2/numpy-2 shims). Generated outputs are gitignored; the tracked asset is keeper pins.

On disk now:
- `data/sections.jsonl` — 6 rows, 1 track (Rebirth), all `heard=true`. The whole keeper set.
- `data/drafts.jsonl` — 125 `msa-draft` rows across the 13 A Higher Place tracks (allin1, GPU).
- `data/beats.jsonl` — 13 tracks (`beat_this` preferred).
- `data/compare.json` — drafts vs keepers. Rebirth (holdout): **F0.5=0.737 F3=0.800 role3=0.250**.
- `data/sync.jsonl` — 13 A Higher Place tracks, all with a cached 6-stem **guitar** stem. `sync`
  prefers the guitar stem and **falls back to the mix per witness** (isolated guitar can mis-peak
  where the mix doesn't and vice versa). Two witnesses score alignment: a blurred (~120 ms) **onset**
  correlation, and **chroma** (tab pitches sustained vs `chroma_cqt`). `sync_ok` passes if either
  witness on either source is within 350 ms at score ≥0.15; `used_stem`, `clock_ratio`,
  `chroma_lag`, `chroma_score` are recorded. **6 `sync_ok`**: `02`/`04`/`06`/`08`/`10` on onsets,
  `03` on chroma (onset said 3.4 s, chroma 0.07 s). `05/07/09/11/12/13` still fail (residual
  0.4–1.0 s lead-ins, or chroma lags 2.0–2.5 s / low score). `01 - Rebirth` `no-gp`. Perfect tabs in
  `gp5/A Higher Place/`.
- `data/agree.jsonl` — Rebirth pass 1 (6 boxes). Pass 2 needs a human re-pin, then
  `boo-lab agree --album X --track Y --diff`.
- `data/map.csv` — 71 rows, 55 `match=yes`; `flac_sha256` only once `scan`/`hash` runs.
- `data/holdout.csv` — 7 songs reserved. `engine/data/riff_bank.json` is local/gitignored.

Pytest proves wiring. It does not prove a riff.
