# CURRENT — read this first (2026-09-18)

Single source of truth for humans and later bots. If README/STATUS/LAW disagree with this file, this file wins. Then fix the others.

Operators start at `USER.md` (Part A to work, Part B for every button and file).

Living docs are `USER.md` / `LAW.md` / `CURRENT.md` / `README.md` / `STATUS.md` / `CHANGELOG.md` only.

> **Read this first.**
> Keepers = `data/sections.jsonl` (`source=human`/`guess-accepted` **and** `heard=true`).
> Drafts = `data/drafts.jsonl` (`msa-draft` / `songformer-draft` / `guess`) — **never keepers**.
> Box fields: `start end role layer form figure_id unique instrument start_bar end_bar source heard`.
> Studio table columns match those; waveform is WaveSurfer, with a real mel spectrogram below it (Wave / Spec / Both).
> `structure` writes `drafts.jsonl` only. `hear` and `sync` require **both** `--album` and `--track`.
> `hash` fills `flac_sha256`; `sync` writes `data/sync.jsonl` (`sync_ok`/`lag_sec`); `beats` → `data/beats.jsonl`.
> Every `sections.jsonl` write is atomic; Save keeps `data/sections.jsonl.bak`, reports `dropped_unheard`, and rejects bad boxes/roles/sources (fail closed).
> Holdout songs stay unpinned. GP7 `.gp`/`.gpx` is read natively (parsed GPIF) and preferred over `.gp5`; no conversion.
> One album side per session. Default install is thin; interns (allin1 / beat-this / SongFormer) are optional.
> Machines may draft. They never label.
> Interns run on **GPU when present** (`boo_lab/device.py`); `boo-lab doctor` must print `cuda=True`.
> New machine: `setup.bat --flac <CORPUS> --gp <GP_ROOT>` then `boo-lab doctor` (green).

## What this is

A **section lab** for metal FLACs (Born of Osiris first, other bands via ingest). Human output is `data/sections.jsonl` — **keeper pins only** (`source=human`/`guess-accepted`, `heard=true`), each with a figure/function `layer` and a `figure_id` — plus optional Pack clips under `work/` (gitignored). Machines write `data/drafts.jsonl` (MSA/SongFormer/Guess) and never keepers. It is not God Tier Metal, not a DAW, not a tab reader, not an auto-songwriter.

GitHub: `https://github.com/z2wgv7dc4h-alt/1222` path `tools/boo-lab`.  
Newest lab commit: `0a98c31` (sync clocks GP7 via GPIF, preferring a `.gp/.gpx` over a sibling `.gp5`); before it `e2a5dee` (GPIF notes: midi/voices/articulations/tempo map), `42d47f6` (GPIF→GP5 writer + GPIF sync fallback), `7dfdfe1` (parse `score.gpif`), `9fca6e6` (START.bat runs hash + beats/sync), `5df12ab` (one resumable `interns` pass), `a21bc29` (`hash` fills `flac_sha256`), `21c54ea` (JAMS from studio).

## Paths

```
LAB     C:\Users\RIGGUSPIG\Desktop\god-tier-metal\tools\boo-lab
CORPUS  C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\audio-corpus
BOO     ...\audio-corpus\born_of_osiris
GP      C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\gp-tabs
        gp5\<band>\   GP4/GP5 / old GP text header
        gp7\<band>\   .gpx / modern .gp
```

`BOO_FLAC_ROOT` = **CORPUS** (`audio-corpus`).  
If it is set to `born_of_osiris`, ingest puts Veil of Maya at `born_of_osiris\new_band\...`. That already happened once. Move it.

## Start

```
cd C:\Users\RIGGUSPIG\Desktop\god-tier-metal\tools\boo-lab
.venv\Scripts\activate
set BOO_FLAC_ROOT=C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\audio-corpus
set BOO_GP_ROOT=C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\gp-tabs
python -m boo_lab.cli scan
python -m boo_lab.cli hash
python -m boo_lab.cli interns --steps beats,sync
python -m boo_lab.cli studio --port 8765
```

`START.bat` runs those four in order. The `interns --steps beats,sync` pass is
resumable and skips songs already on disk.

http://127.0.0.1:8765 — Ctrl+Shift+R after HTML. Restart the process after `.py` changes. One server.

GPU check (do this before trusting any intern): `python -m boo_lab.cli doctor` — it must print
`cuda=True` + the GPU name. `doctor` also names any missing intern/extra and the exact install.
Interns (allin1 / beat_this / torchcrepe) read `boo_lab/device.py`; they never hardcode CPU.

## Data written

