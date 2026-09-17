# CURRENT — read this first (2026-09-18)

Single source of truth for humans and later bots. If README/STATUS/LAW disagree with this file, this file wins. Then fix the others.

> **Read this first.**
> Keepers = `data/sections.jsonl` (`source=human`/`guess-accepted` **and** `heard=true`).
> Drafts = `data/drafts.jsonl` (`msa-draft` / `songformer-draft` / `guess`) — **never keepers**.
> Box fields: `start end role layer form figure_id unique instrument start_bar end_bar source heard`.
> Studio table columns match those; waveform is WaveSurfer, with a real mel spectrogram below it (Wave / Spec / Both).
> `structure` writes `drafts.jsonl` only. `hear` and `sync` require **both** `--album` and `--track`.
> `hash` fills `flac_sha256`; `sync` writes `data/sync.jsonl` (`sync_ok`/`lag_sec`); `beats` → `data/beats.jsonl`.
> Holdout songs stay unpinned. GP5 for extract; GP7 is eyes / export-to-GP5.
> One album side per session. Default install is thin; interns (allin1 / beat-this / SongFormer) are optional.
> Machines may draft. They never label.
> Interns run on **GPU when present** (`boo_lab/device.py`); `boo-lab doctor` must print `cuda=True`.
> New machine: `setup.bat --flac <CORPUS> --gp <GP_ROOT>` then `boo-lab doctor` (green).

## What this is

A **section lab** for metal FLACs (Born of Osiris first, other bands via ingest). Human output is `data/sections.jsonl` — **keeper pins only** (`source=human`/`guess-accepted`, `heard=true`), each with a figure/function `layer` and a `figure_id` — plus optional Pack clips under `work/` (gitignored). Machines write `data/drafts.jsonl` (MSA/SongFormer/Guess) and never keepers. It is not God Tier Metal, not a DAW, not a tab reader, not an auto-songwriter.

