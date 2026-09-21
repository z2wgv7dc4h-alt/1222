## Unreleased
- constraints: pin `setuptools>=45,<81` so madmom/allin1 keep `pkg_resources` (fixes TWDA structure SKIP).
- Guess: merge adjacent same-letter GP markers into one continuous box; nested blast/breakdown drafts no longer split those runs. Later returns of the same figure stay separate.
# Changelog

## 2026-09-21 (later)

### Guess builds a structure spine from a tab-notes pack (no GP)

- A FLAC + tab-notes pack with **no `.gp`** (Mindful) used to fall through to
  audio-only half-time breakdowns. When `sync_ok` and `discover_pack` finds a
  pack, Guess now builds a real spine from the pack: high-density guitar
  phrases become `riff` boxes with simple `riff-A` / `riff-B` / `riff-C` ids by
  order (`source=tabnotes-structure`, new in `SOURCES`), on top of the existing
  kick-notation breakdowns and blast hints. No GP-style `A1`/`B` letters are
  invented -- the pack has none.
- The pack spine is **primary like `gp-marker`**: `_suppress_figure_flood` now
  caps figure-hash drafts against both sources (`_spine_spans` /
  `_spine_primary`), so a pack song is not buried under short 2-bar hashes. A
  GP marker tab still wins (the pack spine is only built when no `gp-marker`
  boxes exist), so Starved is unregressed. The `tabnotes-density` riff merge is
  skipped when the spine already supplied those phrases.
- New `tabnotes_drafts.pack_structure_spans` / `structure_drafts_for_song`;
  tests in `tests/test_guess.py` + `tests/test_tabnotes_drafts.py`; 445 pass.

### Ingest prep syncs pack-only tracks

- interns._step_sync used to require a GP path, so FLAC + tab-notes (no .gp)
  skips â€” Mindful never auto-synced after ingest. Now syncs when GP **or**
  discover_pack finds a pack. Tests in 	ests/test_interns_sync_pack.py.

### Blast role, on_figure, drum-feel drafts

- New function role **`blast`** (full-speed / blastbeat), opposite of breakdown;
  pin **T**, lane + docs. Stackable on a riff like breakdown.
- Optional box field **`on_figure`**: function â†’ figure_id it rides (no `riff-blast-A` names).
- Guess may propose `source=blast-hint` from dense drum stems; gated like breakdowns.
- Schema/SOURCES/LAW/USER updated; tests green on guess/schema/annotator blast path.

### Guess marker-first (Starved fix)

- When `sync_ok` and the GP has measure markers, **gp-marker sections are the spine**.
- Figure-hash / density micro-cells are **suppressed or capped** (â‰¥ ~4 s) so Guess
  does not flood 30 short riffs on top of A1â€¦H.
- `B - Solo`-style markers map to solo with figure letter / `on_figure`, not solo-B crumbs.
- MSA/Songformer remain **Load drafts**, not merged into the Guess button flood.

### Ingest discover + pack hygiene

- `read_manifest` enriches title/artist/id from `notes.json` (Songsterr thin manifests).
- `unpack_pack` skips sibling `.zip` / `_unpacked` junk in a reused drop folder.
- Fresh per-drop folder in `/api/ingest`; Mindful-style packs discover after ingest.
- Studio: outside-click closes right-click `#ctx` (capture) and stops Aâ€“B box loop.

### Track-list Pack / TN badge

- `/api/tracks` rows now carry `has_pack` + `pack_source`: true when
  `tabnotes.discover_pack` matches the song **or** a row in the ingested
  `data/tabnotes_index.jsonl` matches (same fuzzy title/artist rule, index is
  the cheap fallback). Never writes keepers.
- Sidebar meta shows `Pack` (pack is the only tab) or `TN` (pack supplements a
  GP tab); new **Pack** filter pill shows only songs with a pack. Help drawer
  gains one line. Tests in `tests/test_annotator.py`.

### Multi-select stem listen (real)

- The stem chips are now an **audition mixer**, not a waveform swap. Toggle any
  cached demucs stem (drums / bass / guitar / piano / other / vocals); with one
  or more on, the main transport plays the **sum of exactly those stems** via a
  lazily-created `AudioContext` (no new deps), and the full mix is muted
  (`ws.setVolume(0)`). All off â†’ full mix as before.
- Stems are decoded once per track and cached; playback is anchored to
  WaveSurfer's playhead and re-anchored on drift / seek / Aâ€“B loop wrap, so Play
  box and the box loop keep working. Chips for stems the song has not cached are
  greyed out and disabled. Track switch clears the selection back to the mix.
- Lower stem lane still shows one stem's waveform (the chip you toggled on).

### Still pending (honest)

- Nothing on this ticket; the two "later" items above are done.

## 2026-09-21

### Guess marker-first: no more figure-hash flood on a well-marked tab

- When a song's `sync_ok` tab carries measure markers, the `gp-marker`
  sections are the spine and the figure-hash stream is capped against them.
  Any figure draft shorter than 4 s is dropped (`FIGURE_DRAFT_MIN_SPAN`); once
  markers hit `GP_MARKER_MIN=4` or cover half the duration
  (`_markers_primary`), a draft that overlaps any marker is dropped too, so
  only uncovered gaps get filled. A returning marker letter already carries
  the same `figure_id`, so the `riff-D x4` / `solo-B` crumb pile is gone.
- A marker like `B-Solo` still emits `role=solo` / `figure_id=solo-B` from
  the letter; function overlays (halftime/kick/blast) are untouched and link
  to the overlapping marker figure via `on_figure`.
- Guess drops any `msa-draft`/`songformer-draft` source defensively -- those
  belong to Load drafts. New helpers `_marker_spans`/`_markers_primary`/
  `_suppress_figure_flood`; 6 new tests (`tests/test_guess.py`); 436 pass.

### Ingest UX: single file/folder, inferred band, auto-prep

- `ingest()` now takes a lone `.flac`/`.wav`, GP file, tab-notes `.zip`,
  `notes.json`, or pack folder â€” not only a mixed archive. New `_from_pack_id`
  reads `born_of_osiris__the_new_reign__s32187`; `_from_filename` reads
  `Born_Of_Osiris-Elimination` / `Born Of Osiris - Song`. A blank / `new_band`
  / `unknown` band is replaced by the inferred one and returned as
  `report["band"]` (with `band_inferred` and `albums`).
- New `prep_after_ingest()` runs after every `/api/ingest` and `boo-lab ingest`:
  scan â†’ album-scoped hash â†’ `interns --steps beats,sync` â†’ tab-notes density
  drafts, each soft-fail. Studio Corpus drop accepts files/folders, keeps
  relative paths, shows prep status, and reloads `/api/tracks` without a full
  page reload. `--band` is now optional. 10 tests (`tests/test_ingest.py`).

### Tab-notes utilization: density drafts, meter cuts, predict articulations

