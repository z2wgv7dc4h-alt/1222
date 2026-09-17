# Status — 2026-09-18

Canonical detail: **CURRENT.md**; commands in **README.md**.

Works: studio keeps pins (`human`/`guess-accepted` + `heard`) in `sections.jsonl`; mel
spectrogram under the WaveSurfer waveform; 6-stem picker; drafts; `hear`/`sync`/`hash`;
`agree`/`compare`/`export-jams`/`beats`/`audit`/`report`; **199 tests pass**.
Interns (allin1 structure, beat_this, torchcrepe) run on **CUDA** when present
(RTX 5080, `torch 2.8.0+cu128`); `boo-lab doctor` reports the build. allin1 works
without an old natten build via `_natten_compat` (legacy NATTEN API + madmom
py2/numpy-2/`collections` shims). Generated outputs are gitignored; the tracked asset is
keeper pins. Engine: **820 passed, 1 skipped** (`labyrinth` hard-fails on bank-uncovered
roles; the tests encode that).

Hardening (2026-09-18): the keeper law fails closed (`is_keeper` missing-source = not a
keeper; `canonical_role` → `None`; `stamp_box` rejects unknown role/source;
`schema.load_section_rows` is the one reader and requires `role` + keeper `source` +
`heard is True`). Every `sections.jsonl` write is atomic (`schema.write_jsonl_atomic`);
Save also keeps `data/sections.jsonl.bak` and reports `dropped_unheard`; `beats`/`structure`/
`sync`/`agree`/`drums`/`vocal_melody` no longer blank their output on a zero-row run.

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
  `chroma_lag`, `chroma_score`, `offset_sec` are recorded. An **aligned-with-offset** outcome also
  passes: a peak outside the 0.35 s zero window but within 5 s, with score ≥0.15, **peak prominence**
  ≥0.05, and the other witness agreeing on the offset within 0.25 s. **7 `sync_ok`**: `02`/`04`/
  `06`/`08`/`10` on onsets, `03` on chroma, `13` as a lead-in (`ok (lead-in -1.00s)`, both witnesses
  at −1.00 s). Not passed: `05` and `12` agree on ~0.4–1.0 s but the peak isn't prominent enough;
  `07` drifts 2.7 % (needs the rate fit, not an offset); `11` is 14 % short (missing section — a data
  gap); `09`'s chroma alone suggests a ~0.67 s offset but the onset witness doesn't corroborate, so
  it isn't trusted. `01 - Rebirth` `no-gp`.
- `data/agree.jsonl` — Rebirth pass 1 (6 boxes). Pass 2 needs a human re-pin, then
  `boo-lab agree --album X --track Y --diff`.
- `data/map.csv` — 71 rows, 55 `match=yes`; `flac_sha256` only once `scan`/`hash` runs.
- `data/holdout.csv` — 7 songs reserved. `engine/data/riff_bank.json` is local/gitignored.

Pytest proves wiring. It does not prove a riff.