| path | what |
|---|---|
| `data/map.csv` | scan result: album, track, flac path, gp path, match, `flac_sha256` |
| `data/sections.jsonl` | **keeper** boxes only. Save **replaces** that track’s rows, keeps other tracks; one-step undo copy at `data/sections.jsonl.bak` |
| `data/drafts.jsonl` | machine drafts (`msa-draft`, `songformer-draft`, `guess`). Never keepers |
| `data/holdout.csv` | fixed whole-song train/val reservation (`ensure_holdout`) |
| `data/agree.jsonl` | two-pass keeper snapshots (`boo-lab agree --write`), pass 1/2 |
| `data/compare.json` | drafts-vs-keepers report (`boo-lab compare`) |
| `data/beats.jsonl` | beat/downbeat grid (`boo-lab beats`) |
| `data/sync.jsonl` | tab-vs-audio witness (`boo-lab sync`): `sync_ok`, `lag_sec`, `score` |
| `data/corpus_health.json` | pipeline state (`boo-lab report`) |
| `data/rebirth-sections.jsonl` | reference labels for Rebirth |
| `work/stems/` | Demucs cache, 6-stem `htdemucs_6s` preferred (gitignored) |
| `work/msa/` | raw allin1/SongFormer payloads (gitignored) |
| `work/drop/`, `work/pack/`, `work/jams/`, `work/lyrics/` | outputs (gitignored) |

Never commit FLACs, GP, stems, zips, tokens, `.venv`.

## Roles

intro, build, riff, hook, breakdown, solo, chill, pulse, outro.

- Different roles **may overlap**. Same role on the same span = merge or split.
- **Riff** = guitar figure. Repeats stay one box unless the figure changes.
- **Breakdown** = function (usually drums half-time / pit). Can sit on the **same** guitar as a Riff.
- **Pulse** = a *named* synth/keyboard loop (hummable). Not “keys are in the mix.” New figure = new Pulse. Repeats of that figure stay one box. Do not paint Pulse over Build/Outro just because pads continue.
- **Chill** = energy sit-down, not “quiet intro.”
- **Build** = rise that is not the hook itself.
- **Intro** on an instrumental album door (Rebirth) may span the whole file; Pulse/Build/Outro layer on top.

Layers and provenance:

- Figure roles (`riff hook solo pulse`) and function roles (`intro build breakdown chill outro`) **may overlap each other**; two boxes of the **same** role overlapping by more than 50 ms is rejected on Save.
- `figure_id` defaults to `"{role}-A"`; a returning figure keeps the same `figure_id`.
- `source`: `human` / `guess-accepted` are keepers; `guess` / `msa-draft` / `songformer-draft` are drafts.
- `heard`: only boxes you actually listened to. Save writes keepers only (`source` keeper **and** `heard=true`); unheard boxes are dropped. This is why old pins need `boo-lab hear` first.

## Rebirth (A Higher Place, 86.63s)

Energy + flux from the user’s FLAC (not a published piano score — none exists). Joe Buras keys; comments compare it to Final Fantasy / *The Takeover* ending.

```
intro  0.00–86.63
pulse  13.00–27.80     first theme; hits ~every 3.25s. Do not start at 20.
pulse  33.00–41.50
pulse  46.20–51.00
build  52.80–66.50     dense, not spaced loops
outro  69.50–86.63
```

Leave 28–33, 51–53, 66.5–69.5 empty. No Breakdown. No Guess after these are saved.

If Save ever wrote six `0.00–0.25` rows, the pins fired before duration loaded — only possible on an old build, since the current Save **refuses** `end <= start`. Recover via `data/sections.jsonl.bak`, or paste the lines above into `sections.jsonl` and reload.

## UI contract

