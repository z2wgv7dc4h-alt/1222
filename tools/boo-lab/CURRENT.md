# CURRENT — contract

Living docs: USER.md (operator), LAW.md (rules), this file (short contract), README.md (install + commands), STATUS.md (counts), CHANGELOG.md (dated history). If they disagree, LAW + this file win; then fix the others.

## Keepers / drafts / writers

- **Keepers** = data/sections.jsonl with source in human / guess-accepted and heard=true.
- **Drafts** = data/drafts.jsonl (msa-draft, songformer-draft, guess, gp-marker, igure-hash, last-hint, 	abnotes-density, 	abnotes-structure, 	abnotes-phrase, keeper-model). Never keepers.
- **Writers of sections.jsonl:** studio **Save**, oo-lab hear, album-remove. Save drops unheard boxes and replaces that track's rows only.
- Machines may draft. **They never label.**

Box fields: start end role layer form figure_id on_figure unique instrument start_bar end_bar source heard (+ optional pack_id / pack_note_source when a trusted pack matched on Save).

## Paths

`
<LAB>     tools/boo-lab
<CORPUS>  audio-corpus          (env BOO_FLAC_ROOT)
<GP>      gp-tabs               (env BOO_GP_ROOT)
          gp5/<band>/           GP4/GP5
          gp7/<band>/           .gp / .gpx
`

BOO_FLAC_ROOT must be the **corpus** root, not a single band folder (ingest footgun).

## Start

`
cd <LAB>
.venv\Scripts\activate
set BOO_FLAC_ROOT=<CORPUS>
set BOO_GP_ROOT=<GP>
python -m boo_lab.cli scan
python -m boo_lab.cli hash
python -m boo_lab.cli interns
python -m boo_lab.cli studio --port 8765
`

START.bat = scan → hash → full interns (side window) → studio. Studio-only: python -m boo_lab.cli studio. http://127.0.0.1:8765 — Ctrl+Shift+R after HTML. oo-lab doctor must print cuda=True when a GPU is expected.

## Data written

| path | what |
|---|---|
| data/map.csv | scan: album, track, flac/gp paths, match, lac_sha256 (local-only; see .gitignore) |
| data/sections.jsonl | **keepers** only; Save keeps sections.jsonl.bak |
| data/drafts.jsonl | machine drafts; never keepers |
| data/holdout.csv | whole-song train/val reservation |
| data/beats.jsonl | beat/downbeat grid |
| data/sync.jsonl | tab-vs-audio: sync_ok, lag_sec, score |
| data/figures.jsonl | figure-hash drafts |
| data/adapt.json | per-album calibration (local) |
| work/ | stems, models, pack outputs (gitignored) |

Never commit FLACs, GP, stems, zips, tokens, .venv.

## Roles + overlap

Roles: intro, build, riff, hook, breakdown, blast, solo, chill, pulse, outro.

- Different roles **may** overlap. Two boxes of the **same** role on the same seconds → Save refuses.
- Breakdown / blast = functions (may sit on the same guitar as a riff). Never invent 
iff-blast-A.
- Pulse = named synth/keyboard figure, not “keys are audible.”
- Optional on_figure on a function box links the igure_id it rides.
- Figure roles default igure_id to {role}-A (or a tab letter); function roles may leave igure_id blank.

## Short law echoes

- `data/rebirth-sections.jsonl` is a **reference snapshot** of the Rebirth pins, not the writer path. Live keepers are only `data/sections.jsonl` (Save / hear / album-remove). Do not teach any command to write both.

- Pre-stamp Rebirth rows are grandfathered (accepted as-is by `load_section_rows`); audit flags their schema gaps as warnings only. A Save of a new track must go through `stamp_box` — it never back-fills the old rows.

- `phrase_spans` retune on import is **optional**; failure logs `phrase_retune skipped:` and keeps stock `tabnotes_drafts.pack_phrase_spans`.

- Prefer GP7 .gp/.gpx (parsed GPIF) over .gp5; no GP7→GP5 conversion.

- scan writes match=`stub` when the chosen GP is a stub (under 10 KB, or a `*_solo*`/cover/bass-only/Misha-mix/intro-only name); only match=`yes` is bankable — extract, figures, and holdout skip the rest. Files are never deleted or renamed.
- Do not rename FLACs; match tabs in map.csv.
- Guess / structure / predict (keeper-model) write **drafts only**. Predictor v1 is an optional scaffold — needs non-holdout keepers; holdout-only labs skip Save train unless holdout_fallback is explicit.
- VAL / holdout songs do not train or vote prefer=; pinning is fine (Rebirth is already pinned).
- gpif_to_gp5 stays unused.

Dated session notes, commit hashes, UI pixel novels, and predictor manifesto live in CHANGELOG.md.
