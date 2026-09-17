# Status — 2026-09-17

Canonical detail: **CURRENT.md**; commands in **README.md**.

Works: studio keeps pins (`human`/`guess-accepted` + `heard`) in `sections.jsonl`; mel
spectrogram under the WaveSurfer waveform; 6-stem picker; drafts; `hear`/`sync`/`hash`;
`agree`/`compare`/`export-jams`/`beats`/`audit`/`report`; 153 tests pass.

Empty or unrun on disk:
- `data/sections.jsonl` — 6 rows, 1 track (Rebirth). That is the whole keeper set.
- `data/drafts.jsonl` / `compare.json` / `beats.jsonl` / `sync.jsonl` / `agree.jsonl` — not written yet.
- `data/map.csv` — 71 rows, 55 `match=yes`; `flac_sha256` only once `scan`/`hash` runs.
- `data/holdout.csv` — 7 songs reserved. `engine/data/riff_bank.json` is local/gitignored.

Pytest proves wiring. It does not prove a riff.
