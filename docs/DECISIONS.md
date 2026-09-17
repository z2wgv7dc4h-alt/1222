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

## 2026-09-18 — lab hardening (facts)

- **One reader.** `schema.load_section_rows(path, keepers_only=True)` is the only reader of
  `sections.jsonl` (used by `pack`/`drums_extract`/`vocal_melody`/`holdout`). Keepers = truthy
  `role` + keeper `source` + `heard is True`. No twin readers.
- **Fail closed.** `is_keeper` treats a missing/empty source as not-a-keeper; `canonical_role`
  returns `None` for unmappable input; `stamp_box` rejects an unknown role/source. Unknown is never
  coerced to `human`/`riff`.
- **Atomic writes.** `schema.write_jsonl_atomic` (temp + fsync + `os.replace`) is the one writer.
  Every `sections.jsonl` write — Save, `hear`, album-remove — uses it; Save keeps
  `data/sections.jsonl.bak` (one-step undo) and reports `dropped_unheard`. A zero-row/failed run must
  never blank a prior file.
- **GPU by default.** `device.torch_device()` is the only switch; interns never hardcode `"cpu"`.
- **allin1 compat lives in `_natten_compat`, applied at `import boo_lab`.** Do not "fix" by pinning
  an old natten (no Windows/py3.12 wheel); the shim restores the pre-0.17 API, madmom's py2 builtins
  and `np.int`, NumPy-2 ragged `asarray`, and the `collections` ABCs.
- **Labyrinth hard-fail stays.** A bank-uncovered role raises `RiffBankCoverageError` (never silent
  Markov); the engine tests assert that rather than demanding the preset compose.
- **The beat grid is used, not write-only.** The studio draws beat/downbeat ticks and snaps dragged
  edges; Guess snaps its half-time/kick spans. `beats.jsonl` had been written and never read.
- **Guess uses the tab's own section identity.** Marker letters become `form`/`figure_id`, repeats are
  expanded (a returning letter is the same section), and it walks the tab's playback order. Sections
  carry `unique` when their letter occurs once.
- **Guess gates on sync.** A tab measured as not `sync_ok` has its marker sections dropped (not
  silently trusted); `sync_ok` keeps them. Calibration (shifting by the measured lag) waits until the
  lag sign is trusted.
- **Measure-content riff segmentation is rejected.** Comparing measures by note/rhythm pattern
  over-segments (795–1057 sections vs 143 markers; precision 0.15). Do not ship it; the tabs' marker
  letters and the allin1 `msa-draft` audio segmentation are the riff signal. Audio-based
  non-breakdown segmentation and an audio solo detector (0% hit rate) are likewise not shipped.
