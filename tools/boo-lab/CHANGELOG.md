# Changelog

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
