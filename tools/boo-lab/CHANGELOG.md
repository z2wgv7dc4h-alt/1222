# Changelog

## 2026-09-18

### Export keepers to JAMS from the studio

- `jams_export.export_jam_one` writes one song's keeper boxes to `work/jams/<album>/<track>.jams` (JAMS 0.3, `segment_lab_figure` + `segment_lab_function`), reusing `build_jam`; it refuses with "no keepers to export" or a VAL reason and never touches `sections.jsonl`. New `POST /api/jams/{id}` exposes it (409 on refusal) and the Lab menu gains a **JAMS** button that reports the written path. USER.md Part B gets a JAMS note; CURRENT lists the endpoint.

### STATUS counts from disk

- New `boo-lab status` (`src/boo_lab/status.py`): rewrites only the marker-delimited `<!-- status:counts -->` block in `STATUS.md` with counts read from disk — keeper rows/tracks via `schema.load_section_rows`, draft rows + sources, `sync_ok`/total, and `map.csv` rows (reusing `data/corpus_health.json` when it is at least as new as the CSV instead of a second walker). The test-count line and all prose paragraphs are left untouched; it never runs pytest. STATUS.md gains the block; README/CURRENT list the command.

### One operator doc stack (drop APPLY/PATCHES/PROTOCOL/QUALITY)

- Removed `APPLY.md`, `PATCHES.md`, `PROTOCOL.md`, `QUALITY.md` (stale maintainer notes). The living docs are now only `USER.md` (operators), `LAW.md` (rules + a new "Quality bar" subsection), `CURRENT.md` (internals), `README.md` (install/reference), `STATUS.md` (snapshot), `CHANGELOG.md`. USER.md's first paragraph points at LAW/CURRENT/README; CURRENT lists the six living docs; no behavior change.

### Highlight selected track; docs catch-up

- The selected `#list` song is re-marked `.on` on every render (click, J/K, filter, first load) with `aria-current="true"` and a visible warm wash (`#1c1a14`), gold left rule, and `:focus-visible` gold outline — no reliance on the 2px border alone. `boo-lab figures` windows + adapt + `prefer=` remain wired; Guess still refuses a finished song. Docs: README points at `USER.md` and groups absolute paths under "This machine"; USER.md notes the guess refusal and the list highlight; STATUS's studio block covers adapt, figure windows, refusal, highlight and USER.md. Lab tests: **278 passed**.

### Guess won't touch finished songs; show adapt + prefer

- Guess refuses a song that already has a heard keeper: the studio button and `GET /api/estimate/{id}` return/alert "This song already has keepers. Guess is for a first pass." (`409`) instead of merging new drafts; an empty-keeper track still Guess-es. `apply_adapt` now stamps a changed draft with `adapt` (`shift` / `role` / `figure` combinations, only when a shift is ≥0.02 s or a role/figure actually changed; never a keeper source), and Guess/Load drafts coach once with "Adapted N drafts from your last saves on this album." `GET /api/tracks` carries `prefer` from `intern_rank.json` and the studio's Lab summary shows `prefer=none|…`. Docs: README paths moved under a "This machine" heading, USER.md notes the guess refusal, STATUS notes adapt/refuse/prefer. Lab tests: **278 passed**.

### Adapt intern drafts on load/structure

- `apply_adapt` now also runs on intern drafts: `structure.build_drafts` calibrates each new draft row before writing `data/drafts.jsonl`, and the studio's Load drafts (`GET /api/drafts`) calibrates the returned list; both print `adapt: intern drafts n_pairs=…` when the album blob has `n_pairs>=1`. Rows are flagged `_adapted` so a structure-written row is never shifted twice on load. Drafts only (keepers skipped), `heard`/`source` untouched, `sections.jsonl` never written. Lab tests: **273 passed**.

### Guess proposes figure windows + breakdown gate

- Guess now adds **figure-window drafts** from `data/figures.jsonl` when the song is `sync_ok` and the occurrence seconds are `times_trusted` (`role=riff`, `figure_id` set, `source=guess`, `heard=false`; a marker covering the same span within 0.35 s with the same `figure_id` is skipped). Not sync_ok or untrusted times ⇒ zero figure drafts. Audio half-time/kick breakdowns are filtered by a per-album gate: `rebuild_album` stores `breakdowns {n, median_span_sec}` (heard `breakdown` keepers, holdout excluded) in the album's `adapt.json` blob; with `n>=2` only spans 0.5–1.5× the median survive, `n<2` keeps current rules. Guess prints `figures_drafts=M breakdowns_used=N`; `sections.jsonl` untouched. Lab tests: **270 passed**.