- New `src/boo_lab/tabnotes_drafts.py`. When a song's `sync.jsonl` is
  `sync_ok`, `pack_density_drafts` proposes high guitar-onset-density spans as
  `role=riff` and reuses Guess's `_half_time_spans` on the pack's drum onsets
  for `role=breakdown`; `build_density_drafts` merges them unheard
  (`source="tabnotes-density"`, added to `schema.SOURCES`) into
  `data/drafts.jsonl`, replacing only prior same-source rows for the songs
  rebuilt and leaving the file untouched on zero rows. Caps: same-role spans
  merge, min span 1 s. CLI `boo-lab tabnotes-drafts [--album] [--track]`;
  `interns` gains a `tabnotes_drafts` step after `sync`; Guess merges the riff
  spans read-only. `meter_cuts` reports measure boundaries where a pack's time
  signature changes or its tempo automation jumps (GPIF `tempo_map`/
  `time_sig_map` fallback); Guess notes `tempo/meter cuts at 12.3s, 45.1s` and
  snaps its audio/density edges to them (0.75 s), no new boxes. Predict frame
  features gain tab onset-density, palm-mute density, hammer density and a raw
  onset count (`N_MELS + 6`, zeros without a trusted tab). New tests
  (`tests/test_tabnotes_drafts.py` + Guess/predict additions); 407 pass.

### Studio: double-click loops the box

- Double-click a region or its table row: zoom spectrogram and **A-B loop** that span while you drag edges. Esc / Space / Play (toggle) stops; **Play box** still plays once.

### Structure predictor v1 scaffold (keeper-trained, drafts only)

- New `src/boo_lab/predict.py` + `boo-lab predict-train [--album X]` / `boo-lab predict
  [--album X] [--track Y]`. Trains a small 2-layer Conv1d (role + boundary heads) from
  heard keepers only: fixed 0.25s librosa log-mel + RMS + onset frames over the cached
  guitar stem else the mix, + one tab-onset-density column when `sync.jsonl` is `sync_ok`.
  Checkpoint `work/models/structure-v1/{weights.pt,config.json,label_map.json,metrics.json}`;
  a rerun loads and fine-tunes. Writes `data/drafts.jsonl` rows with the new
  `source=keeper-model` (`schema.SOURCES`, `heard=false`), replacing only prior
  keeper-model rows for those songs â€” never `sections.jsonl`. Holdout never trains; a
  holdout-only lab (today Rebirth) trains a flagged `holdout_fallback` overfit smoke.
  Guess merges existing keeper-model drafts read-only; `interns` gains a `predict` step
  that infers only when a model exists; Save fires a 3-epoch background fine-tune
  (torch-gated daemon, `BOO_PREDICT_SAVE_TRAIN=0` off). 7 new tests (`tests/test_predict.py`).

### Structure predictor north star (docs)

- CURRENT.md / USER.md: real learning = a keeper-trained structure model (drafts only);
  frozen interns do not retrain from Save; adapt/learn stay calibration. Thin v1 plan:
  boundary+role heads, `predict-train` / `predict`, holdout eval, Guess draft source later.

### START.bat: full interns prep before studio

- `START.bat` runs `scan` â†’ `hash` â†’ full `boo-lab interns` before studio (cache-first;
  never auto-Guess / never Save keepers). USER/README Open-Start aligned.

### Guess prefers map/GP7 via GPIF (not sibling GP5)

- `_prefer_tab` + `estimate_from_gpif`; sync_ok gate unchanged.

### Studio GP badge honesty

- `annotator.tracks()` resolves the `map.csv` gp path first, then upgrades a legacy `.gp5` to a matching GP7 via `sync._prefer_gpif_path` and the lab's own GP-root index (GP7-preferred), so a `.gp`/`.gpx` sibling in another `gp_root` subdir still wins; `.gp`/`.gpx` display as `GP7`, and a map path already pointing at GP7 is kept. Filter label is `Tab`. (`test_tracks_badge_prefers_gp7_over_legacy_gp5`.)

### GPIF note_events tempo carry-forward + Elimination sync_ok

- Mid-song tempo map on onsets; Elimination re-synced lead-in ok.

### Lyrics WhisperX times + gp_chroma 4-tuple

- Vocals stem â†’ WhisperX times; GPIF 4-tuple onsets no longer null chroma.
## 2026-09-18

### Studio: lanes named once; tiles show figure_id not "Riff"

- `annotator.html`: region tiles no longer paint the role word (`content: LABEL[role]` â†’ `""`); a tile shows only its `figure_id`, and only when it is wider than ~48px (`regionLabelFor`), so short boxes keep colour with no text and labels stop colliding. Each role's name now appears **once**, in a 44px left gutter overlay (`#lanegutter`, one label per lane), and the All/Figures/Functions pills hide the gutter label with its lane (`updateGutter`). No free-floating role text in the waveform; the region title tooltip still carries roleÂ·figureÂ·times. Selection outline/row highlight, single-click-no-zoom, double-click zoom, and the right-click menu are unchanged.

### Rematch GP: scored unique assignment; GP7 packs win

- `catalogue._key` now strips a leading track number whether it is followed by a separator **or a space** (`07 - Exist` and `07 Exist` both â†’ `exist`) and strips the `Born Of Osiris` band prefix however it is punctuated (so `Born_Of_Osiris-Goddess_Of_The_Dawn-s402311.gp` keys as `goddessofthedawn`, not `bornofosirisgoddessofthedawn`). New `_gp_candidates` scores every GP for a track â€” exact key `1000`, meaningful substring (both keys â‰¥5) `500+overlap`, a lead-track-number bonus when the filenames agree, a small **GP7 `.gp`/`.gpx` bonus** over `.gp5`, then the shorter name â€” and `scan_roots` assigns **one GP file â†’ one FLAC** (skips an already-claimed candidate). `_find_gp` now delegates to it. This drops the generic `me` alias overmatch (one tab was matched to four songs), restores the full Goddess tab, and lets the full GP7 packs (Discovery/AHP/Eternal Reign, placed under `gp-tabs/gp7/<band>/<album>/`, local) win over their numbered `.gp5` twins. `map.csv` rebuilt (71 rows, 52 `match=yes`; Discovery 13/13, AHP 12/12, Eternal Reign 9/9 now GP7); sync re-run (52 songs): **14 ok** â€” the GP7 tabs clock differently from the `.gp5`s, so the pass count dropped with the honest content mismatch. 3 new catalogue tests; a sync test made hermetic (`delenv BOO_GP_ROOT`). 342 pass.

### Ingest detects tab-notes zips into data/tabnotes

