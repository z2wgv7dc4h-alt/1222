# CURRENT — read this first (2026-09-14)

Single source of truth for humans and later bots. If README/STATUS/LAW disagree with this file, this file wins. Then fix the others.

## What this is

A **section lab** for metal FLACs (Born of Osiris first, other bands via ingest). Output is `data/sections.jsonl` + optional Pack clips under `work/` (gitignored). It is not God Tier Metal, not a DAW, not a tab reader, not an auto-songwriter.

GitHub: `https://github.com/z2wgv7dc4h-alt/1222` path `tools/boo-lab`.  
Tip that first shipped the night’s UI/guess work: `6482c30` `guess bpm fix, save harvest, riff colors`. Later local files (ingest hoist, catalogue unique match, gitutil ignore `work/`, docs) may still need a separate commit.

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

## Data written

| path | what |
|---|---|
| `data/map.csv` | scan result: album, track, flac path, gp path, match |
| `data/sections.jsonl` | one JSON object per box. Save **replaces** that track’s rows, keeps other tracks |
| `data/rebirth-sections.jsonl` | reference labels for Rebirth |
| `work/stems/` | Demucs cache (gitignored) |
| `work/drop/` | ingest landing (gitignored) |
| `work/pack/` or pack output | sliced mix/drums/bass/other/novox + meta (gitignored) |
| `work/lyrics/` | LRC cache |

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
- Drums lane: display of cached stem, **not** proof Guess ran.
- Table is source of truth on Save (`harvestTable`). Blur number fields before Save.
- Play = whole track. Play box = selected region only.
- Guess merges drafts if boxes already exist; do not Guess a finished song.
- Lyrics: click line to seek; ±0.2 nudge; Save lyrics.
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

For each **human** box: mix clip + drums/bass/other/no-vox if stems exist + `meta.json` (times, role, gp path). Vocals removed via Demucs stems, not by a second product. Rhythm vs lead vs keys is **not** auto-split; “other” is the leftover stem. That is enough until 20 labelled songs.

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
`POST /api/ingest` multipart `band` + `files`  
`GET|POST|PUT /api/lyrics/{id}`  
`POST /api/pack/{id}`  
`POST /api/git/push`

Track id is **map row index after album sort**. Lookup audio by album+track so “Rebirth” cannot stream “Machine.”

## CLI

`init-map` `scan` `studio`/`annotate` `ingest DROP --band` `stems` `pack` `lyrics` `structure` `extract` `gate` `export-bank`

## Decisions (do not reopen without a new fact)

- Sparse human structure + stems pack beats “learn 10k FLACs end-to-end” for form.
- No DAW, no RoFormer tonight, no AlphaTab as a product (tabs are not a product surface).
- No madmom as a hard dependency (Python 3.12 / numpy war). Librosa + Demucs only.
- allin1 optional and often broken in this venv; Guess must work without it.
- No tab scraping.
- Overlaps are layered roles, not two riffs of the same name.
- Guess never overwrites a careful Save if the user does not press Guess.
- Art is local files next to FLACs, not MusicBrainz.

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

## What to do next (human)

Label Elimination by ear. Do not wait on Guess. Scan after any ingest. Push docs+code from cmd when a chunk of work is done.