GitHub: `https://github.com/z2wgv7dc4h-alt/1222` path `tools/boo-lab`.  
Newest lab commit: `26b4d8d` (`START.bat`; `INSTALL.bat` no longer clobbers `.env`); before it `50f0eb6` (audio lead-ins: prominent, corroborated offset), `fab89f5` (stems `--album`, guitar-stem-preferred sync + mix fallback).

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
python -m boo_lab.cli studio --port 8765
```

http://127.0.0.1:8765 — Ctrl+Shift+R after HTML. Restart the process after `.py` changes. One server.

GPU check (do this before trusting any intern): `python -m boo_lab.cli doctor` — it must print
`cuda=True` + the GPU name. `doctor` also names any missing intern/extra and the exact install.
Interns (allin1 / beat_this / torchcrepe) read `boo_lab/device.py`; they never hardcode CPU.

## Data written

| path | what |
|---|---|
| `data/map.csv` | scan result: album, track, flac path, gp path, match, `flac_sha256` |
| `data/sections.jsonl` | **keeper** boxes only. Save **replaces** that track’s rows, keeps other tracks |
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

If Save wrote six `0.00–0.25` rows, the pins fired before duration loaded. Paste the lines above into `sections.jsonl` and reload.

## UI contract

- Left: albums collapse, cover thumb if `cover.jpg` / `folder.jpg` / `Cover/` / Cyrillic `Сover.jpg` sits next to FLACs.
- Green GP5 = matched tab. Partial only if notes/name say stub/fragment/bass-only.
- Mix lane: drag boxes. Click empty wave to seek. Clicking a box edge should not steal the next pin — leave a gap or seek first.
- Spectrogram: real mel spectrogram of the already-decoded buffer under the mix; **Wave / Spec / Both** toggle (default Both), click to seek, current boxes overlaid. Waveform stays WaveSurfer.
- Stem lane: pick any cached Demucs stem (drums/bass/guitar/piano/other/vocals); the drum-confidence note flags sections the classifier is unsure about.
- Table is source of truth on Save (`harvestTable`); columns role / figure / form / uniq / inst / bar0 / bar1 / start / end / source / heard. Blur number fields before Save.
- **Heard** gates the save: untick it and the box is dropped. A heard draft saves as `guess-accepted`.
- **Save is atomic**: temp file in the same dir, `fsync`, then `os.replace`. A crash, full disk, or aborted write leaves `sections.jsonl` (the one unrecoverable artifact) untouched and returns a real error.
- **A bad box rejects the whole save** with 400: `end <= start`, non-numeric/non-finite `start`/`end`, a non-object row, a box whose role maps to none, or an unknown/missing `source`. Never repaired into a `0.25s` box (Bugs #2), never defaulted to a human keeper.
- **Fail closed**: `schema.is_keeper` is true only for `human`/`guess-accepted` (missing/empty source is NOT a keeper); `schema.canonical_role` returns `None` for unmappable input. Every non-keeper source promotes to `guess-accepted` once Heard (derived from `SOURCES - KEEPER_SOURCES`).
- A **malformed line already in `sections.jsonl`** is skipped and counted, not fatal: the response carries `malformed_lines_skipped` and `malformed_line_numbers`.
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
2. Parse rehearsal markers → roles if the marker text maps (`break` → breakdown). Most BoO GP5s have **no markers** → all cuts become riff/verse.
3. Demucs drums stem into `work/stems/` (first time slow).
4. librosa beat_track on that stem. Tempo must go through `_scalar` (numpy 2 `float(array)` crash used to abort here).
5. Half-time IOI (~1.65× median, ≥6s) → breakdown drafts.
6. Kick band <140 Hz IOI ≥5s → breakdown drafts.
7. `_clean` short/overlap junk.

If the blue bar says `only 0-dimensional arrays can be converted to Python scalars`, the server is still on old `guess.py`.  
If it says `librosa beats, no half-time`, drums ran and found no slam — correct on Rebirth, common on mid-tempo grooves.

Guess is **not** a BoO brain. Elimination GP markers = riff slices that stop mid-song. Human paints Breakdown and the tail.

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
`POST /api/git/push`

Track id is **map row index after album sort**; audio/cover/tab/drums/stem/lyrics/pack resolve by
album+track so “Rebirth” cannot stream “Machine.”

## CLI

`init-map` `scan` `hash` `studio`/`annotate` `ingest` `stems` `pack` `drums` `vocals` `holdout`
`lyrics` `structure` `beats` `audit` `extract` `gate` `report` `export-bank` `agree` `compare`
`hear` `sync` `export-jams` `doctor`

`structure` writes `data/drafts.jsonl` only (allin1 → `msa-draft`; SongFormer when
`SONGFORMER_HOME`/import → `songformer-draft`). `agree` snapshots keeper pins (pass 1/2) and diffs
them; `compare` scores drafts vs keepers per source; `export-jams` writes JAMS 0.3 figure/function
layers; `beats` writes `beat_this`/allin1 beat grids; `hear` flips `heard` on one song's keepers.
None of them writes `sections.jsonl` except the studio Save.

Optional interns: `pip install -e ".[intern]"` (allin1, beat-this, natten, jams, mir_eval);
`.[pitch]` torchcrepe; `.[align]` whisperx. Never default dependencies. Pins: `constraints.txt`.
GPU torch must be installed from the CUDA index (`setup.bat` does it); a plain `pip install torch`
on Windows is CPU-only. allin1's removed NATTEN API and madmom's py2/numpy-2 breakage are repaired
at runtime by `boo_lab/_natten_compat.py`, so no old natten build is needed.

## Research outputs (machines may draft, not label)

- `data/drafts.jsonl` — allin1 `msa-draft`, SongFormer `songformer-draft`, Guess `guess`.
- `boo-lab agree --album X --track Y --write` — snapshot keepers as pass 1 (first) or pass 2 (re-pin); `--diff` gives role-agnostic boundary hit-rate @0.5s/@3.0s plus role/figure agreement. Never a pass 3.
- `boo-lab compare [--album X]` — drafts vs keepers per song **and per source**: precision/recall/F @0.5/@3 plus role agreement; marks `split=holdout` (never skipped). Writes `data/compare.json`.
- `boo-lab export-jams --out DIR` — one `.jams` per keeper song, `segment_lab_figure` + `segment_lab_function`; holdout skipped.
- `boo-lab beats [--album X]` — `data/beats.jsonl` (`beat_this` preferred, allin1 fallback).
- `boo-lab sync --album X --track Y` — GP onset clock vs the audio envelope (guitar stem else mix); `sync_ok` iff `|lag| < 0.35 s` and score ≥ 0.15. Writes `data/sync.jsonl`.
- `boo-lab hash [--album X]` — fills empty `flac_sha256` cells in `map.csv` (scan hashes on rewrite).
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

## What to do next (human)

Label Elimination by ear. Do not wait on Guess. Scan after any ingest. Push docs+code from cmd when a chunk of work is done.