- `ingest.py` now detects tab-notes packs with `tabnotes.is_pack` (a folder or `.zip` whose `notes.json` is `format: tab-notes/1`; a GP/FLAC zip is never one) and unpacks each into `data/tabnotes/<safe_id>/` (`unpack_pack` strips the zip `<id>/` prefix, overwrites only that id), runs `load_pack`, and upserts `data/tabnotes_index.jsonl` via `append_index`. FLAC/GP/art copy behaviour is unchanged and packs are never copied into `BOO_FLAC_ROOT`/`BOO_GP_ROOT`; `_unpack_zips` skips them so they stop landing in `_unpacked` as mystery archives. `map.csv`/`sections.jsonl` are untouched (no stable `tabnotes` column exists). CLI `ingest <drop> --band NAME` and the studio `/api/ingest` drop both pass `lab_root` so the same path runs; one line per pack prints `id | title | tracks=N events=N -> dest`. Synthetic fixture only; no commercial pack in git. 339 pass.

### Tab-notes zip is a full multi-track score (raw+timeline+notes)

- New `src/boo_lab/tabnotes.py`: `load_pack(path)` accepts an operator-pasted `.zip`, its unpacked folder, or a `notes.json` (no HTTP, no required unzip) and parses the flat `notes.json` (format `tab-notes/1`, all event keys), `timeline.json` measures (the AUDIO clock: `start_sec_audio`/`audio_duration_sec`), `raw/song.json` tracks (tuning/capo/volume/balance/tempo automations) **and** `raw/parts/N.json` raw beats/notes (tuplet, dotted, bend_points), plus `raw/video_points.json`. Model: `TabTrack`, `TabEvent`, `TabRawBeat`/`TabRawNote`, `TabMeasure`, `TabNotesPack` with `audio_sec(event)`, both totals and `clock_ratio`, and `video_sec`. Helpers: `events_for`, `onsets_audio` (category/track), `onsets_audio_by_track`, `tempo_map` (raw automations else timeline), `tuning_of`, `bar_events`, `bar_fp_tab` (durationâ†’1/8, `pitch%12`, palm_mute/dead/hammer). CLI `boo-lab tabnotes --path F [--json] [--index]` (index â†’ `data/tabnotes_index.jsonl` only). `sync` discovers a pack under `data/tabnotes/**` (fuzzy title/artist), clocks guitar onsets on the audio grid (else drums), records `tabnotes`/`tabnotes_tracks`/`Â· tabnotes`, and prefers it over sibling `.gp5`/GPIF. Synthetic folder+zip fixtures (`tests/fixtures/tabnotes_tiny*`); `data/tabnotes/` is gitignored (operator packs may be commercial). No `sections.jsonl` writes; 336 pass.

### Studio: single click selects; double-click zooms to the box

- In `annotator.html`, a **single click** on a waveform region or its table row now only selects it (region marked, row `.on`): no zoom/fit/`setMinMax`/`zoomTo`/`pxPerSec`, no playhead seek, and no `scrollIntoView` page jump. **Double-click** (region or row) is the only detail jump: select, seek the playhead to the box start, and zoom the spectrogram to that box with ~10% padding each side (`zoomSpecToBox`). The spectrogram gained a real time window (`specView`); `drawSpec` crops `spec.off` and maps boxes/playhead to it, and the spectrogram click-to-seek maps through the same window. `Esc` (or the existing reset path) restores the previous zoom, else the full-song view; loading a song / Guess adding drafts never auto-zooms. The old double-click-toggles-heard shortcut is gone (heard stays in the row and the right-click panel, which are unchanged). No backend/schema change.

### Per-track drums/vocals drafts; fix vocals 6-stem lookup

- `drums`/`vocals` gain `--per-track`: `build_drum_patterns`/`build_vocal_melody` emit **one whole-track row per song** (`role=None`, `mode="track"`, `start=0`, `end=duration`, full onsets/notes, `split`) for every row with a cached 6-stem, no keeper pin needed. Both are still drafts only (never `sections.jsonl`); the two modes coexist â€” `_write_mode` replaces only its own `mode` and keeps the other (section rows carry no `mode` key). Fixed a real bug: `vocal_melody._find_vocals` omitted `htdemucs_6s` (the default 6-stem cache that `stems.find_stem` includes), so vocals found ~2 tracks; it now finds 34/71. Test count 327.

### Sync clocks GP7 via GPIF; do not prefer sibling gp5

- `sync_track` now prefers a GP7 score over a `.gp5`: given a row `gp` ending `.gp5`, `_prefer_gpif_path` finds a matching `.gp`/`.gpx` (same normalized stem, ignoring `07 -` vs `07 `) beside it or under `BOO_GP_ROOT/gp7`, clocks that path, and records it in the sync dict `gp` (note gains `Â· gpif`). `sync._tab_notes` / `_tab_play_seconds` read a `.gp`/`.gpx` via `gpif.load_score` + `note_events`/`duration_sec` FIRST instead of `guitarpro.parse`; `.gp5` and every other suffix still use guitarpro. `LAG_TOLERANCE`/`SCORE_THRESHOLD` and the clock-rate path are untouched, no GP5 files are deleted, `map.csv` is not rewritten, and `gpif_to_gp5` stays unused. Tests: sibling-`.gp` preference, GPIF-first routing, lone `.gp5` still guitarpro; 4 new, 322 pass.

### Expand GPIF notes (midi, voices, articulations, tempo map)

- `gpif.GpifNote` gains `voice`, `dead`, `accent`, `hammer`, `slide`; every Voice in a Bar is parsed (both schemas) and each note carries its voice index; `midi = tuning_midi[string-1] + fret` when the index exists, else `None` (never invented), replacing the XML `<Midi>` read. `note_events` now yields `(seconds, midi, duration_sec, palm_mute)` â€” seconds stays element `[0]`, so `sync`'s GPIF onset clock keeps grading GP7s (the only `sync.py` change is `gp_onset_times` reading `e[0]`; the GPIF fallback stays and no new sync logic was added). `tempo_map` is now `(unexpanded beat, bpm)` and `duration_sec` uses it (else per-bar/score tempo). CLI `gpif` prints `n_with_midi`. Fixture `tests/fixtures/tiny.gp` extended with a second voice; tests updated. No `sections.jsonl`, no `guess.py`/`figures.py`/`extract.py` edits, `gpif_to_gp5` untouched/unused. 318 pass.

### Richer GPIF model (midi, articulations, beats, tempo maps)

- `boo_lab/gpif.py` now reads the whole score, not just the clock: `GpifScore` gains `artist`/`album`; `GpifTrack` gains instrument type (`InstrumentSet/Type`) and capo; `GpifNote` gains `midi` and `articulations` (palm_mute/hammer/pull_off/dead/ghost/harmonic/slide/bend/let_ring/staccato/vibrato/accent/tie/trill/tremolo, normalized from flag elements or `Property` names); new `GpifBeat` (track/bar/`t_beat`/duration + `dynamic`, `chord`, `text`, its notes) and `GpifScore.beats`; new helpers `tempo_map`, `time_sig_map`, `section_list` alongside the existing repeat/`playback_beats`/`duration_sec`/`note_events`. Both the flat GP8/alphaTab schema and the nested fixture populate the richer fields (verified on the real GP7 packs: Bass/guitar instrument types, sections `A (0:01)`â€¦, harmonic/tie/slide/vibrato articulations, per-note midi). Foundation only â€” no consumer behavior changed (`sync`/`figures`/Guess untouched), no `sections.jsonl` writes, no GP5 conversion. Tests: 4 new; 317 pass.