### USER.md operator manual (gold vs stencil)

- New `tools/boo-lab/USER.md`: the operator manual in two parts — Part A (open, mark, keys, stuck) and Part B (gold keeper vs stencil draft, roles, Guess/interns, sync, learn/adapt as a scoreboard not training, figures/cells, VAL, commands, do-nots). README points to it first (`Using it: read USER.md first`) and labels absolute Windows paths "this machine". The studio How drawer gains the two-line suggestion/VAL note, and Guess / Load drafts now show a coach nudge (`N drafts — tick heard on the ones you accept, then Save.`) without overwriting a real error. CURRENT: operators start at USER.md. No behavior/math changes.

### Per-album adapt from accepted drafts (edges, role, figure)

- New `src/boo_lab/adapt.py`: `rebuild_album` pairs heard keepers with the album's drafts (greedy nearest start <= 3.0 s) and stores a per-album blob in `data/adapt.json` — median edge shift (`shift_start`/`shift_end`, clamped +/-0.50 s), intern-role -> saved-role map (min 2 pairs when n_pairs>=3, else 1), and draft `figure_id` -> saved `figure_id`. Holdout tracks never teach a mixed album (a holdout-only album may build for itself). `apply_adapt` shifts/maps only draft boxes, never ticks `heard`, never changes `source`, never writes `sections.jsonl`. Guess applies it after markers/breakdowns (prints `adapt: album=… n_pairs=… shift_start=…`); Save rebuilds the album blob and logs an `adapt` event best-effort; CLI `boo-lab adapt [--album X]`. `intern_rank`'s vote is untouched (still 5 songs). `data/adapt.json` gitignored. Lab tests: **265 passed**.

### Guess stretches marker times by `sync` clock_ratio

- When a song's `sync.jsonl` row is `sync_ok` with `clock_ratio` off 1.0 by ≥0.002, `estimate_hybrid` scales every tab-marker `start`/`end` by that ratio before the rest of the pipeline (existing beat snap unchanged), prints `guess: clock_ratio=1.027 stretched N markers`, and notes it. `clock_ratio` ~1.0/None leaves times unchanged; `sync_ok` false (or no row) still drops markers; audio-derived breakdown drafts are never stretched (they already live on the FLAC clock). Guess now resolves the typed album/track against `map.csv` before the sync/beats lookup. Thresholds untouched. Lab tests: **256 passed**.

### Intern rank spine; stub `enough_to_train` gone

