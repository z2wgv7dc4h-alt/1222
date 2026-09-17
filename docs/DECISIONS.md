# DECISIONS

Facts only. Overturned lines stay here so nobody “rediscovers” them.

## Keep

- Symbolic writer, fretboard-legal notes, seeded RNG, no vocals.
- Do not edit Ww. Do not extend `123`.
- Steal methods, not datasets. No Songsterr automation (declined twice).
- No DadaGP/ProgGP without author access (gated).
- Reaper is the renderer. Editor is not Reaper.
- Guided = same params as Pro.
- Slam preset removed. IA devices (blasts, pinch, half-time) may exist as devices.
- Power chords fatten at **MIDI export only**. Judge/bass see one pitch.
- X.35 70% verbatim theme reuse.
- Labyrinth = BoO listening preset. Bank is the writer for that preset’s main riff.
- P8.1 static `.rpp` instead of live reapy daemon.

## Kill / ghetto

- Audio model as composer (Suno etc.).
- Local Transformer on ~70 songs (`riff_model.py`) — v20 was nonsense. File may stay; no import from `song.py`.
- Growing Markov as the product path.
- Role-bag 1-bar collage as “BoO.”
- Silent Markov when a labyrinth role has no fragments — must become hard-fail or drop the role.
- `/next` walking a novel. Queue is `TASKS.md` ## Now only.
- “Have you used all data?” as a session starter.

## Scope vs reality

Scope said: every note from theory, no pre-made MIDI.  
Labyrinth bank **is** pre-made GP bars. That is the product for BoO. Other presets may stay theory/Markov and must be labelled as such.

## Listen vs tests

Pytest proves wiring. User ear proves a riff. STATUS may not tick “sounds like BoO.”

## 2026-09-17 — boo-lab lab rules

- **A keeper is heard.** `data/sections.jsonl` holds keepers only (`source=human`/`guess-accepted`
  **and** `heard=true`). Machines write `data/drafts.jsonl` (`msa-draft`/`songformer-draft`/`guess`);
  they never label.
- **`structure` never writes `sections.jsonl`.** Drafts only. The studio Save is the one writer.
- **Box identity is form + figure_id + role:** `form` = large-scale letter, `figure_id` = the small
  figure (`riff-A`), `role` = function; `unique` / `instrument` / `start_bar` / `end_bar` optional.
- **Interns are extras.** allin1 / beat-this / SongFormer / jams / mir_eval stay optional; the
  default install is thin. The suite runs without them (mocked).
- **6-stem Demucs (`htdemucs_6s`) is the default** so guitar/piano separate from “other”; old
  4-stem caches stay valid.
- **Witnesses are map-level:** `flac_sha256` pins a row to the exact file; `sync_ok` means the tab
  clock is within 350 ms of the audio. Pins without `sync_ok` are still valid if heard; extract
  users should prefer `sync_ok`.
- **The studio spectrogram is a second view** of the already-decoded buffer; it does not change
  Save rules, and its failure never blocks pin/save.