### GPIF to GP5 writer; sync may clock from GP7 parse

- New `src/boo_lab/gpif_to_gp5.py`: `gpif_to_gp5(score, out)` builds a real `guitarpro.Song` from a `GpifScore` (title/tempo, one track per GPIF track skipping drums, strings from `tuning_midi`, headers from masterbars, notes as beats at `t_beat` with string/fret, `palmMute` when parsed) and writes GP5 (`version=(5,1,0)`), returning `(Path, drops)`; repeats are written as GP5 `isRepeatOpen`/`repeatClose`, section text as a `Marker`, and drops call out a skipped drum track or an out-of-range string. CLI `boo-lab gpif --path F --write-gp5 DIR` writes `<stem>.from-gpif.gp5` and prints the drops; `gp-export` converts each GPIF-parsable `.gp/.gpx` into `work/gp5-from-gpif/` and records `converted=true`/`drops` in `data/gp_export.jsonl` (still no TuxGuitar subprocess, no invented GP7 writer). `sync._tab_notes` now falls back to `gpif.note_events` (onsets only) when pyguitarpro rejects a `.gp/.gpx`, and `_tab_play_seconds` to `gpif.duration_sec`; if GPIF also fails the outcome stays `unreadable-gp`, `sync_ok` is never set from a failed parse, and `clock_ratio` is unchanged. Guess math, adapt, overlap Save rules untouched; no `sections.jsonl` writes. Round-trip + drops + fallback tests; 313 pass.

### Parse GP7 score.gpif for duration and notes