- `learn.py` rewritten. `record(lab_root, kind, album="", track="", **payload)` appends a `{ts, kind, album, track, payload}` event to `data/learn.jsonl` and never raises into the caller. `build_rank`/`run_learn` rebuild `data/intern_rank.json` from `compare.compare()` (rebuilt when stale; no second F@0.5) and mark `prefer` only when a draft source has **>= 5 non-holdout songs** with keepers+drafts, **F@0.5 >= 0.50**, and a **>= 0.03** lead; holdout scores stay in the dict but never vote. Read-only `figure_agree` (keeper `figure_id` vs `figures.jsonl`, no renames), `sync_rate`, and `agree_pass` (via agree.py's own `diff_passes`) are recorded. `enough_to_train`/`role_prior`/`note` are removed; Save logs `save_snapshot`, `compare` refreshes the rank best-effort, and `structure`/`guess` print `prefer=<source>` only when they emit it. CLI `boo-lab learn [--album X]`; `data/learn.jsonl` + `data/intern_rank.json` gitignored. Lab tests: **252 passed**.

### `gp-export` records GP7/gpx that cannot feed markers

- New `boo-lab gp-export [--gp-root DIR]` (default `BOO_GP_ROOT`): finds every `.gp`/`.gpx` under the GP root and probes it through the already-used pyguitarpro path. A file that parses already works in `extract`/`scan`, so the command just tells you to run `boo-lab scan`; a `.gpx` — or a ZIP-container `.gp` (real `.gpx` content under a `.gp` name) — that pyguitarpro cannot read is recorded as `gpx-unsupported`, and any other parse failure as `gp7-unsupported`, in `data/gp_export.jsonl` (gitignored). No GP7 binary writer is invented, no converter is bundled, and `sections.jsonl` is never touched. Lab tests: **245 passed**.

### Figure windows are runs; studio suggests ids only

- `figures.py` windowing replaced: `bar_fp` (quantized 1/8 onsets + `deltas` + pitch-class sets; octave/velocity ignored, chords kept as sets) splits playback order into maximal equal-bar RUNS, and each run becomes ONE ostinato window — 8 identical bars yield 1 window, not 7 sliding 2-bar windows; leftover bars are paired into non-overlapping 2-bar blocks and a 2-bar window is never emitted inside a longer same-sequence window. `cluster_song` groups by exact fingerprint only (Jaccard merge removed), names a cluster by a consistent GP marker letter (`{role}-{letter}`) else `riff-A/B` by first start, and sets `conflict=true` when one letter maps to two fingerprints. `build_figures` emits only repeating clusters and carries `conflict`. The studio `<figure>` datalist still lists `n_hits>=2` ids (no auto-fill, no `heard`, no Save of hashes); a conflict raises one coach line without overwriting an explicit error. Lab tests: **241 passed**.

### Bank stores short cells per figure_id, not whole pins

- New `src/boo_lab/cells.py`: `assemble_cells` groups one-bar riff_bank fragments by `figure_id` (a human keeper figure_id covering the bar when `sync_ok`, else a `figures.jsonl` occurrence, else the marker letter / a local bar hash) and emits **one representative cell of 2–4 bars** — preferring the hashed `figures.jsonl` window, then an identical-bar run, then the first 1–2 bars. Every other hit is only an `occurrences` pointer (seconds only when `times_trusted`), so an 8-bar human box becomes a 2-bar cell, never an 8-bar bank fragment. `song_cells`/`build_cells` write `data/riffs.jsonl` per song and never blank it on a zero-row run; `boo-lab extract` now emits cells (and reduces long pins) while keeping the audio fallback and writing atomically. `tests/test_role_map.py` guards the lab→engine role map (all 9 roles present; `pulse` deliberately `None`; unknown fails). Lab tests: **237 passed**.

### Album/track resolve the way the studio names them

- New `catalogue.resolve_row`: exact → casefold → leading `YYYY` / `YYYY - ` album prefix + normalized track key (so `07 - Exist` == `07 Exist` == `Exist`; a different album that merely shares a year never matches; the numbered track wins when several reduce to the same title). Wired into `sync_track`, `hear`, `figures` (`build_figures` + CLI full-map reload), and the `agree`/`compare` CLI. A map miss is now `no-row`, distinct from a matched row whose gp is missing (`no-gp`, which fills the real gp/flac strings so the human sees the path); the returned record carries the resolved album/track. A genuinely failed `sync` note appends `tab_play=Xs flac=Ys dly=Zs`, reusing extract's `_playback_duration` (no second tempo walker). No sync math, thresholds, or keepers changed. Lab tests: **231 passed**.

### Clock rate-fit wired into sync_ok; untrusted figure times stay bars-only

- **Rate drift is a first-class outcome.** `sync.py` already computed `best_clock_fit` but `decide()` only used the ratio=1 lag; now the rate-adjusted onset lag must pass `decide` (still `|lag| < 0.35 s`, score ≥ 0.15 — no threshold loosened) and the chroma witness must agree at that same ratio within 0.25 s (a lone onset rate-fit may stand when no chroma exists). `clock_ratio` is always recorded (1.0 when no stretch) and a pass notes `ok (rate 1.027)`. The ~2.7% uniform-drift class passes; 20% still fails; a searched ratio with a bad resampled lag is not a pass.
- **Figure times follow the clock.** `build_figures` looks up `data/sync.jsonl`; unless that song's `sync_ok` is true it writes `start`/`end` and occurrence seconds as `null`, keeps `start_bar`/`end_bar` and the hash, and adds `times_trusted`.
- **LAW**: pin-layer vs cell-layer (2–4 bar cell inside a figure, never a 40 s box), and GP7 is not a Guess marker clock (GP5 markers; GP7 only after deterministic export-to-GP5). Lab tests: **223 passed**.

### Figure hashes — riff identity, never keepers

- New `src/boo_lab/figures.py`: `hash_window` fingerprints a 2- or 4-measure window from riff_bank's per-measure fragments (chord-aware pitch-class sets, coarse 4-beat onset grid; octave/velocity ignored), `cluster_song` groups exact hashes (optional pitch-class Jaccard merge when windows carry `pcs`/`rhythm`) and letters `riff-A`, `riff-B`, ... by first start, and `build_figures` walks the matched GP5 in playback order, slices contiguous 2/4-bar windows, clusters 4-bar first then uncovered 2-bar, and writes `data/figures.jsonl` (`source="figure-hash"`) with the never-blank-on-zero-rows law. `load_figures` reads it back per song. CLI `boo-lab figures [--album X --track Y]` (album+track together) and studio `GET /api/figures/{track_id}` feed a `figure` datalist (no auto-fill, no `heard`). Reuses `extract._engine_riff_bank`, `sync._playback_order`, `schema.write_jsonl_atomic`; never touches `sections.jsonl`/`drafts.jsonl`. Lab tests: **216 passed** (9 new in `tests/test_figures.py`). *(Superseded: windowing is now runs, not sliding 2/4-bar windows, and there is no Jaccard merge — see the "Figure windows are runs" entry above.)*

### Studio copy tidy — pin then drag

- The empty-wave ghost now reads **"Press 1 for Riff"**; the coach's zero-box line and the How drawer both say pins/keys **create** a box and drag only fits it; the table foot no longer implies dragging creates a box. **Pack** shows `"Save keepers before Pack."` (as an error) when there are no boxes, leaving the fetch path untouched. Docs corrected: in-app **Undo** exists (button + Ctrl+Z, plus `sections.jsonl.bak` on Save), daily pinning is role + figure + start/end + heard only (`form`/`uniq`/`inst`/bars sit behind **More columns**), and the Play/clock/Play box/Save/Undo/How bar with **Lab** / **Corpus** holding the rest is documented. No math, no endpoints, no ids changed.

### Coach line, first-run How, duration gate

- **Live coach in `#err`.** `showErr` now fills the status bar with a contextual default when no explicit message is given: wait-for-clock (`ws` duration <2), `VAL — leave unpinned`, `Press 1 for Riff (drag moves a box; it does not create one).`, `N not heard — Save will drop them`, else `N boxes. Save writes keepers.` Explicit errors (save failed, Guess notes, dropped_unheard) are tagged and never overwritten; the row/clock observer refreshes the coach only when it is not explicit.
- **Duration gate.** `add()` refuses to draw before the clock shows the full length (`showErr("Wait. Clock must show the full length before you draw.", true)`), the same guard to reuse for any future enableDragSelection.
- **First-run How.** The drawer auto-opens once after tracks load; Close or the scrim stores `boo-lab-how-v1` so it never auto-opens again.
- **Small type fixes.** Clock placeholder is `0:00 / —` in the HTML and pre-ready; `WaveSurfer.create` height is 168 to match `#wave`; the table header reads `figure (riff-A)`; How step 2 says to press a role pin (or 1) then drag, and explains figure naming.

### Studio regression pass

- **Chrome verified, not redesigned.** All 46 `getElementById` targets resolve; `harvestTable` still reads every `data-f` field and `table()` still builds the extra `<td>`s (CSS hides them, DOM keeps them); keyboard shortcuts (Space, 1–4, I/B/C/P, S, N, J/K, Delete, Ctrl+Z, ?, Esc) are intact and skipped for `INPUT`/`SELECT`; filters, dropzone, stem buttons, spec pills, Snap beats, Save's `dur<2`/`end<=start`/all-tiny refusals, and Guess's `/api/estimate/{id}` merge are unchanged. No duplicate ids, no new network calls, no `/api/sync` from the browser, and a zero-track load returns cleanly. Inline JS passes `node --check`. Added one comment above `*` in `<style>` marking the chrome intent.

### Empty + waiting states

- **List reads at a glance.** Each song meta is now `FLAC · GP5` / `FLAC · GP7` / `FLAC · no tab` / `FLAC · partial GP5`, built from the existing `has_flac` / `has_gp` / `gp_partial` / `gp_kind`; a tiny `VAL` tag shows when `split==="val"`; a mute `tab off-clock` shows only if a track row already carries `sync_ok===false` (the field is absent from `/api/tracks` today, so it is skipped — no new fetch). Filter pills are a segmented All / GP5 / No tab control.
- **Empty wave ghost.** With a song selected, duration loaded, and no boxes, `#emptyghost` overlays the mix lane ("Press 1 for Riff" / "1 Riff  2 Hook  3 Breakdown  I Intro"); it vanishes on the first box. Pure HTML/CSS overlay, `pointer-events:none`.
- **Waiting signals.** The Lab summary carries a mute count of draft/guess rows; **Pack** is visually disabled (`.off` + `aria-disabled`) at zero boxes and its handler early-returns with "Save keepers before Pack."; Guess / Save / heard / Snap beats / VAL badge have hover `title`s.
- Corpus drop-zone copy states the ingest contract; lyric/stem lanes get 8px bottom padding. Frontend only — no FFT / beat-canvas or API change, all ids intact.

### Studio chrome restyle + More columns

- **Finished-instrument chrome.** App is a 280px rail | main grid with the spectrogram dock at 104px; the rail keeps album thumbs, the serif wordmark, and one quiet line ("Pick a song. Box a part. Tick heard. Save."); song rows are tighter (13px title / 11px meta) and the active song is a gold 2px left rule, not a slab. Work header is one strip (48px art, title, album, VAL badge).
- **Two-row transport.** Primary row is Play · clock · Play box · Save (filled gold) · Undo · How (≤6 controls). A quiet second row holds `<details>` **Lab** (Guess, Load drafts, Lyrics, Pack, Snap beats, JSON, Next GP) and **Corpus** (drop zone + band name, Push git, Remove album). Role pins are their own equal-width row: 8px radius, coloured border only, fill at 12% on hover/active. Coach line is a full-width 13px bar; errors are breakdown red, never `alert()`.
- **More columns.** The table still holds every column and `data-f` attribute; `form` / `uniq` / `inst` / `bar0` / `bar1` / `source` start hidden (`display:none`) and **More columns** (`#btnMoreCols`) toggles `show-extra`. The How drawer is 400px and the dock gains a gold hairline. Restyle only plus that one small toggle — every `getElementById` id unchanged, no function body touched.

### Beat grid in the studio + Guess sync gate

- **Beat grid used.** New `GET /api/beats/{id}` serves `data/beats.jsonl`; the studio draws beat/downbeat ticks over the waveform and, with **Snap beats** (default on), snaps a dragged box edge to the nearest downbeat (≤250 ms) else nearest beat (≤120 ms). Previously `beats.jsonl` was written and never read.
- **Guess snaps to the grid.** Its audio-derived spans (half-time / kick breakdowns) are snapped to the nearest downbeat (≤250 ms), else beat (≤120 ms), from `data/beats.jsonl`.
- **Guess gates on sync.** `estimate_hybrid` now reads `data/sync.jsonl` for the song: if the tab was measured as **not** `sync_ok`, its marker sections are dropped with a note ("tab markers dropped: sync not ok … paint by hand"); if `sync_ok`, they're kept and the note says so. A tab known to misalign no longer silently supplies wrong times.

### Guess reads the tab's section structure

- `extract.estimate_from_gp` now walks the tab in **playback order** (repeats expanded) instead of once, and carries the marker's **section identity**: `form` = the letter (`A`/`B`/`C1`), `figure_id` = `role-token` (`riff-B`), and `unique` when the letter occurs once. A repeated letter (`02`'s `B`, `10`'s `A/B/F`, `12`'s `A/C/D`) now shows up as the *same returning section* rather than a fresh riff. The last box reaches the repeat-aware tab length (`_playback_duration`). The studio's Guess now uses those `form`/`figure_id`/`unique` fields instead of hardcoding `A`/`<role>-A`. Roles still come from `infer_role` (letters aren't roles; `C1 - Solo` → solo).

