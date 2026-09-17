# Status — 2026-09-18

Canonical detail: **CURRENT.md**; commands in **README.md**.

Works: studio keeps pins (`human`/`guess-accepted` + `heard`) in `sections.jsonl`; mel
spectrogram under the WaveSurfer waveform; 6-stem picker; drafts; `hear`/`sync`/`hash`;
`agree`/`compare`/`export-jams`/`beats`/`audit`/`report`; **171 tests pass**.
Interns (allin1 structure, beat_this, torchcrepe) run on **CUDA** when present
(RTX 5080, `torch 2.8.0+cu128`); `boo-lab doctor` reports the build. allin1 works
without an old natten build via `_natten_compat` (legacy NATTEN API + madmom
py2/numpy-2 shims). Generated outputs are gitignored; the tracked asset is keeper pins.

On disk now:
- `data/sections.jsonl` — 6 rows, 1 track (Rebirth), all `heard=true`. The whole keeper set.
- `data/drafts.jsonl` — 125 `msa-draft` rows across the 13 A Higher Place tracks (allin1, GPU).
- `data/beats.jsonl` — 13 tracks (`beat_this` preferred).
- `data/compare.json` — drafts vs keepers. Rebirth (holdout): **F0.5=0.737 F3=0.800 role3=0.250**.
- `data/sync.jsonl` — 13 A Higher Place tracks. `gp_onset_times` now reads `song.tempo` and walks
  the tab in **playback order** (repeat-open/close + alternative endings expanded, measure advance
  from the same beat arithmetic). GP clock now matches audio length within ~2% for 10 of 13.
  **3 `sync_ok`**: `02 - Elimination` (lag −0.093 s, 0.23), `06 - Starved` (−0.093 s, 0.39),
  `10 - A Higher Place` (0.023 s, 0.52); was 0 before. Still failing: `12` just over tolerance
  (−0.42 s); `03/05/08` find a wrong correlation peak despite near-right length; `02/08/11` tabs
  are 12–23% short of the recording. `01 - Rebirth` has no tab (`no-gp`). Perfect tabs in
  `gp5/A Higher Place/`; old duplicates in `reference/gp-tabs-superseded/`.
- `data/agree.jsonl` — Rebirth pass 1 (6 boxes). Pass 2 needs a human re-pin, then
  `boo-lab agree --album X --track Y --diff`.
- `data/map.csv` — 71 rows, 55 `match=yes`; `flac_sha256` only once `scan`/`hash` runs.
- `data/holdout.csv` — 7 songs reserved. `engine/data/riff_bank.json` is local/gitignored.

Pytest proves wiring. It does not prove a riff.