- New `src/boo_lab/gpif.py`: `open_gp(path)` opens a GP6/7 `.gpx`/`.gp` zip and requires `Content/score.gpif` (fail closed), `parse_gpif(xml)` returns a `GpifScore` (title, tempo, tracks with `tuning_midi`, masterbars with time signature / repeat map / section marker, notes with bar / `t_beat` / string / fret / duration / `palm_mute`). `playback_bar_order` expands masterbar repeat groups (same open/close/count idea as Guess's `sync._playback_order`); `playback_beats` and `duration_sec` walk that order (per-bar tempo map). New CLI `boo-lab gpif --path FILE` prints duration_sec/n_bars/n_notes/n_markers and writes nothing; GP7 supplies markers/notes only via this parsed score, never via Guess invention, and there is still no GP5 writer. Hand-made fixture `tests/fixtures/tiny.gp` (2 bars 4/4 120 bpm, D-standard, 4 notes, 2x repeat) + 10 tests. Untouched: Guess math, adapt, overlap Save rules, sync thresholds.

### Per-role lanes, right-click edit, layer filter

- The wave is now 240px and each role owns a lane (topâ†’bottom Introâ€¦Outro; `top=index*100/9`, `height=100/9-1`), so stacked parts show at once â€” `paintRegions`/`region-created` position every bar, and a row's role change re-lanes it. Selection is two-way: clicking a bar marks its `<tr>` `.on` (+`scrollIntoView`) with a stronger outline, clicking a row lights its bar, one box at a time. New right-click panel `#ctx` (role / figure / heard / unique / inst, Play box, Split at playhead when the playhead is inside, Delete) writes the SAME table `data-f` cells â€” no second Save path; Esc / click-outside closes. Hover shows a tooltip and double-click toggles heard. **Play box** is now one shared `playBox()` helper. A new All / Figures / Functions pill row next to Wave/Spec/Both hides other regions and rows with `display:none` (Save still harvests hidden rows). The figure datalist merges `/api/figures` (`n_hits>=2`) with figure_ids already on the song and drops intern prefixes (`intro-`/`verse-`/`chorus-`/`bridge-`) unless already used; figure inputs are â‰¥9em and `main` reserves 120px so the list can open. Guess math, adapt, overlap Save rules, and sync thresholds untouched.

### One resumable `interns` pass (cached analysis)

- New `src/boo_lab/interns.py` + `boo-lab interns [--album X] [--steps a,b,c]`: runs the whole analysis chain in order â€” `stems â†’ beats â†’ structure â†’ drums â†’ vocals â†’ lyrics â†’ sync â†’ extract â†’ figures â†’ compare â†’ learn â†’ status` â€” over the real `map.csv` rows. Each step is wrapped so one failure never aborts the rest (its error is reported and the run continues), and re-running resumes: `structure` reuses cached allin1/SongFormer JSON, `beats`/`sync`/`lyrics` skip rows already on disk. `compare` mirrors the CLI (writes `data/compare.json`, then `learn`), `learn` returns the rank summary, `extract` shells the CLI with `--album`. Never writes `sections.jsonl`. `structure.build_drafts` now loads `work/msa/<track>.json` / `.songformer.json` before re-running an intern, and a crashed/failed SongFormer run no longer feeds `None` into the segment reader (regression: the cached SongFormer payload is still emitted). Lab tests: **296 passed** (new `tests/test_interns.py`).

### Export keepers to JAMS from the studio

- `jams_export.export_jam_one` writes one song's keeper boxes to `work/jams/<album>/<track>.jams` (JAMS 0.3, `segment_lab_figure` + `segment_lab_function`), reusing `build_jam`; it refuses with "no keepers to export" or a VAL reason and never touches `sections.jsonl`. New `POST /api/jams/{id}` exposes it (409 on refusal) and the Lab menu gains a **JAMS** button that reports the written path. USER.md Part B gets a JAMS note; CURRENT lists the endpoint.

### STATUS counts from disk

- New `boo-lab status` (`src/boo_lab/status.py`): rewrites only the marker-delimited `<!-- status:counts -->` block in `STATUS.md` with counts read from disk â€” keeper rows/tracks via `schema.load_section_rows`, draft rows + sources, `sync_ok`/total, and `map.csv` rows (reusing `data/corpus_health.json` when it is at least as new as the CSV instead of a second walker). The test-count line and all prose paragraphs are left untouched; it never runs pytest. STATUS.md gains the block; README/CURRENT list the command.

### One operator doc stack (drop APPLY/PATCHES/PROTOCOL/QUALITY)

- Removed `APPLY.md`, `PATCHES.md`, `PROTOCOL.md`, `QUALITY.md` (stale maintainer notes). The living docs are now only `USER.md` (operators), `LAW.md` (rules + a new "Quality bar" subsection), `CURRENT.md` (internals), `README.md` (install/reference), `STATUS.md` (snapshot), `CHANGELOG.md`. USER.md's first paragraph points at LAW/CURRENT/README; CURRENT lists the six living docs; no behavior change.

### Highlight selected track; docs catch-up

- The selected `#list` song is re-marked `.on` on every render (click, J/K, filter, first load) with `aria-current="true"` and a visible warm wash (`#1c1a14`), gold left rule, and `:focus-visible` gold outline â€” no reliance on the 2px border alone. `boo-lab figures` windows + adapt + `prefer=` remain wired; Guess still refuses a finished song. Docs: README points at `USER.md` and groups absolute paths under "This machine"; USER.md notes the guess refusal and the list highlight; STATUS's studio block covers adapt, figure windows, refusal, highlight and USER.md. Lab tests: **278 passed**.

### Guess won't touch finished songs; show adapt + prefer

- Guess refuses a song that already has a heard keeper: the studio button and `GET /api/estimate/{id}` return/alert "This song already has keepers. Guess is for a first pass." (`409`) instead of merging new drafts; an empty-keeper track still Guess-es. `apply_adapt` now stamps a changed draft with `adapt` (`shift` / `role` / `figure` combinations, only when a shift is â‰¥0.02 s or a role/figure actually changed; never a keeper source), and Guess/Load drafts coach once with "Adapted N drafts from your last saves on this album." `GET /api/tracks` carries `prefer` from `intern_rank.json` and the studio's Lab summary shows `prefer=none|â€¦`. Docs: README paths moved under a "This machine" heading, USER.md notes the guess refusal, STATUS notes adapt/refuse/prefer. Lab tests: **278 passed**.

### Adapt intern drafts on load/structure

- `apply_adapt` now also runs on intern drafts: `structure.build_drafts` calibrates each new draft row before writing `data/drafts.jsonl`, and the studio's Load drafts (`GET /api/drafts`) calibrates the returned list; both print `adapt: intern drafts n_pairs=â€¦` when the album blob has `n_pairs>=1`. Rows are flagged `_adapted` so a structure-written row is never shifted twice on load. Drafts only (keepers skipped), `heard`/`source` untouched, `sections.jsonl` never written. Lab tests: **273 passed**.

### Guess proposes figure windows + breakdown gate

- Guess now adds **figure-window drafts** from `data/figures.jsonl` when the song is `sync_ok` and the occurrence seconds are `times_trusted` (`role=riff`, `figure_id` set, `source=guess`, `heard=false`; a marker covering the same span within 0.35 s with the same `figure_id` is skipped). Not sync_ok or untrusted times â‡’ zero figure drafts. Audio half-time/kick breakdowns are filtered by a per-album gate: `rebuild_album` stores `breakdowns {n, median_span_sec}` (heard `breakdown` keepers, holdout excluded) in the album's `adapt.json` blob; with `n>=2` only spans 0.5â€“1.5Ã— the median survive, `n<2` keeps current rules. Guess prints `figures_drafts=M breakdowns_used=N`; `sections.jsonl` untouched. Lab tests: **270 passed**.

### USER.md operator manual (gold vs stencil)

- New `tools/boo-lab/USER.md`: the operator manual in two parts â€” Part A (open, mark, keys, stuck) and Part B (gold keeper vs stencil draft, roles, Guess/interns, sync, learn/adapt as a scoreboard not training, figures/cells, VAL, commands, do-nots). README points to it first (`Using it: read USER.md first`) and labels absolute Windows paths "this machine". The studio How drawer gains the two-line suggestion/VAL note, and Guess / Load drafts now show a coach nudge (`N drafts â€” tick heard on the ones you accept, then Save.`) without overwriting a real error. CURRENT: operators start at USER.md. No behavior/math changes.

### Per-album adapt from accepted drafts (edges, role, figure)

- New `src/boo_lab/adapt.py`: `rebuild_album` pairs heard keepers with the album's drafts (greedy nearest start <= 3.0 s) and stores a per-album blob in `data/adapt.json` â€” median edge shift (`shift_start`/`shift_end`, clamped +/-0.50 s), intern-role -> saved-role map (min 2 pairs when n_pairs>=3, else 1), and draft `figure_id` -> saved `figure_id`. Holdout tracks never teach a mixed album (a holdout-only album may build for itself). `apply_adapt` shifts/maps only draft boxes, never ticks `heard`, never changes `source`, never writes `sections.jsonl`. Guess applies it after markers/breakdowns (prints `adapt: album=â€¦ n_pairs=â€¦ shift_start=â€¦`); Save rebuilds the album blob and logs an `adapt` event best-effort; CLI `boo-lab adapt [--album X]`. `intern_rank`'s vote is untouched (still 5 songs). `data/adapt.json` gitignored. Lab tests: **265 passed**.

### Guess stretches marker times by `sync` clock_ratio

- When a song's `sync.jsonl` row is `sync_ok` with `clock_ratio` off 1.0 by â‰¥0.002, `estimate_hybrid` scales every tab-marker `start`/`end` by that ratio before the rest of the pipeline (existing beat snap unchanged), prints `guess: clock_ratio=1.027 stretched N markers`, and notes it. `clock_ratio` ~1.0/None leaves times unchanged; `sync_ok` false (or no row) still drops markers; audio-derived breakdown drafts are never stretched (they already live on the FLAC clock). Guess now resolves the typed album/track against `map.csv` before the sync/beats lookup. Thresholds untouched. Lab tests: **256 passed**.

### Intern rank spine; stub `enough_to_train` gone

- `learn.py` rewritten. `record(lab_root, kind, album="", track="", **payload)` appends a `{ts, kind, album, track, payload}` event to `data/learn.jsonl` and never raises into the caller. `build_rank`/`run_learn` rebuild `data/intern_rank.json` from `compare.compare()` (rebuilt when stale; no second F@0.5) and mark `prefer` only when a draft source has **>= 5 non-holdout songs** with keepers+drafts, **F@0.5 >= 0.50**, and a **>= 0.03** lead; holdout scores stay in the dict but never vote. Read-only `figure_agree` (keeper `figure_id` vs `figures.jsonl`, no renames), `sync_rate`, and `agree_pass` (via agree.py's own `diff_passes`) are recorded. `enough_to_train`/`role_prior`/`note` are removed; Save logs `save_snapshot`, `compare` refreshes the rank best-effort, and `structure`/`guess` print `prefer=<source>` only when they emit it. CLI `boo-lab learn [--album X]`; `data/learn.jsonl` + `data/intern_rank.json` gitignored. Lab tests: **252 passed**.

### `gp-export` records GP7/gpx that cannot feed markers

- New `boo-lab gp-export [--gp-root DIR]` (default `BOO_GP_ROOT`): finds every `.gp`/`.gpx` under the GP root and probes it through the already-used pyguitarpro path. A file that parses already works in `extract`/`scan`, so the command just tells you to run `boo-lab scan`; a `.gpx` â€” or a ZIP-container `.gp` (real `.gpx` content under a `.gp` name) â€” that pyguitarpro cannot read is recorded as `gpx-unsupported`, and any other parse failure as `gp7-unsupported`, in `data/gp_export.jsonl` (gitignored). No GP7 binary writer is invented, no converter is bundled, and `sections.jsonl` is never touched. Lab tests: **245 passed**.

### Figure windows are runs; studio suggests ids only

- `figures.py` windowing replaced: `bar_fp` (quantized 1/8 onsets + `deltas` + pitch-class sets; octave/velocity ignored, chords kept as sets) splits playback order into maximal equal-bar RUNS, and each run becomes ONE ostinato window â€” 8 identical bars yield 1 window, not 7 sliding 2-bar windows; leftover bars are paired into non-overlapping 2-bar blocks and a 2-bar window is never emitted inside a longer same-sequence window. `cluster_song` groups by exact fingerprint only (Jaccard merge removed), names a cluster by a consistent GP marker letter (`{role}-{letter}`) else `riff-A/B` by first start, and sets `conflict=true` when one letter maps to two fingerprints. `build_figures` emits only repeating clusters and carries `conflict`. The studio `<figure>` datalist still lists `n_hits>=2` ids (no auto-fill, no `heard`, no Save of hashes); a conflict raises one coach line without overwriting an explicit error. Lab tests: **241 passed**.

### Bank stores short cells per figure_id, not whole pins

- New `src/boo_lab/cells.py`: `assemble_cells` groups one-bar riff_bank fragments by `figure_id` (a human keeper figure_id covering the bar when `sync_ok`, else a `figures.jsonl` occurrence, else the marker letter / a local bar hash) and emits **one representative cell of 2â€“4 bars** â€” preferring the hashed `figures.jsonl` window, then an identical-bar run, then the first 1â€“2 bars. Every other hit is only an `occurrences` pointer (seconds only when `times_trusted`), so an 8-bar human box becomes a 2-bar cell, never an 8-bar bank fragment. `song_cells`/`build_cells` write `data/riffs.jsonl` per song and never blank it on a zero-row run; `boo-lab extract` now emits cells (and reduces long pins) while keeping the audio fallback and writing atomically. `tests/test_role_map.py` guards the labâ†’engine role map (all 9 roles present; `pulse` deliberately `None`; unknown fails). Lab tests: **237 passed**.

### Album/track resolve the way the studio names them

- New `catalogue.resolve_row`: exact â†’ casefold â†’ leading `YYYY` / `YYYY - ` album prefix + normalized track key (so `07 - Exist` == `07 Exist` == `Exist`; a different album that merely shares a year never matches; the numbered track wins when several reduce to the same title). Wired into `sync_track`, `hear`, `figures` (`build_figures` + CLI full-map reload), and the `agree`/`compare` CLI. A map miss is now `no-row`, distinct from a matched row whose gp is missing (`no-gp`, which fills the real gp/flac strings so the human sees the path); the returned record carries the resolved album/track. A genuinely failed `sync` note appends `tab_play=Xs flac=Ys dly=Zs`, reusing extract's `_playback_duration` (no second tempo walker). No sync math, thresholds, or keepers changed. Lab tests: **231 passed**.

### Clock rate-fit wired into sync_ok; untrusted figure times stay bars-only

- **Rate drift is a first-class outcome.** `sync.py` already computed `best_clock_fit` but `decide()` only used the ratio=1 lag; now the rate-adjusted onset lag must pass `decide` (still `|lag| < 0.35 s`, score â‰¥ 0.15 â€” no threshold loosened) and the chroma witness must agree at that same ratio within 0.25 s (a lone onset rate-fit may stand when no chroma exists). `clock_ratio` is always recorded (1.0 when no stretch) and a pass notes `ok (rate 1.027)`. The ~2.7% uniform-drift class passes; 20% still fails; a searched ratio with a bad resampled lag is not a pass.
- **Figure times follow the clock.** `build_figures` looks up `data/sync.jsonl`; unless that song's `sync_ok` is true it writes `start`/`end` and occurrence seconds as `null`, keeps `start_bar`/`end_bar` and the hash, and adds `times_trusted`.
- **LAW**: pin-layer vs cell-layer (2â€“4 bar cell inside a figure, never a 40 s box), and GP7 is not a Guess marker clock (GP5 markers; GP7 only after deterministic export-to-GP5). Lab tests: **223 passed**.

### Figure hashes â€” riff identity, never keepers

- New `src/boo_lab/figures.py`: `hash_window` fingerprints a 2- or 4-measure window from riff_bank's per-measure fragments (chord-aware pitch-class sets, coarse 4-beat onset grid; octave/velocity ignored), `cluster_song` groups exact hashes (optional pitch-class Jaccard merge when windows carry `pcs`/`rhythm`) and letters `riff-A`, `riff-B`, ... by first start, and `build_figures` walks the matched GP5 in playback order, slices contiguous 2/4-bar windows, clusters 4-bar first then uncovered 2-bar, and writes `data/figures.jsonl` (`source="figure-hash"`) with the never-blank-on-zero-rows law. `load_figures` reads it back per song. CLI `boo-lab figures [--album X --track Y]` (album+track together) and studio `GET /api/figures/{track_id}` feed a `figure` datalist (no auto-fill, no `heard`). Reuses `extract._engine_riff_bank`, `sync._playback_order`, `schema.write_jsonl_atomic`; never touches `sections.jsonl`/`drafts.jsonl`. Lab tests: **216 passed** (9 new in `tests/test_figures.py`). *(Superseded: windowing is now runs, not sliding 2/4-bar windows, and there is no Jaccard merge â€” see the "Figure windows are runs" entry above.)*

### Studio copy tidy â€” pin then drag

- The empty-wave ghost now reads **"Press 1 for Riff"**; the coach's zero-box line and the How drawer both say pins/keys **create** a box and drag only fits it; the table foot no longer implies dragging creates a box. **Pack** shows `"Save keepers before Pack."` (as an error) when there are no boxes, leaving the fetch path untouched. Docs corrected: in-app **Undo** exists (button + Ctrl+Z, plus `sections.jsonl.bak` on Save), daily pinning is role + figure + start/end + heard only (`form`/`uniq`/`inst`/bars sit behind **More columns**), and the Play/clock/Play box/Save/Undo/How bar with **Lab** / **Corpus** holding the rest is documented. No math, no endpoints, no ids changed.

### Coach line, first-run How, duration gate

- **Live coach in `#err`.** `showErr` now fills the status bar with a contextual default when no explicit message is given: wait-for-clock (`ws` duration <2), `VAL â€” leave unpinned`, `Press 1 for Riff (drag moves a box; it does not create one).`, `N not heard â€” Save will drop them`, else `N boxes. Save writes keepers.` Explicit errors (save failed, Guess notes, dropped_unheard) are tagged and never overwritten; the row/clock observer refreshes the coach only when it is not explicit.
- **Duration gate.** `add()` refuses to draw before the clock shows the full length (`showErr("Wait. Clock must show the full length before you draw.", true)`), the same guard to reuse for any future enableDragSelection.
- **First-run How.** The drawer auto-opens once after tracks load; Close or the scrim stores `boo-lab-how-v1` so it never auto-opens again.
- **Small type fixes.** Clock placeholder is `0:00 / â€”` in the HTML and pre-ready; `WaveSurfer.create` height is 168 to match `#wave`; the table header reads `figure (riff-A)`; How step 2 says to press a role pin (or 1) then drag, and explains figure naming.

### Studio regression pass

- **Chrome verified, not redesigned.** All 46 `getElementById` targets resolve; `harvestTable` still reads every `data-f` field and `table()` still builds the extra `<td>`s (CSS hides them, DOM keeps them); keyboard shortcuts (Space, 1â€“4, I/B/C/P, S, N, J/K, Delete, Ctrl+Z, ?, Esc) are intact and skipped for `INPUT`/`SELECT`; filters, dropzone, stem buttons, spec pills, Snap beats, Save's `dur<2`/`end<=start`/all-tiny refusals, and Guess's `/api/estimate/{id}` merge are unchanged. No duplicate ids, no new network calls, no `/api/sync` from the browser, and a zero-track load returns cleanly. Inline JS passes `node --check`. Added one comment above `*` in `<style>` marking the chrome intent.

### Empty + waiting states

- **List reads at a glance.** Each song meta is now `FLAC Â· GP5` / `FLAC Â· GP7` / `FLAC Â· no tab` / `FLAC Â· partial GP5`, built from the existing `has_flac` / `has_gp` / `gp_partial` / `gp_kind`; a tiny `VAL` tag shows when `split==="val"`; a mute `tab off-clock` shows only if a track row already carries `sync_ok===false` (the field is absent from `/api/tracks` today, so it is skipped â€” no new fetch). Filter pills are a segmented All / GP5 / No tab control.
- **Empty wave ghost.** With a song selected, duration loaded, and no boxes, `#emptyghost` overlays the mix lane ("Press 1 for Riff" / "1 Riff  2 Hook  3 Breakdown  I Intro"); it vanishes on the first box. Pure HTML/CSS overlay, `pointer-events:none`.
- **Waiting signals.** The Lab summary carries a mute count of draft/guess rows; **Pack** is visually disabled (`.off` + `aria-disabled`) at zero boxes and its handler early-returns with "Save keepers before Pack."; Guess / Save / heard / Snap beats / VAL badge have hover `title`s.
- Corpus drop-zone copy states the ingest contract; lyric/stem lanes get 8px bottom padding. Frontend only â€” no FFT / beat-canvas or API change, all ids intact.

### Studio chrome restyle + More columns

- **Finished-instrument chrome.** App is a 280px rail | main grid with the spectrogram dock at 104px; the rail keeps album thumbs, the serif wordmark, and one quiet line ("Pick a song. Box a part. Tick heard. Save."); song rows are tighter (13px title / 11px meta) and the active song is a gold 2px left rule, not a slab. Work header is one strip (48px art, title, album, VAL badge).
- **Two-row transport.** Primary row is Play Â· clock Â· Play box Â· Save (filled gold) Â· Undo Â· How (â‰¤6 controls). A quiet second row holds `<details>` **Lab** (Guess, Load drafts, Lyrics, Pack, Snap beats, JSON, Next GP) and **Corpus** (drop zone + band name, Push git, Remove album). Role pins are their own equal-width row: 8px radius, coloured border only, fill at 12% on hover/active. Coach line is a full-width 13px bar; errors are breakdown red, never `alert()`.
- **More columns.** The table still holds every column and `data-f` attribute; `form` / `uniq` / `inst` / `bar0` / `bar1` / `source` start hidden (`display:none`) and **More columns** (`#btnMoreCols`) toggles `show-extra`. The How drawer is 400px and the dock gains a gold hairline. Restyle only plus that one small toggle â€” every `getElementById` id unchanged, no function body touched.

### Beat grid in the studio + Guess sync gate

- **Beat grid used.** New `GET /api/beats/{id}` serves `data/beats.jsonl`; the studio draws beat/downbeat ticks over the waveform and, with **Snap beats** (default on), snaps a dragged box edge to the nearest downbeat (â‰¤250 ms) else nearest beat (â‰¤120 ms). Previously `beats.jsonl` was written and never read.
- **Guess snaps to the grid.** Its audio-derived spans (half-time / kick breakdowns) are snapped to the nearest downbeat (â‰¤250 ms), else beat (â‰¤120 ms), from `data/beats.jsonl`.
- **Guess gates on sync.** `estimate_hybrid` now reads `data/sync.jsonl` for the song: if the tab was measured as **not** `sync_ok`, its marker sections are dropped with a note ("tab markers dropped: sync not ok â€¦ paint by hand"); if `sync_ok`, they're kept and the note says so. A tab known to misalign no longer silently supplies wrong times.

### Guess reads the tab's section structure

- `extract.estimate_from_gp` now walks the tab in **playback order** (repeats expanded) instead of once, and carries the marker's **section identity**: `form` = the letter (`A`/`B`/`C1`), `figure_id` = `role-token` (`riff-B`), and `unique` when the letter occurs once. A repeated letter (`02`'s `B`, `10`'s `A/B/F`, `12`'s `A/C/D`) now shows up as the *same returning section* rather than a fresh riff. The last box reaches the repeat-aware tab length (`_playback_duration`). The studio's Guess now uses those `form`/`figure_id`/`unique` fields instead of hardcoding `A`/`<role>-A`. Roles still come from `infer_role` (letters aren't roles; `C1 - Solo` â†’ solo).

