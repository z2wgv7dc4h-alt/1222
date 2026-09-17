# Changelog

## 2026-09-17

- **Keeper schema.** `schema.py` is the single source of truth (roles, figure/function layers, `SOURCES`, `is_keeper`, `stamp_box`, `same_role_overlaps`). Studio Save writes keepers only (`human`/`guess-accepted` + `heard`), drops unheard/`guess`/`msa-draft`, stamps a heard draft `guess-accepted`, rejects same-role overlap >50 ms, preserves extras; `GET /api/drafts`; tables carry role/figure/start/end/source/heard; **Load drafts** appends `msa-draft`/`guess` unheard.
- **Old pins.** `boo-lab hear --album X --track Y` flips `heard=true` on already-keeper rows for one track only (never the whole catalog).
- **Drafts.** `structure` writes `data/drafts.jsonl` only (allin1 → `msa-draft`; SongFormer when `SONGFORMER_HOME`/import → `songformer-draft`); `audit` command; keeper filtering in `pack`/`extract`; env-aware GP roots (`BOO_GP_ROOT`).
- **Research outputs.** `agree` (two-pass keeper diff, HR 0.5/3 + role/figure agreement), `compare` (drafts vs keepers, per-source rows, precision/recall/F 0.5/3 + role agreement, marks `split=holdout`), `export-jams` (JAMS 0.3 figure/function layers), `beats` (beat_this → allin1 fallback, `data/beats.jsonl`). Optional `intern` extra.
- **Audio pipeline.** Demucs default is 6-stem `htdemucs_6s` (guitar/piano isolated; Pack slices them, no-vox mixed from 6); `audio_extract` audio fallback (`source_type=audio_transcribed`); drum `low_confidence` flag; corpus `report`/`corpus_health.json`; train/val `holdout.csv` + `split` on every output.
- **Riffs.** `RiffFragment` gains `instrument`, `source_type`, `chord_notes`, `chord_frets`; cell hits carry real `palm_mute/harmonic/slide/tremolo/vibrato/accent`; categorized riff-bank failure reasons.
- **Vocals/lyrics.** Vocal melody via CREPE (pyin fallback); plain LRCLIB lyrics display + WhisperX **force-alignment of the provided words**; LRCLIB lookup fixes (space-numbered tracks, retries, no-duration fallback).
- **Studio.** Canonical roles, guarded Remove-album, 6-stem picker (`GET /api/stem`), per-song VAL badge, drum-confidence note (`GET /api/analysis`), flac fallback, safe album+track id resolution; `test_*` suite (136 tests) + `pyproject.toml` pytest config.

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
