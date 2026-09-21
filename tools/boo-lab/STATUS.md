# Status — 2026-09-18

Canonical detail: **CURRENT.md**; commands in **README.md**.

<!-- status:counts:start -->
## Counts (from disk)

- keepers: 6 row(s) across 1 track(s)
- drafts: 1450 row(s); sources: msa-draft, songformer-draft
- sync: 14 ok / 52 row(s)
- map.csv: 83 row(s)
<!-- status:counts:end -->

Works: studio keeps pins (`human`/`guess-accepted` + `heard`) in `sections.jsonl`; mel
spectrogram under the WaveSurfer waveform; 6-stem picker; drafts; `hear`/`sync`/`hash`;
`agree`/`compare`/`export-jams`/`beats`/`audit`/`report`; **361 tests pass**.
Multi-guitar tracks (2026-09-21): a tab-notes pack can carry more than one
`guitar`-category track (checked on a real corpus song: three, mean pitches 51.7/
50.1/46.6 — too close together to be a real rhythm/lead register split, so no
"lead" guessing). `figures.py` now clusters every extra guitar track on its own
(`guitar<index>-` figure_id prefix + a `track_index` field), instead of silently
discarding everything but the single lowest-mean-pitch track.
Tabnotes bass/pulse/tempo/kick (2026-09-21): `figures.py` now clusters a tab-notes
pack's `bass`-category track too (same RUNS/cluster machinery as guitar, `bass-`
figure_id prefix + `instrument` field so a bass riff can never collide with a guitar
one sharing a letter), decoupled from guitar-cluster success so either instrument can
produce rows on its own. `_tab_pulse_windows` turns a pack's `other`-category track
(a named synth/keyboard, LAW.md's Pulse) into `role="pulse"` draft rows — no GP-side
equivalent, tabnotes-only. New `tempo_hints.py`/`data/tempo_hints.jsonl`
(`boo-lab tempo-hints`) surfaces a pack's tempo-automation BPM changes as an
informational note in Guess's output, never an auto-created box — a tempo bump
correlates with a section change but never implies a role. `guess.py`'s breakdown
detector now prefers real kick onsets from a pack's own drum notation (GM pitch 36,
verified against a real corpus pack: 600 of 1311 drum events) over the spectral-guess
`_kick_spans`, whenever `sync_ok` is true; falls back to the audio heuristic otherwise
so a song without a pack is unaffected. All four additions are read-only/draft-only —
nothing here writes `sections.jsonl`.
GP7/GPIF (2026-09-18): `boo_lab/gpif.py` reads a `.gp`/`.gpx` `score.gpif` natively
(flat GP8/alphaTab + nested), exposing title/artist/album, tracks (tuning, instrument,
capo), masterbars (time sig/repeats/sections/tempo), beats (dynamic/chord/text) and notes
(voice, string/fret/duration, computed `midi`, articulations). `sync` prefers a matching
`.gp/.gpx` over a `.gp5` sibling and clocks it via `gpif.note_events` (seconds first);
`.gp5` stays guitarpro. No GP5 conversion (`gpif_to_gp5` unused).
Matcher (2026-09-18): `catalogue._key` strips a space-numbered track prefix and the band
prefix in any punctuation; `_gp_candidates` scores each GP (exact > substring, lead-number
bonus, GP7 `.gp`/`.gpx` bonus over `.gp5`, shorter name) and `scan_roots` assigns one GP
file to one FLAC. The full GP7 packs for Discovery / A Higher Place / Eternal Reign live
under `gp-tabs/gp7/<band>/<album>/` and win; `map.csv` is 83 rows / 66 `match=yes`.
Interns pass (2026-09-18): `boo-lab interns [--album X] [--steps a,b,c]` runs the whole
chain in order (`stems → beats → structure → drums → vocals → lyrics → sync → extract →
figures → compare → learn → status`), cache-first and resumable — `structure` reuses
`work/msa/<track>.json` / `.songformer.json`, `beats`/`sync`/`lyrics` skip finished rows —
and each step is isolated so one failure never aborts the rest. Never writes `sections.jsonl`.
Learn (2026-09-18): `boo-lab learn` ranks the draft sources from keepers (5-song vote, F@0.5 >= 0.50,
0.03 margin, holdout excluded) into `data/intern_rank.json`; the `enough_to_train` stub is gone and
it still never writes keepers. Current keepers are Rebirth-only, so `prefer=none`.
Studio (2026-09-18): per-album adapt calibrates intern drafts (Guess application + structure write +
`GET /api/drafts`), a changed draft carries an `adapt` stamp (never a keeper source), Guess proposes
figure windows when `sync_ok`, Guess refuses a song that already has heard keepers (`409`), the
selected `#list` row is highlighted (`.on` + `aria-current`), and the Lab summary shows `prefer=…`
from intern_rank. Operators start at `USER.md`. Still 6/Rebirth keepers.
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