### Hardening pass

- **Fail-closed keeper law, one reader.** `schema.is_keeper` is true only for `human`/`guess-accepted`
  (a missing/empty source is NOT a keeper); `canonical_role` returns `None` for unmappable input;
  `stamp_box` rejects an unknown role/source instead of defaulting to `human`. New
  `schema.load_section_rows(path, keepers_only=True)` is the single reader (used by
  `pack`/`drums_extract`/`vocal_melody`/`holdout`) and enforces the full law — `role` + keeper
  `source` + `heard is True`. Deleted the four twin readers, including the
  `source == "human" or role` precedence bug that accepted machine drafts as human labels.
- **Atomic, non-destructive files.** `schema.write_jsonl_atomic` (temp + fsync + `os.replace`) is the
  one writer. Every `sections.jsonl` write — Save, `hear`, album-remove — uses it; album-remove
  parses (and aborts on a malformed line, nothing deleted) before touching files, and `hear` refuses
  rather than drop a malformed line. `beats`, `structure.build_drafts`, `sync`, `agree`,
  `drums_extract` and `vocal_melody` no longer blank their output on a zero-row/failed run.
- **Save is transparent + undoable.** The response carries `dropped_unheard` and
  `malformed_lines_skipped`; the previous file is kept as `data/sections.jsonl.bak` before each Save;
  the studio refuses a box with `end <= start` instead of the old auto-repair to `0.25s`; the source
  dropdown includes `songformer-draft` and Load-drafts preserves the real source.
