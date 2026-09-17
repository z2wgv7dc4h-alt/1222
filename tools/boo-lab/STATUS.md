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
- `data/sync.jsonl` — 13 A Higher Place tracks. `gp_onset_times` reads `song.tempo`, walks the tab
  in **playback order** (repeats + alternative endings expanded). Two witnesses now score alignment:
  a blurred (~120 ms) **onset** correlation, and a **chroma** correlation (tab pitches, sustained,
  vs `chroma_cqt` — drums matter far less). `sync_ok` passes if either is within 350 ms at score
  ≥0.15; `clock_ratio`, `chroma_lag`, `chroma_score` are recorded. **6 `sync_ok`** (0 → 3 → 5 → 6):
  `02`, `04`, `06`, `08`, `10` on onsets; `03` rescued by chroma (onset said 1.21 s, chroma 0.16 s).
  Still failing: `12/13` lags 0.4–1.0 s, `05` ~1 s, `07/09/11` chroma lags 1.9–2.5 s / low score.
  `01 - Rebirth` has no tab (`no-gp`). Perfect tabs in `gp5/A Higher Place/`.
- `data/agree.jsonl` — Rebirth pass 1 (6 boxes). Pass 2 needs a human re-pin, then
  `boo-lab agree --album X --track Y --diff`.
- `data/map.csv` — 71 rows, 55 `match=yes`; `flac_sha256` only once `scan`/`hash` runs.
- `data/holdout.csv` — 7 songs reserved. `engine/data/riff_bank.json` is local/gitignored.

Pytest proves wiring. It does not prove a riff.