### Hardening pass

- **Fail-closed keeper law, one reader.** `schema.is_keeper` is true only for `human`/`guess-accepted`
  (a missing/empty source is NOT a keeper); `canonical_role` returns `None` for unmappable input;
  `stamp_box` rejects an unknown role/source instead of defaulting to `human`. New
  `schema.load_section_rows(path, keepers_only=True)` is the single reader (used by
  `pack`/`drums_extract`/`vocal_melody`/`holdout`) and enforces the full law â€” `role` + keeper
  `source` + `heard is True`. Deleted the four twin readers, including the
  `source == "human" or role` precedence bug that accepted machine drafts as human labels.
- **Atomic, non-destructive files.** `schema.write_jsonl_atomic` (temp + fsync + `os.replace`) is the
  one writer. Every `sections.jsonl` write â€” Save, `hear`, album-remove â€” uses it; album-remove
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

- **Perfect tabs + faithful sync clock.** Official 02â€“13 A Higher Place GP5s placed in
  `gp5/A Higher Place/` (old Songsterr/musicnotes duplicates moved to `reference/gp-tabs-superseded/`).
  `sync.gp_onset_times` now: reads `song.tempo` (defaulting to 120 stretched every tab ~1.6Ã—),
  walks measures in **playback order** â€” `_playback_order` expands repeat-open/close and
  alternative endings â€” and advances by the same beat arithmetic as the onsets. GP clock matches
  audio length within ~2% for 10 of 13 (was 0.85â€“1.76Ã—). `catalogue._key`/scan now matches
  space-numbered `NN Title.gp5` (`07 Exist` had silently unmatched). `sync_ok`: 02/06/10 (was 0).