- **allin1/madmom importability.** `madmom` added to the `intern` extra (allin1 imports it but its
  metadata omits it); `_natten_compat` also aliases the `collections` ABCs and now runs at
  `import boo_lab`, so `doctor`/CLI/structure apply the shims before madmom/allin1 load.
- **Engine tests encode the labyrinth hard-fail.** `tests/test_song.py` / `test_legato.py` no longer
  demand that a bank-uncovered role compose (a bank-tolerant seed helper), and a new test asserts
  `RiffBankCoverageError` for `chill`/`outro`. Engine: **820 passed, 1 skipped**.
- **Local data rebuilt:** `drafts.jsonl` 125 rows (reconstructed from `work/msa` without re-running
  allin1), `beats.jsonl` 13 tracks, `sync.jsonl` 7/13 `sync_ok`.

### Earlier this date

- **Perfect tabs + faithful sync clock.** Official 02–13 A Higher Place GP5s placed in
  `gp5/A Higher Place/` (old Songsterr/musicnotes duplicates moved to `reference/gp-tabs-superseded/`).
  `sync.gp_onset_times` now: reads `song.tempo` (defaulting to 120 stretched every tab ~1.6×),
  walks measures in **playback order** — `_playback_order` expands repeat-open/close and
  alternative endings — and advances by the same beat arithmetic as the onsets. GP clock matches
  audio length within ~2% for 10 of 13 (was 0.85–1.76×). `catalogue._key`/scan now matches
  space-numbered `NN Title.gp5` (`07 Exist` had silently unmatched). `sync_ok`: 02/06/10 (was 0).
