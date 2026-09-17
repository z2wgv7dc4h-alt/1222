# Changelog

## 2026-09-18

- **Perfect tabs + faithful sync clock.** Official 02–13 A Higher Place GP5s placed in
  `gp5/A Higher Place/` (old Songsterr/musicnotes duplicates moved to `reference/gp-tabs-superseded/`).
  `sync.gp_onset_times` now: reads `song.tempo` (defaulting to 120 stretched every tab ~1.6×),
  walks measures in **playback order** — `_playback_order` expands repeat-open/close and
  alternative endings — and advances by the same beat arithmetic as the onsets. GP clock matches
  audio length within ~2% for 10 of 13 (was 0.85–1.76×). `catalogue._key`/scan now matches
  space-numbered `NN Title.gp5` (`07 Exist` had silently unmatched). `sync_ok`: 02/06/10 (was 0).
- **Refinements.** Demucs subprocess gets an explicit `--device` from `device.py` (was implicitly
  choosing); `beats` allin1 fallback caches under `work/allin1`; `doctor --require-interns` exits
  non-zero when an intern is missing and `setup.bat` aborts on it, so a broken install fails at
  setup instead of at first analyze.
- **GPU by default.** Root cause of slow runs: the venv had `torch 2.8.0+cpu` and allin1 defaults
  to `device='cpu'`. `device.py` (`torch_device()`/`gpu_name()`) is the single switch; allin1,
  beat_this and torchcrepe read it. Verified on the RTX 5080 (`torch 2.8.0+cu128`); allin1 Rebirth
  now ~23s with `bpm=72`, 6 labeled segments, 85 beats instead of a degenerate single-label result.
- **Durable allin1.** `_natten_compat.py` reimplements NATTEN's pre-0.17 API
  (`natten1dqkrpb`/`natten1dav`/`natten2dqkrpb`/`natten2dav`) with exact `get_window_start` /
  `get_pb_start` ports and registers it before `allin1` imports; also restores madmom's Python-2
  builtins, the removed `np.int` aliases, and a NumPy-2-safe ragged `asarray`. No old natten build
  needed.
- **Onboarding + safety net.** `setup.bat` (venv, cu128-or-CPU torch, core + intern + pitch +
  align, then doctor), `constraints.txt` hard pins, `boo-lab doctor` (torch/CUDA/GPU + core deps +
  interns + extras with install hints). `structure` caches allin1 demix/spec under `work/allin1`.
- **Real drafts.** `structure --album "2009 - A Higher Place"` wrote 125 `msa-draft` rows,
  `sections.jsonl` untouched; `compare` reports F0.5=0.737 F3=0.800 role3=0.250 on Rebirth.
- **Repo hygiene.** `data/{drafts,beats,compare,sync,agree}.*` and `*.egg-info/` gitignored;
  `boo_lab.egg-info` untracked. Tests: `test_natten_compat`, `test_device`, `test_doctor` → 169.

## 2026-09-17

- **Keeper schema.** `schema.py` is the single source of truth (roles, figure/function layers, `SOURCES`, `is_keeper`, `stamp_box`, `same_role_overlaps`). Studio Save writes keepers only (`human`/`guess-accepted` + `heard`), drops unheard/`guess`/`msa-draft`, stamps a heard draft `guess-accepted`, rejects same-role overlap >50 ms, preserves extras; `GET /api/drafts`; tables carry role/figure/start/end/source/heard; **Load drafts** appends `msa-draft`/`guess` unheard.
- **Old pins.** `boo-lab hear --album X --track Y` flips `heard=true` on already-keeper rows for one track only (never the whole catalog).
- **Drafts.** `structure` writes `data/drafts.jsonl` only (allin1 → `msa-draft`; SongFormer when `SONGFORMER_HOME`/import → `songformer-draft`); `audit` command; keeper filtering in `pack`/`extract`; env-aware GP roots (`BOO_GP_ROOT`).
- **Research outputs.** `agree` (two-pass keeper diff, HR 0.5/3 + role/figure agreement), `compare` (drafts vs keepers, per-source rows, precision/recall/F 0.5/3 + role agreement, marks `split=holdout`), `export-jams` (JAMS 0.3 figure/function layers), `beats` (beat_this → allin1 fallback, `data/beats.jsonl`). Optional `intern` extra.
- **Audio pipeline.** Demucs default is 6-stem `htdemucs_6s` (guitar/piano isolated; Pack slices them, no-vox mixed from 6); `audio_extract` audio fallback (`source_type=audio_transcribed`); drum `low_confidence` flag; corpus `report`/`corpus_health.json`; train/val `holdout.csv` + `split` on every output.
- **Riffs.** `RiffFragment` gains `instrument`, `source_type`, `chord_notes`, `chord_frets`; cell hits carry real `palm_mute/harmonic/slide/tremolo/vibrato/accent`; categorized riff-bank failure reasons.
- **Vocals/lyrics.** Vocal melody via CREPE (pyin fallback); plain LRCLIB lyrics display + WhisperX **force-alignment of the provided words**; LRCLIB lookup fixes (space-numbered tracks, retries, no-duration fallback).
- **Studio.** Canonical roles, guarded Remove-album, 6-stem picker (`GET /api/stem`), per-song VAL badge, drum-confidence note (`GET /api/analysis`), flac fallback, safe album+track id resolution; `test_*` suite (136 tests) + `pyproject.toml` pytest config.
- **Box identity.** `stamp_box` gains `form` / `unique` / `instrument` / `start_bar` / `end_bar`; Save passes them through and fills GP bars only when `match=yes` (`extract.bars_for_times`, never blocks); studio columns `form / uniq / inst / bar0 / bar1`.
- **Map witnesses.** `map.csv` gains `flac_sha256` (`scan` hashes on rewrite, `boo-lab hash` fills empties; unknown columns preserved); `boo-lab sync --album --track` scores the GP onset clock vs the audio envelope and writes `data/sync.jsonl` (`sync_ok` iff `|lag| < 0.35 s` and score ≥ 0.15).
- **Studio spectrogram.** Real JS mel spectrogram drawn from the already-decoded WaveSurfer buffer (no second fetch, no deps): synced playhead, click-to-seek, section-box overlays, Wave/Spec/Both toggle. Tests: 153.

## 2026-09-14

- Save: harvest table first; refuse empty `0–0.25` boxes; wait for wave duration.
- Play box: stop at region end.
- Riff colour vs grey wave (riff was the same gold as the waveform).
- Guess: `_scalar` / `_flist` for librosa+numpy2; kicks no longer die when BPM fails.
- gitutil: do not add `work/`; ignore CRLF + gitignore hints; push without captured stdout so GCM can run.
- Ingest: copy artwork; walk dropped folders; keep album paths; infer band from `Band - Album - Year` and `Band-Song.gp5`; write new bands under `audio-corpus/<band>` not `born_of_osiris/new_band`.
- Catalogue scan: one GP per track; fuzzy title; strip Songsterr ids / “official tab”; short titles need a tighter score.
- Docs: README, LAW, STATUS, CHANGELOG, `.env.example`, CATALOG header, **CURRENT.md**.

## 2026-09-13

- Studio UI, Demucs-on-demand drums, lyrics LRC, Pack, ingest endpoint, album grouping.
- Commit `6482c30` on `z2wgv7dc4h-alt/1222`: guess BPM fix, save harvest, riff colours.
