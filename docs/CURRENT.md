# CURRENT

updated: 2026-09-18
pytest: engine **820 passed, 1 skipped**; boo-lab **322 passed**

## Now

The lab (`tools/boo-lab`) is the active work and its own source of truth:
**`tools/boo-lab/CURRENT.md`**. It pins human keepers (`data/sections.jsonl`),
drafts machine output (`data/drafts.jsonl`), and ships a full studio + CLI
(spectrogram, draft/keeper schema, witnesses, agreement/JAMS exports).
Engine work below is paused; nothing here consumes the lab yet.

Lab pass (latest commit `0a98c31`): GP7 is native — `boo_lab/gpif.py` parses a
`.gp`/`.gpx` `score.gpif` (tracks/tunings/instrument, masterbars/time-sig/repeats/sections,
beats, notes with computed midi + articulations) and `sync` prefers a matching `.gp`/`.gpx`
over a `.gp5` sibling, clocking it via `gpif.note_events` (no GP5 conversion). Before it
`e2a5dee` (GPIF notes), `5df12ab`/`9fca6e6` (`interns` pass; `START.bat` runs hash +
beats/sync), `a21bc29` (`hash` fills `flac_sha256`). Interns run on
**GPU by default** (`boo_lab/device.py`); allin1 is
repaired for modern natten + madmom on py3.12/numpy2 by `boo_lab/_natten_compat.py` (also aliases the
`collections` ABCs and runs at `import boo_lab`); `setup.bat` + `constraints.txt` + `boo-lab doctor`
make a fresh machine reproducible. **Hardening**: the keeper law fails closed (one
`schema.load_section_rows` reader; `is_keeper`/`canonical_role`/`stamp_box` reject unknowns), every
`sections.jsonl` write is atomic with a `sections.jsonl.bak` one-step undo, and `beats`/`structure`/
`sync`/`agree`/`drums`/`vocal_melody` no longer blank their output on a zero-row run. `structure` wrote
**125 drafts** (13 BoO tracks); `compare` on Rebirth (holdout): **F0.5=0.737 F3=0.800 role3=0.250**;
`sync` **17/55**; engine **820 passed, 1 skipped**; boo-lab **322 passed**. Studio now draws beat/downbeat ticks and snaps box edges, plus per-role lanes (right-click to edit, layer filter); Guess carries the tab's section letters/repeats, gates on `sync_ok`, and snaps its audio spans to the beat grid. The lab now ships one resumable `boo-lab interns` pass over the whole analysis chain (drafts only), and clocks GP7 `.gp`/`.gpx` natively via the parsed GPIF score.

Real, done, verified, pushed this pass (tools/boo-lab/ + engine/riff_bank.py):
- Labyrinth bank redesigned: ONE real song, ONE 2-4 bar contiguous riff,
  tiled (the "role-bag medley" approach was heard, killed — see
  docs/DECISIONS.md). `RiffBankCoverageError` hard-fails a labyrinth role
  with no bank coverage instead of silently falling back to Markov.
- `RiffFragment` gained `chord_notes`/`chord_frets` — real chords were
  being collapsed to their top note only; now 35.6% of hits (real 2-note
  chords) and 2.5% (3-note) are preserved, not discarded.
- Real bass/lead-guitar/drum-onset/vocal-melody(pitch only, no lyrics)/
  audio-fallback extraction, all built and wired.
- boo-lab: real pytest suite (was zero), content-based mislabeled-.gpx
  detection (a real corpus scan found 53 `.gp3/4/5`-extensioned files were
  actually zip-based .gpx content), 6-stem demucs default (guitar now
  separable from "other"), corpus-health report, train/val holdout,
  human-role vocab bug fixed (boo-lab's own roles riff/hook/pulse were
  never translated to the engine's verse/chorus/[none] before being
  written to RiffFragment.role — dead code path so far, nothing corrupted
  yet, but was live wrong).
- Gitignored `tools/boo-lab/data/{riffs,vocal_melody,drum_patterns,
  section_tempo}.jsonl` — real extracted note/pitch content, same
  local-only posture as `engine/data/riff_bank.json`, this repo is public.

Not yet done: engine-side integration (bass/lead/drums/vocal-melody actually
consumed by generation) and per-section tempo/time-signature. Everything the
lab shipped this session is done: pack slices the 6-stem guitar/piano output,
drum `low_confidence`, CREPE vocal melody, `flac_sha256`/`sync_ok` witnesses,
box identity fields (`form`/`unique`/`instrument`/bars), and the studio
spectrogram. Source of truth for all of it: `tools/boo-lab/CURRENT.md`.

Do not write more X devices. Do not train. Do not import riff_model.py.
Do not `/next` the old queue.

1. `tools/boo-lab` — pin riffs on FLACs you own (`START.bat`).
2. Engine — one `source_song`, 2-4 bar riff, tile. Hard-fail empty labyrinth roles (no silent Markov).
3. Listen in **tab view** first. NAM/P8 only after that riff survives.

## Local only (gitignored; missing on a fresh clone)

| What | Path |
|---|---|
| Bank 2328 bars / 23 songs | `engine/data/riff_bank.json` |
| GP sources | `reference/gp-tabs/` |
| FluidSynth | `tools/fluidsynth/bin/fluidsynth.exe` |
| Soundfont | `tools/soundfonts/GeneralUser-GS.sf2` |
| ffmpeg | `tools/ffmpeg.exe` |
| Demo | Desktop `phase2_riffbank_demo.mp3` |

No bank file → labyrinth falls back to Markov. That is degradation, not a pass.

## Gaps that are real

- Bank: zero `chill` / `outro` fragments.
- P8.2-P8.8 (buses, NAM, sfizz, mix): MISSING. P8.1 `.rpp` exists.
- `riff_model.py` exists, unused for labyrinth. Do not import it.
- Twin APIs still live (`structure.pickup` vs `_pickup_cells`; pinch). One winner later, not now.

## History

Session novels: `docs/archive/` (FCC Read denied). Pre-cleanup TASKS/CURRENT: git `ac047fd`. Do not resurrect them into the queue.