- **Lead-in outcome.** `best_alignment` now also returns peak **prominence**; sync passes an
  "aligned with offset" case when a peak is outside the 0.35 s zero window but within 5 s, scores
  â‰¥0.15, has prominence â‰¥0.05, and the other witness agrees on the offset (â‰¤0.25 s). Recorded as
  `offset_sec` / `ok (lead-in X.XXs)`. `13 - Faces Of Death` passes this way (both witnesses at
  âˆ’1.00 s); `05/12` don't (peak not prominent); `07/09/11` still fail as misalignment/data. `sync_ok`: 6 â†’ **7**.
- **Guitar-stem sync.** `sync` now prefers the cached 6-stem `guitar.wav` and falls back to the mix
  per witness (guitar-only broke `02`, which the mix gets right). `stems` now actually honors its
  long-parsed-but-ignored `--album` flag and skips already-cached tracks; ran it to cache guitar for
  all 13 A Higher Place tracks.
- **Sync chroma co-witness.** Added `gp_chroma` (tab pitches held over each beat) + `audio_chroma`
  (`chroma_cqt`) + `chroma_lag_and_score`; `sync.jsonl` records `chroma_lag`/`chroma_score` and
  `sync_ok` passes if **either** the onset or chroma witness aligns. Rescued `03` (onset 1.21 s vs
  chroma 0.16 s) â€” `sync_ok` 5 â†’ **6**. `07/09/11` still fail (chroma lag 1.9â€“2.5 s / low score).