Studio/Guess (2026-09-18): the studio draws **beat/downbeat ticks** from `data/beats.jsonl` and, with
**Snap beats**, snaps a dragged box edge to the nearest downbeat (≤250 ms) else beat (≤120 ms). Guess
now carries the tab's **section identity** (marker letter → `form`/`figure_id`/`unique`, repeats
expanded in playback order), **gates** its marker sections on `sync_ok` (drops them when the tab was
measured as misaligned), and **snaps** its own half-time/kick spans to the beat grid. Raw-note content
segmentation was prototyped and **rejected** (795–1057 sections vs 143 markers, precision 0.15) — the
tabs' marker letters plus the allin1 drafts are the real riff signal. Studio chrome is now a rail |
main layout with a two-row transport (**Lab** / **Corpus** `<details>`), equal-width role pins, and a
**More columns** toggle (`form` / `uniq` / `inst` / `bar0` / `bar1` / `source` hidden by default) —
restyle only, all ids and behavior unchanged. Waiting states: rows read `FLAC · GP5/GP7` / `no tab` /
etc. (+ `VAL` tag), an empty wave shows a "Press 1 for Riff" ghost, and the Lab summary counts
draft rows while **Pack** is greyed until boxes exist. Ghost copy and How now match "pin then drag"
(pins/keys create a box; drag fits it); Pack refuses with "Save keepers before Pack." when there
are no boxes. Figures (2026-09-18): `boo-lab figures` hashes 2/4-bar GP windows, clusters repeats
inside one song, and suggests `figure_id`s to `data/figures.jsonl` (`source=figure-hash`, drafts
only — never `sections.jsonl`); the studio offers them as a `figure` datalist. Regression pass
(2026-09-18): all 58
`getElementById` ids resolve, `harvestTable` reads every `data-f`, shortcuts/filters/dropzone/stems/
spec/Snap/Save/Guess unchanged, no dup ids and no new network calls; `node --check` clean.
The `#err` bar is now a live coach (wait-for-clock / VAL / "Press 1 for Riff" / unheard / box
count) that never overwrites explicit errors; `add()` refuses before the clock is ready; How
auto-opens once (`boo-lab-how-v1`); clock placeholder is `0:00 / —`. The wave is 240px with **one
lane per role** (a box sits only in its role's lane, so stacked parts show at once); click a bar to
select its row and vice-versa, right-click it to edit role/figure/heard/unique/inst + Play box /
Split at playhead / Delete, double-click toggles heard, and the All/Figures/Functions pills only
hide (Save still harvests hidden rows).

On disk now:
- `data/sections.jsonl` — 6 rows, 1 track (Rebirth), all `heard=true`. The whole keeper set.
- `data/drafts.jsonl` — 1450 rows across all albums (`msa-draft` + `songformer-draft`, GPU).
- `data/beats.jsonl` — 58 tracks (`beat_this` preferred).
- `data/compare.json` — drafts vs keepers. Rebirth (holdout): **F0.5=0.737 F3=0.800 role3=0.250**.
- `data/sync.jsonl` — **14 `sync_ok` / 52 rows** across all albums. `sync`
  prefers the cached **guitar** stem and **falls back to the mix per witness** (isolated guitar can
  mis-peak where the mix doesn't and vice versa). Two witnesses score alignment: a blurred (~120 ms)
  **onset** correlation, and **chroma** (tab pitches sustained vs `chroma_cqt`). `sync_ok` passes if
  either witness on either source is within 350 ms at score ≥0.15; `used_stem`, `clock_ratio`,
  `chroma_lag`, `chroma_score`, `offset_sec` are recorded. An **aligned-with-offset** outcome also
  passes: a peak outside the 0.35 s zero window but within 5 s, with score ≥0.15, **peak prominence**
  ≥0.05, and the other witness agreeing on the offset within 0.25 s. A `.gp`/`.gpx` is clocked from
  its parsed GPIF score (no conversion), and a `.gp5` row prefers a matching `.gp`/`.gpx` sibling.
Read the live `sync_ok` count from `data/sync.jsonl` — never type 14/52 from memory.
- `data/agree.jsonl` — Rebirth pass 1 (6 boxes). Pass 2 needs a human re-pin, then
  `boo-lab agree --album X --track Y --diff`.
- `data/map.csv` — 83 rows, 66 `match=yes` (Discovery/AHP/Eternal Reign full GP7; no GP
  matched to two tracks; the +12 are Veil of Maya `2015 - Matriarch` tracks from an ingest,
  whose FLACs sit in `audio-corpus/01..12/`); `flac_sha256` only once `scan`/`hash` runs.
- `data/holdout.csv` — 7 songs reserved. `engine/data/riff_bank.json` is local/gitignored.

Sync (2026-09-18): the existing `best_clock_fit` rate fit is wired into `sync_ok` — the resampled
onset lag must pass `decide` and the chroma witness must agree within 0.25 s at that ratio;
`clock_ratio` is always recorded and the ~2.7% drift class can pass while 20% still fails. Figure
rows omit `start`/`end` seconds unless the song's `sync_ok` is true.

Pytest proves wiring. It does not prove a riff.