- **Lead-in outcome.** `best_alignment` now also returns peak **prominence**; sync passes an
  "aligned with offset" case when a peak is outside the 0.35 s zero window but within 5 s, scores
  ≥0.15, has prominence ≥0.05, and the other witness agrees on the offset (≤0.25 s). Recorded as
  `offset_sec` / `ok (lead-in X.XXs)`. `13 - Faces Of Death` passes this way (both witnesses at
  −1.00 s); `05/12` don't (peak not prominent); `07/09/11` still fail as misalignment/data. `sync_ok`: 6 → **7**.
- **Guitar-stem sync.** `sync` now prefers the cached 6-stem `guitar.wav` and falls back to the mix
  per witness (guitar-only broke `02`, which the mix gets right). `stems` now actually honors its
  long-parsed-but-ignored `--album` flag and skips already-cached tracks; ran it to cache guitar for
  all 13 A Higher Place tracks.
- **Sync chroma co-witness.** Added `gp_chroma` (tab pitches held over each beat) + `audio_chroma`
  (`chroma_cqt`) + `chroma_lag_and_score`; `sync.jsonl` records `chroma_lag`/`chroma_score` and
  `sync_ok` passes if **either** the onset or chroma witness aligns. Rescued `03` (onset 1.21 s vs
  chroma 0.16 s) — `sync_ok` 5 → **6**. `07/09/11` still fail (chroma lag 1.9–2.5 s / low score).
- **Sync metric.** `best_lag_and_score` now blurs both envelopes (~120 ms) before correlating, so an
  onset only has to land near a tab note instead of exactly on it. Wrong-peak lags collapsed
  (13: 64 s→1.0 s, 11: 116 s→4.5 s, 05: 6.1 s→1.0 s). Added `best_clock_fit` (clock-rate search) as
  a `clock_ratio` **diagnostic** — deliberately not used to override the raw peak, since on a tab
  that's short because a section is missing it finds bogus rates. `sync_ok`: 3 → **5** (02/04/06/08/10).
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
  `boo_lab.egg-info` untracked. Tests: `test_natten_compat`, `test_device`, `test_doctor` → 177.

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