- **Sync metric.** `best_lag_and_score` now blurs both envelopes (~120 ms) before correlating, so an
  onset only has to land near a tab note instead of exactly on it. Wrong-peak lags collapsed
  (13: 64 sâ†’1.0 s, 11: 116 sâ†’4.5 s, 05: 6.1 sâ†’1.0 s). Added `best_clock_fit` (clock-rate search) as
  a `clock_ratio` **diagnostic** â€” deliberately not used to override the raw peak, since on a tab
  that's short because a section is missing it finds bogus rates. `sync_ok`: 3 â†’ **5** (02/04/06/08/10).
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
  `boo_lab.egg-info` untracked. Tests: `test_natten_compat`, `test_device`, `test_doctor` â†’ 177.

## 2026-09-17

- **Keeper schema.** `schema.py` is the single source of truth (roles, figure/function layers, `SOURCES`, `is_keeper`, `stamp_box`, `same_role_overlaps`). Studio Save writes keepers only (`human`/`guess-accepted` + `heard`), drops unheard/`guess`/`msa-draft`, stamps a heard draft `guess-accepted`, rejects same-role overlap >50 ms, preserves extras; `GET /api/drafts`; tables carry role/figure/start/end/source/heard; **Load drafts** appends `msa-draft`/`guess` unheard.
- **Old pins.** `boo-lab hear --album X --track Y` flips `heard=true` on already-keeper rows for one track only (never the whole catalog).
- **Drafts.** `structure` writes `data/drafts.jsonl` only (allin1 â†’ `msa-draft`; SongFormer when `SONGFORMER_HOME`/import â†’ `songformer-draft`); `audit` command; keeper filtering in `pack`/`extract`; env-aware GP roots (`BOO_GP_ROOT`).
- **Research outputs.** `agree` (two-pass keeper diff, HR 0.5/3 + role/figure agreement), `compare` (drafts vs keepers, per-source rows, precision/recall/F 0.5/3 + role agreement, marks `split=holdout`), `export-jams` (JAMS 0.3 figure/function layers), `beats` (beat_this â†’ allin1 fallback, `data/beats.jsonl`). Optional `intern` extra.
- **Audio pipeline.** Demucs default is 6-stem `htdemucs_6s` (guitar/piano isolated; Pack slices them, no-vox mixed from 6); `audio_extract` audio fallback (`source_type=audio_transcribed`); drum `low_confidence` flag; corpus `report`/`corpus_health.json`; train/val `holdout.csv` + `split` on every output.
- **Riffs.** `RiffFragment` gains `instrument`, `source_type`, `chord_notes`, `chord_frets`; cell hits carry real `palm_mute/harmonic/slide/tremolo/vibrato/accent`; categorized riff-bank failure reasons.
- **Vocals/lyrics.** Vocal melody via CREPE (pyin fallback); plain LRCLIB lyrics display + WhisperX **force-alignment of the provided words**; LRCLIB lookup fixes (space-numbered tracks, retries, no-duration fallback).
- **Studio.** Canonical roles, guarded Remove-album, 6-stem picker (`GET /api/stem`), per-song VAL badge, drum-confidence note (`GET /api/analysis`), flac fallback, safe album+track id resolution; `test_*` suite (136 tests) + `pyproject.toml` pytest config.
- **Box identity.** `stamp_box` gains `form` / `unique` / `instrument` / `start_bar` / `end_bar`; Save passes them through and fills GP bars only when `match=yes` (`extract.bars_for_times`, never blocks); studio columns `form / uniq / inst / bar0 / bar1`.
- **Map witnesses.** `map.csv` gains `flac_sha256` (`scan` hashes on rewrite, `boo-lab hash` fills empties; unknown columns preserved); `boo-lab sync --album --track` scores the GP onset clock vs the audio envelope and writes `data/sync.jsonl` (`sync_ok` iff `|lag| < 0.35 s` and score â‰¥ 0.15).
- **Studio spectrogram.** Real JS mel spectrogram drawn from the already-decoded WaveSurfer buffer (no second fetch, no deps): synced playhead, click-to-seek, section-box overlays, Wave/Spec/Both toggle. Tests: 153.

## 2026-09-14

- Save: harvest table first; refuse empty `0â€“0.25` boxes; wait for wave duration.
- Play box: stop at region end.
- Riff colour vs grey wave (riff was the same gold as the waveform).
- Guess: `_scalar` / `_flist` for librosa+numpy2; kicks no longer die when BPM fails.
- gitutil: do not add `work/`; ignore CRLF + gitignore hints; push without captured stdout so GCM can run.
- Ingest: copy artwork; walk dropped folders; keep album paths; infer band from `Band - Album - Year` and `Band-Song.gp5`; write new bands under `audio-corpus/<band>` not `born_of_osiris/new_band`.
- Catalogue scan: one GP per track; fuzzy title; strip Songsterr ids / â€œofficial tabâ€; short titles need a tighter score.
- Docs: README, LAW, STATUS, CHANGELOG, `.env.example`, CATALOG header, **CURRENT.md**.

## 2026-09-13

- Studio UI, Demucs-on-demand drums, lyrics LRC, Pack, ingest endpoint, album grouping.
- Commit `6482c30` on `z2wgv7dc4h-alt/1222`: guess BPM fix, save harvest, riff colours.