- Left: albums collapse, cover thumb if `cover.jpg` / `folder.jpg` / `Cover/` / Cyrillic `Сover.jpg` sits next to FLACs.
- Green GP5 = matched tab. Partial only if notes/name say stub/fragment/bass-only.
- Mix lane: drag boxes. Click empty wave to seek. Clicking a box edge should not steal the next pin — leave a gap or seek first.
- Spectrogram: real mel spectrogram of the already-decoded buffer under the mix; **Wave / Spec / Both** toggle (default Both), click to seek, current boxes overlaid. Waveform stays WaveSurfer.
- Stem lane: pick any cached Demucs stem (drums/bass/guitar/piano/other/vocals); the drum-confidence note flags sections the classifier is unsure about.
- Beat grid: `GET /api/beats/{id}` (from `data/beats.jsonl`); the studio draws faint beat / brighter downbeat ticks over the waveform, and with **Snap beats** on, a dragged box edge snaps to the nearest downbeat (≤250 ms) else nearest beat (≤120 ms). Run `boo-lab beats` first, else no ticks/snap.
- Chrome: 280px rail | main; work header is one strip (48px art, title, album, VAL badge) over a two-row transport. Primary row is Play · clock · Play box · Save (filled gold) · Undo · How; the quiet row holds **Lab** and **Corpus** `<details>` — Lab = Guess, Load drafts, Lyrics, Pack, Snap beats, JSON, Next GP; Corpus = drop zone + band name, Push git, Remove album. Role pins are a separate equal-width row (coloured border only, 12% fill on hover). The 104px spectrogram dock has a gold hairline; the How drawer is 400px.
- At a glance: song rows read `FLAC · GP5` / `GP7` / `no tab` / `partial GP5` (plus a tiny `VAL` when the split is val); filter pills are a segmented All / GP5 / No tab. With no boxes and the duration loaded, the mix lane shows a ghost "Press 1 for Riff" (gone after the first box). The Lab summary counts draft/guess rows; **Pack** is greyed at zero boxes (`aria-disabled`) and tells you to Save keepers first. Hover hints on Save / Guess / heard / Snap beats / VAL. `tab off-clock` appears only if a track row exposes `sync_ok===false` (not on `/api/tracks` today).
- Coach: with no explicit message, `#err` becomes the next-step coach — wait-for-clock (`ws` duration <2), `VAL — leave unpinned`, "Press a role pin (or 1 for Riff) — pins create boxes; drag fits them.", "N not heard — Save will drop them", else "N boxes. Save writes keepers." Explicit errors are never overwritten. `add()` refuses before the clock shows the full length; the clock placeholder is `0:00 / —`; the How drawer auto-opens once (Close/scrim writes `boo-lab-how-v1`).
- Role pins / keys create boxes; drag only moves or resizes. In-app **Undo** (button or Ctrl+Z) plus `data/sections.jsonl.bak` on Save.
- Table is source of truth on Save (`harvestTable`); columns role / figure / form / uniq / inst / bar0 / bar1 / start / end / source / heard. `form` / `uniq` / `inst` / `bar0` / `bar1` / `source` start hidden; **More columns** (`#btnMoreCols`) toggles `show-extra`. Every column and `data-f` still harvests. Blur number fields before Save.
- **Heard** gates the save: untick it and the box is dropped. A heard draft saves as `guess-accepted`.
- **Every write to `sections.jsonl` is atomic** (`schema.write_jsonl_atomic`): Save, `boo-lab hear`, and album-remove all use temp + `fsync` + `os.replace`, so a crash/full disk/aborted write leaves the file intact. Album-remove parses the file *before* deleting anything and aborts (400, nothing removed) on a malformed line; `hear` likewise refuses rather than drop a malformed line.
- **A bad box rejects the whole save** with 400: `end <= start`, non-numeric/non-finite `start`/`end`, a non-object row, a box whose role maps to none, or an unknown/missing `source`. Never repaired into a `0.25s` box (Bugs #2), never defaulted to a human keeper.
- **Fail closed**: `schema.is_keeper` is true only for `human`/`guess-accepted` (missing/empty source is NOT a keeper); `schema.canonical_role` returns `None` for unmappable input; and `schema.load_section_rows` (the one reader for pack/drums/vocals/holdout) keeps a row only when `role` + keeper `source` + `heard is True` — the full keeper law. Every non-keeper source promotes to `guess-accepted` once Heard (derived from `SOURCES - KEEPER_SOURCES`).
- A **malformed line already in `sections.jsonl`** is skipped and counted, not fatal: the response carries `malformed_lines_skipped` and `malformed_line_numbers`.
- Save is **not silent about drops**: the response carries `dropped_unheard` (unheard boxes discarded) and `malformed_lines_skipped`, and the studio shows both.
- **One-step undo**: before each Save the previous file is kept as `data/sections.jsonl.bak` (`*.bak` is gitignored). The studio refuses a box with `end <= start` (never auto-repairs it to `0.25s`).
- **Load drafts** appends `data/drafts.jsonl` rows unheard; **VAL** badge marks holdout songs.
- Play = whole track. Play box = selected region only.
- Guess merges drafts if boxes already exist; do not Guess a finished song.
- Lyrics: click line to seek (incl. force-aligned plain lyrics); ±0.2 nudge; Save lyrics.
- Remove album: deletes one album's FLAC/GP under the configured roots, drops its pins/holdout, rescans. Confirm required.
- Drop zone: zip or folder. Type band first. No RAR.
- Push git: best-effort. Cmd is the real backup.

Shortcuts that exist in the page (also shown under How): pins I/R/H/B/S/C etc. as wired; Space play. If `C` fires Chill, that is the pin, not a secret mode.

## Guess pipeline (order)

1. Prefer GP5 on disk (`gp-tabs/gp5`, name match).
2. `extract.estimate_from_gp` walks the tab in **playback order** (repeats expanded): one box per marker, and it carries the tab's own **section identity** — `form` = the marker letter (`A`/`B`/`C1`), `figure_id` = `role-token` (`riff-B`), `unique` when that letter occurs once. A repeated letter (e.g. `02`'s `B`, `10`'s `A/B/F`) is therefore the **same returning section**, not a new riff. The last box reaches the tab's repeat-aware length (`_playback_duration`).
3. Markers name a section letter, not a semantic role, so the role comes from `infer_role(marker)` and otherwise stays `riff` (`C1 - Solo` → solo). The human still picks hooks/breakdowns/etc.
4. Demucs drums stem into `work/stems/` (first time slow).
5. librosa beat_track on that stem. Tempo must go through `_scalar` (numpy 2 `float(array)` crash used to abort here).
6. Half-time IOI (~1.65× median, ≥6s) → breakdown drafts.
7. Kick band <140 Hz IOI ≥5s → breakdown drafts.
8. Audio-derived spans snap to the beat grid (nearest downbeat ≤250 ms else beat ≤120 ms) when `data/beats.jsonl` has the song.
9. `_clean` short/overlap junk.

Audio can only ever propose **breakdowns** (half-time/kick); everything else is tab-marker or the human.

If it says `librosa beats, no half-time`, drums ran and found no slam — correct on Rebirth, common on mid-tempo grooves.

Guess is **not** a BoO brain. It carries the tab's section letters and repeats, but a letter is not a role — the human paints hooks/breakdowns and the tail the tab doesn't notate.

**Rate-aware markers.** When the song's `data/sync.jsonl` row is `sync_ok` with `clock_ratio` off 1.0
by ≥0.002, Guess scales every tab-marker `start`/`end` by that ratio before the rest of the pipeline
(the existing beat snap still applies afterwards), and prints
`guess: clock_ratio=1.027 stretched N markers`. `clock_ratio` None/~1.0 (±0.002) leaves times
unchanged; `sync_ok` false (or no row) still drops the markers. Audio-derived breakdown drafts are
never stretched — they already live on the FLAC clock.

Guess refuses a **finished** song (any heard keeper already on the track → `409`, no new drafts);
a draft changed by `apply_adapt` carries an `adapt` stamp (`shift`/`role`/`figure`, never a keeper
source), the Lab summary shows `prefer=…` from `intern_rank.json`, and the selected `#list` row gets
`.on` + `aria-current="true"` on every render (gold rule, warm wash, focus ring).

## Figures (riff identity, never keepers)

`boo-lab figures [--album X --track Y]` fingerprints each bar (`bar_fp`:
quantized 1/8 onsets + `deltas` + pitch-class sets) and windows are **runs** —
a maximal run of equal bars is ONE ostinato window, never sliding 2/4-bar
windows. Windows cluster by exact fingerprint and are named by a consistent GP
marker letter (`{role}-{letter}`) else `riff-A/B` by first start; a letter that
maps to two fingerprints is flagged `conflict=true`. It names bars that already
exist as measures — identity, not segmentation; it never cuts new boxes and
never invents boundaries. Rows land in `data/figures.jsonl` with
`source="figure-hash"` — a draft that never writes `sections.jsonl`/
`drafts.jsonl` and never ticks `heard`. `--album` and `--track` must be passed
together. The studio reads it at `GET /api/figures/{track_id}` to fill a
`figure` datalist (no auto-fill, no Save of hashes); a conflict raises one coach
line, "Tab letter maps to two figures — pick in the box."

## Ingest

Copies:

- audio `.flac/.wav` → `audio-corpus/<band>/<album>/`
- art `.jpg/.jpeg/.png/.webp/.gif` → same album folder
- GP5/GP4/GP3 / old `.gp` with `FICHIER GUITAR` header → `gp-tabs/gp5/<band>/<album>/`
- `.gpx` / other `.gp` → `gp-tabs/gp7/<band>/`

Band inference:

- Typed box wins unless it is `new_band`.
- Folder `Veil Of Maya - Matriarch - 2015` → band `veil_of_maya`, album `2015 - Matriarch`.
- File `Veil_Of_Maya-Mikasa.gp5` → band + title.
- If `BOO_FLAC_ROOT` is a single-band folder and the inferred band differs, write to **parent**/`<band>` (sibling of BoO).

Then `scan` rebuilds `map.csv`.

## Scan / matching

- Do **not** rename FLACs.
- Strip track numbers, Songsterr `s12345`, words like official/tab/guitarpro.
- Split `Band-Song` / `Band_Song`.
- Unique assignment: one GP file → one FLAC, best score first.
- Short titles (`XIV`, `Exist`) need a high score.
- `no tab` = no file, or title is `track02`. Rename the **tab**.

BoO rip folders that lie (Discovery living under “Soul Sphere”, Simulation under “FYE Discovery”) — `data/CATALOG.md`. Skip Misha mix FLACs for the bank.

## Extract / cell layer

`boo-lab extract` writes **one representative cell per `figure_id`** to `data/riffs.jsonl` — the
shortest repeating cell inside that figure (2, 3, or 4 bars), preferring the hashed window in
`data/figures.jsonl` when `n_hits>=2`; every other hit is only a pointer (`occurrences` bars,
seconds only when `times_trusted`). An 8-bar human `riff-A` box becomes a 2-bar cell, never an 8-bar
bank fragment. Zero cells never blanks an existing file.

## Interns pass (one command)

`boo-lab interns [--album X] [--steps a,b,c]` runs the whole chain in order —
`stems beats structure drums vocals lyrics sync extract figures compare learn
status` — over the `map.csv` rows (album-filtered). Every step is independent:
a failure is recorded as `{"error": …}` and the rest still run, so a re-run
resumes. It skips finished work (`beats` / `sync` / `lyrics` already on disk;
`structure` reuses cached `work/msa/<track>.json` + `.songformer.json` instead
of re-running allin1/SongFormer). `compare` writes `data/compare.json` then
`learn`; `extract` shells `boo-lab extract --album`. It never writes
`sections.jsonl`/keepers. Step functions live in `src/boo_lab/interns.py`;
`structure.build_drafts` reads its cache first.

## GPIF reader

`boo_lab/gpif.py` reads a GP7/GP6 `.gp`/`.gpx` **score** from the zip without
converting (`open_gp` needs `Content/score.gpif`; flat GP8/alphaTab and the
nested fixture both parse). `GpifScore`: `title`/`artist`/`album`/`tempo`,
`tracks` (name, `tuning_midi`, instrument, capo), `masterbars` (time sig,
repeat map, section, tempo), `beats` (dynamic/chord/text) and `notes` — **every
Voice** in a Bar, with string/fret/duration/`voice`, `midi = tuning_midi[string-1]
+ fret` (None out of range), `palm_mute`/`dead`/`accent`/`hammer`/`slide` +
`articulations`. Helpers: `tempo_map` (`(unexpanded beat, bpm)`, drives
`duration_sec`), `time_sig_map`, `section_list`, `playback_bar_order`,
`playback_beats`, `note_events` (`(seconds, midi, duration_sec, palm_mute)`;
seconds first so `sync`'s GPIF clock keeps working). CLI `gpif` adds
`n_with_midi`. No `sections.jsonl`; fixture `tiny.gp` is hand-made.

## Sync clocks GP7 (GPIF) first

When a row's `gp` is a `.gp5`, `sync_track` looks for a matching `.gp`/`.gpx`
(same normalized stem, ignoring `07 -` vs `07 `) beside it or under
`BOO_GP_ROOT/gp7`, clocks that path, and records it in the sync dict `gp`
(the note gains `· gpif`). `_tab_notes` / `_tab_play_seconds` read a
`.gp`/`.gpx` via `gpif.load_score` + `note_events` / `duration_sec` FIRST
(never `guitarpro.parse` first, never a conversion); `.gp5` still goes through
`guitarpro.parse`. LAG 0.35 / SCORE 0.15 and the rate path are unchanged; no
GP5 files are deleted and `map.csv` is not rewritten. `gpif_to_gp5` stays
unused. No `sections.jsonl`.

## Learn (intern rank)

`boo-lab learn [--album X]` rebuilds `data/intern_rank.json` from `compare.compare()` (never a
second F@0.5) and appends events to `data/learn.jsonl`. A draft source (`guess` / `msa-draft` /
`songformer-draft`) is preferred only with **>= 5 non-holdout songs** that carry both keepers and
drafts, **F@0.5 >= 0.50**, and a **>= 0.03** lead over the next source; holdout songs are scored but
never vote. Rank only chooses a draft intern — it never labels, never writes `sections.jsonl`, never
trains torch, never fits a model on mixed FLACs. The old `enough_to_train`/`role_prior` gate is gone;
Save appends a `save_snapshot` event, `compare` refreshes the rank, and `structure`/`guess` print
`prefer=<source>` only when they emit that source. `data/learn.jsonl` and `data/intern_rank.json`
stay local (gitignored).

## Adapt (per-album calibration)

`data/adapt.json` is per-album calibration from the first **heard** keeper pairs (greedy nearest
start <= 3.0 s): a median edge shift (`shift_start`/`shift_end`, each clamped to +/-0.50 s), an
intern-role -> saved-role map, and a draft/suggested `figure_id` -> saved map. Guess applies it to
its draft boxes (later Guess on that album), drafts only — keepers are skipped, `heard` is never
ticked, `sections.jsonl` is never written, and intern_rank's 5-song vote is untouched. Holdout
tracks never teach a mixed album (a holdout-only album may build for itself); Save rebuilds the
album's blob, and `boo-lab adapt [--album X]` prints it. Generated/local (gitignored).

## Detect (figure drafts + breakdown gate)

Guess proposes **figure windows** as unheard riff drafts when the song's `sync.jsonl` is `sync_ok`
and `data/figures.jsonl` occurrences are `times_trusted` (`source=guess`, `heard=false`; a marker
already covering the span within 0.35 s with the same `figure_id` is skipped). No sync or untrusted
times ⇒ zero figure drafts. Audio half-time/kick breakdowns obey a **per-album gate** built from
heard `breakdown` keepers on that album excluding holdout (`breakdowns {n, median_span_sec}` in the
album's `data/adapt.json` blob): with `n>=2`, only spans 0.5–1.5× the median are kept; `n<2` keeps
the current rules. Guess prints `figures_drafts=M breakdowns_used=N`. VAL never teaches another
album. Never writes `sections.jsonl`.

## Pack / learning

For each **keeper** box: mix clip + drums/bass/guitar/piano/other/vocals + no-vox (6-stem where cached) + `meta.json` (times, role, `figure_id`, source, split, gp path). Default Demucs model is 6-stem `htdemucs_6s`; guitar/piano are isolated, no-vox is mixed from the six. A track cached only under the old 4-stem model still packs (guitar/piano simply absent). That is enough until 20 labelled songs.

## Git

- Remote `origin` = `https://github.com/z2wgv7dc4h-alt/1222.git`.
- `.git` root is `god-tier-metal`. `cd tools\boo-lab` still uses that repo (`tools/boo-lab/...` paths).
- UI button runs `git add src+data`, commit, push. `work/` is ignored — adding it used to abort the button.
- CRLF warnings are not failure.
- Button cannot type a GitHub password. One successful `git push` in cmd stores creds.
- Verify a file:  
  `https://github.com/z2wgv7dc4h-alt/1222/blob/main/tools/boo-lab/src/boo_lab/<file>`  
  gitutil lives in **`src/boo_lab/`**, not the `tools/boo-lab/` listing.

```
cd C:\Users\RIGGUSPIG\Desktop\god-tier-metal
git add tools/boo-lab/src tools/boo-lab/data tools/boo-lab/*.md tools/boo-lab/.env.example
git commit -m "…"
git push
```

## HTTP (studio)

`GET /` HTML  
`GET /api/tracks`  
`GET /api/audio/{id}` range FLAC  
`GET /api/drums/{id}`  
`GET /api/cover/{id}`  
`GET /api/tab/{id}`  
`GET|POST /api/sections/{id}`  
`GET /api/estimate/{id}` Guess  
`GET /api/stem/{id}/{name}` any cached stem  
`GET /api/analysis/{id}` drum onsets/confidence for the song  
`POST /api/album/remove` `{album, confirm}`  
`GET /api/drafts?album=&track=` machine drafts  
`POST /api/ingest` multipart `band` + `files`  
`GET|POST|PUT /api/lyrics/{id}`  
`POST /api/pack/{id}`  
`POST /api/jams/{id}` keepers → `work/jams/<album>/<track>.jams` (409 when no keepers / VAL)  
`POST /api/git/push`

Track id is **map row index after album sort**; audio/cover/tab/drums/stem/lyrics/pack resolve by
album+track so “Rebirth” cannot stream “Machine.”

## CLI

`init-map` `scan` `hash` `studio`/`annotate` `ingest` `stems` `pack` `drums` `vocals` `holdout`
`lyrics` `structure` `beats` `audit` `extract` `gate` `report` `export-bank` `agree` `compare`
`hear` `sync` `figures` `gp-export` `learn` `adapt` `export-jams` `interns` `gpif` `status` `doctor`

`drums`/`vocals` default to keeper-section rows; `--per-track` adds one whole-track
row per song (`role=None`, `mode="track"`) from the cached 6-stem, no keeper needed —
drafts only, and the two modes coexist in `data/drum_patterns.jsonl` / `data/vocal_melody.jsonl`.

`structure` writes `data/drafts.jsonl` only (allin1 → `msa-draft`; SongFormer when
`SONGFORMER_HOME`/import → `songformer-draft`). `agree` snapshots keeper pins (pass 1/2) and diffs
them; `compare` scores drafts vs keepers per source; `export-jams` writes JAMS 0.3 figure/function
layers; `beats` writes `beat_this`/allin1 beat grids; `hear` flips `heard` on one song's keepers.
None of them writes `sections.jsonl` except the studio Save.

`boo-lab status` rewrites only the marker block in `STATUS.md` from disk: keeper rows/tracks via
`load_section_rows`, drafts + sources, `sync_ok`/total, and `map.csv` rows (reusing
`data/corpus_health.json` when fresh). It never runs pytest and never touches the test-count line.

Album/track arguments resolve the way the studio names them: `catalogue.resolve_row` ignores a
leading `YYYY` / `YYYY - ` album prefix and track-number punctuation, so
`--album "A Higher Place" --track "07 - Exist"` hits the map row `2009 - A Higher Place` / `07 - Exist`
(exact → casefold → core-key; a different album sharing only a year never matches). `sync` / `hear` /
`figures` / `agree` / `compare` use it. A map miss is `no-row`, distinct from a matched row whose gp
is missing (`no-gp`, which still prints the real path); a genuine failed `sync` appends
`tab_play=Xs flac=Ys dly=Zs` to its note.

Optional interns: `pip install -e ".[intern]"` (allin1, beat-this, natten, jams, mir_eval, madmom);
`.[pitch]` torchcrepe; `.[align]` whisperx. Never default dependencies. Pins: `constraints.txt`.
`madmom` is listed explicitly because allin1 imports it but its own metadata omits it.
GPU torch must be installed from the CUDA index (`setup.bat` does it); a plain `pip install torch`
on Windows is CPU-only. allin1's removed NATTEN API, madmom's py2/numpy-2 breakage, and the
`collections` ABC aliases are repaired at runtime by `boo_lab/_natten_compat.install()` — which runs
at `import boo_lab` (so `doctor`/CLI/structure get it first). No old natten build is needed.

## Research outputs (machines may draft, not label)

- `data/drafts.jsonl` — allin1 `msa-draft`, SongFormer `songformer-draft`, Guess `guess`.
- `boo-lab agree --album X --track Y --write` — snapshot keepers as pass 1 (first) or pass 2 (re-pin); `--diff` gives role-agnostic boundary hit-rate @0.5s/@3.0s plus role/figure agreement. Never a pass 3.
- `boo-lab compare [--album X]` — drafts vs keepers per song **and per source**: precision/recall/F @0.5/@3 plus role agreement; marks `split=holdout` (never skipped). Writes `data/compare.json`.
- `boo-lab export-jams --out DIR` — one `.jams` per keeper song, `segment_lab_figure` + `segment_lab_function`; holdout skipped.
- `boo-lab beats [--album X]` — `data/beats.jsonl` (`beat_this` preferred, allin1 fallback).
- `boo-lab sync --album X --track Y` — GP clock vs the audio through **two** co-witnesses: a blurred (~120 ms) onset correlation and a chroma correlation (tab pitches held over each beat vs `chroma_cqt`), preferring the cached guitar stem with a per-witness mix fallback. `sync_ok` if either is within 350 ms at score ≥ 0.15, or an **aligned-with-offset** lead-in (within 5 s, peak prominence ≥ 0.05, other witness agreeing ≤ 0.25 s). Records `used_stem`/`lag_sec`/`score`/`clock_ratio`/`chroma_lag`/`chroma_score`/`offset_sec`. `|lag|` alone is not the rule.
- `boo-lab hash [--album X]` — fills `flac_sha256` in `map.csv` for rows whose FLAC exists (atomic write; never rehashes a valid 64-hex digest).

**Sync clock rate.** `boo-lab sync` now wires the existing `best_clock_fit` (span ±0.08, step 0.01)
into `sync_ok`: the rate-adjusted onset lag must pass `decide` (still `|lag| < 0.35 s`, score ≥ 0.15)
and the chroma witness must agree at that same ratio within 0.25 s (a lone onset rate-fit may stand
when no chroma exists). So the ~2.7% uniform-drift class can pass; 20% still fails. `clock_ratio` is
always recorded (1.0 when no stretch) and a pass reads `ok (rate 1.027)`. No threshold was loosened.
Figure hashes (`data/figures.jsonl`) publish `start`/`end` seconds only when that song's `sync_ok`
is true (`times_trusted`); otherwise bars/hashes only.
- `boo-lab audit` — sources/overlaps/heard/short-box hygiene.

Reading: **F3 high + role agreement low = the intern finds the edges but names them wrong.**

## Decisions (do not reopen without a new fact)

- Sparse human structure + stems pack beats “learn 10k FLACs end-to-end” for form.
- No DAW, no RoFormer tonight, no AlphaTab as a product (tabs are not a product surface).
- No madmom as a hard dependency (Python 3.12 / numpy war). Librosa + Demucs only.
- allin1 optional; now works via `_natten_compat` (legacy NATTEN API + madmom py2 / numpy-2 shim). Guess must still work without it.
- GPU when present: `boo_lab/device.py` `torch_device()` is the only switch; interns never hardcode `"cpu"`.
- Fragile pins live in `constraints.txt`; `setup.bat` + `doctor` are the onboarding path.
- No tab scraping.
- Overlaps are layered roles, not two riffs of the same name.
- Guess never overwrites a careful Save if the user does not press Guess.
- Art is local files next to FLACs, not MusicBrainz.
- **A keeper is heard.** Machines write drafts; they never write keepers.
- allin1 / SongFormer / beat_this / jams / mir_eval are optional **intern** extras, never default deps.
- 6-stem Demucs (`htdemucs_6s`) is the default; old 4-stem caches stay valid.
- `boo-lab hear` is per-track only; never blanket `heard=true` over the catalog.
- **One reader for `sections.jsonl`**: `schema.load_section_rows` (keepers = truthy `role` + keeper `source` + `heard is True`). No twin readers.
- **Every write is atomic** (`schema.write_jsonl_atomic`); a zero-row/failed run must never blank a prior file.
- **Fail closed**: a missing/unknown source is never a keeper; an unmappable role is rejected at Save, never defaulted to `riff`.
- **Labyrinth hard-fails on an uncovered bank role** (`RiffBankCoverageError`); tests encode that, not a silent Markov fallback.
- **`interns` is a CLI pass, not a studio button.** It is a long, GPU-bound job; run `boo-lab interns [--album/--steps]` from cmd (resumable, so re-run is cheap). No SSE/progress endpoint, no blocking request.

## Bugs that already bit us (regressions to refuse)

1. `UnboundLocalError: os` / `scan_roots` — inner import shadowing. Do not nest those imports inside branches.
2. Save sending wave regions at t=0, duration 0 → six `0.25s` boxes. Table wins; refuse all-tiny saves.
3. `float(tempo)` on a 1-d ndarray kills drums Guess.
4. Riff fill same colour as the waveform.
5. Ingest default `new_band` inside `born_of_osiris`.
6. Drop using `f.name` only, dropping folder structure and covers.
7. Git add `work/` + safecrlf warnings treated as fatal.
8. Play box calling `play()` with no end.
9. Audio id = list index without album+track resolve.
10. One GP file matching every similarly named track.
11. `torch+cpu` venv + allin1's `device='cpu'` default → every intern ran on CPU with a GPU idle. Use `device.py`; check `doctor`.
12. natten ≥0.17 dropped the pre-0.17 API allin1 imports (`natten1dav`/`1dqkrpb`/`2dav`/`2dqkrpb`) → `ImportError`. Fixed by `_natten_compat` (exact `get_window_start`/`get_pb_start` ports). Do not "fix" by pinning old natten — no Windows/py3.12 wheel exists.
13. madmom on py3.12 + numpy2: `NameError: integer`, `np.int`, and ragged `asarray` in downbeat tracking. All repaired by `_natten_compat.install()`.
14. GP clock ignored `song.tempo` and defaulted to 120 BPM, stretching every tab ~1.6× — `sync` could never match. Read `song.tempo` (per-measure `header.tempo` only when set).
15. Repeat unroll reset a group's pass count on re-entry (`isRepeatOpen`) → infinite loop (2M onsets) on 02/04/06. Use `setdefault`; the unroll is now unit-tested.
16. Scan GP keys didn't strip a space-form track number, so `07 Exist.gp5` keyed as `07exist` and silently never matched `07 - Exist.flac` (read as "no tab"). Space-numbered keys are added; both the match and the no-overmatch case are tested.
17. `drums_extract`/`vocal_melody` read `sections.jsonl` with `if rec.get("source") == "human" or rec.get("role")` — precedence made the source test dead, so every row (including machine drafts) counted as human. One shared `schema.load_section_rows` now enforces the keeper law.
18. `beats`/`structure.build_drafts`/`drums_extract`/`vocal_melody` opened their output with mode `"w"` and truncated it before writing — a failed/zero-row run blanked the whole file (this actually wiped `drafts.jsonl` once). All buffer + `write_jsonl_atomic`, and only replace when a row was produced.
19. `sections.jsonl` was also rewritten non-atomically by `hear` and album-remove; a crash mid-write destroyed every label. Both now use `write_jsonl_atomic`; album-remove parses (and aborts on a malformed line, deleting nothing) first.
20. `is_keeper(None)`/missing source returned `True` and `canonical_role` defaulted to `"riff"` — fail-open, so unstamped/unmappable rows became trusted human truth. Both fail closed now (`None` role rejects the Save).
21. madmom does `from collections import MutableSequence`; on some py3.12 builds that name is gone. `_natten_compat.install()` aliases the `collections` ABCs and now runs at `import boo_lab`.

## What to do next (human)

Label Elimination by ear. Do not wait on Guess. Scan after any ingest. Push docs+code from cmd when a chunk of work is done.
