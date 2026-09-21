# boo-lab NOW prompt — 2026-09-21

Copy everything between BEGIN and END into the bot as the first message.
One job per turn. Do not pin songs. Do not Guess. Do not train.

======= BEGIN PROMPT =======

You are working in repo `z2wgv7dc4h-alt/1222`, tree `tools/boo-lab` only.
This is a labelling lab, not a music generator.

This session is the **NOW** pass only. Five jobs, in order. After each job: tests, tick it in this prompt’s checklist (or in `tools/boo-lab/BOO-LAB-BOT-TASKS.md` if that file exists), commit that job, STOP.

Do not start “prove cells / export-bank / one engine song”. That is a later pass after the human pins 5 non-VAL tracks.
Do not Guess. Do not write `data/sections.jsonl`. Do not edit Rebirth keepers or `data/holdout.csv`. Do not touch Forge/`Ww`. Do not invent a new intern, draft source, CLI command, or studio button except what a job names.
Do not convert GP7 `.gp`/`.gpx` to GP5. Do not rename FLACs. Do not scrape tabs. Do not import `riff_model.py`. `lead` is an instrument, not a role. Never invent `riff-blast-A`.

## Law

- Keepers = `source` in `{human, guess-accepted}` AND `heard=true`.
- Machines draft only. `structure` / Guess / predict / learn / adapt / extract never write keepers.
- Fail closed: unknown role → reject; unknown source → reject the whole Save; missing source is not a keeper.
- `schema.write_jsonl_atomic` for JSONL writes.
- GP7 is read natively via `gpif.py`.
- Tests for every behavior change. `cd tools/boo-lab && python -m pytest -q` (Windows: `.venv\Scripts\python -m pytest -q`).

## Read first (only these)

- `tools/boo-lab/LAW.md`
- `tools/boo-lab/src/boo_lab/schema.py`
- `tools/boo-lab/src/boo_lab/guess.py` (precedence + Guess cap — read, do not “improve” Guess unless job 2 requires a call-site change)
- `tools/boo-lab/src/boo_lab/extract.py`
- `tools/boo-lab/src/boo_lab/sync.py` (`_prefer_gpif_path`, clock)
- `tools/boo-lab/src/boo_lab/figures.py` (how pack vs GP is chosen today)
- `tools/boo-lab/src/boo_lab/tabnotes.py` (`discover_pack`, `load_pack`, `note`/`bar` helpers)
- `tools/boo-lab/src/boo_lab/compare.py`
- `tools/boo-lab/src/boo_lab/adapt.py`
- `tools/boo-lab/USER.md` Part A only, when you reach job 5

Do not read the whole repo. Do not grow `CURRENT.md`.

---

## Job 1 — `figure_id` default

`schema.stamp_box` today does `(figure_id or "").strip() or f"{role}-A"` for every role.

Change:
- Figure roles (`riff`, `hook`, `solo`, `pulse`): blank → `"{role}-A"` (unchanged).
- Function roles (`intro`, `build`, `breakdown`, `blast`, `chill`, `outro`): blank stays `""`. Do not invent `intro-A` / `blast-A`.
- `on_figure` stays optional and separate. Do not stuff a function’s figure_id from `on_figure`.
- Do not rewrite `data/sections.jsonl` (the 6 Rebirth rows stay as they are on disk).

Tests in `tests/test_schema.py`:
- `stamp_box(0, 4, "riff")` → `figure_id == "riff-A"`
- `stamp_box(0, 4, "blast")` → `figure_id == ""`
- `stamp_box(0, 4, "breakdown", figure_id="riff-B")` → `"riff-B"`
- existing on_figure / blast tests still pass

Commit: `boo-lab: function roles do not invent figure_id`
Stop.

---

## Job 2 — one precedence helper

Today Guess, sync, figures, and extract each pick a different parent file (GP markers vs pack vs GP notes). Add **one** function and switch the call sites.

New helper, pick one home and stick to it (prefer `src/boo_lab/tabnotes.py` or a tiny new `src/boo_lab/precedence.py` — do not add a package of files).

Suggested API (names can be clearer; behavior cannot):

```
def tab_plan(lab_root, album, track, gp_path=None) -> dict:
    # returns a plain dict, no I/O side effects besides reading existing
    # map/sync/pack index. Never writes sections.jsonl.
```

Contract:

1. If no `sync_ok` (no row, or `sync_ok` is not True):
   - `spine = "human"`
   - `markers = False`, `pack_spine = False`
   - extract may still read notes later only when the human has pins; Guess must not emit tab/pack structure
2. If `sync_ok` and the GP (prefer GP7 via existing `_prefer_tab` / `_prefer_gpif_path`) has section markers:
   - `spine = "gp-marker"`
   - pack may still supply `kicks`, `pulse`, `meter_cuts`
   - pack must NOT replace the marker spine
3. Else if `sync_ok` and `discover_pack` hits:
   - `spine = "pack"`
   - pack structure/phrases are the spine
4. Extract notes source (separate key, not the spine):
   - `notes = "gp"` if a readable GP5/GP7 path exists
   - `notes = "pack"` if no GP but a pack exists
   - `notes = None` otherwise
5. Clock for marker/pack seconds:
   - prefer the sync row’s trusted clock (`clock_ratio` already recorded)
   - pack `start_sec_audio` when spine/notes are pack
   - GPIF `note_events` / `duration_sec` when notes are gp

Wire these call sites to **read the helper**, not a private if-ladder:
- `guess.py` — when to emit gp-marker vs pack spine; keep existing marker-first flood cap
- `figures.py` — do not silently let pack always win if markers are the Guess spine; figures for naming may still hash pack tracks, but must not bury markers
- `extract.py` — use `notes` key (job 3)
- `sync.py` — do not invert the helper; if sync currently prefers pack onsets when a pack exists, leave clocking as-is UNLESS it contradicts `sync_ok` gating. Add a comment pointing at the helper so the next pass cannot drift.

Do not restyle Guess. Do not change flood constants unless a test proves markers are not primary when they should be.

Tests:
- fake `sync_ok=False` → spine human, no markers
- fake `sync_ok=True` + GP markers → spine gp-marker, pack kicks allowed
- fake `sync_ok=True` + pack only → spine pack, notes pack
- fake `sync_ok=True` + GP file + pack, no markers → spine pack, notes gp

Commit: `boo-lab: one tab/pack precedence helper`
Stop.

---

## Job 3 — extract cells from the right notes

`boo-lab extract` / `extract_riffs` today goes through `engine/riff_bank` on a GP path. Pack string/fret events are not a cell source.

After job 2’s `notes` key:

- If `notes == "gp"`: keep the existing `riff_bank` / GPIF path. Do not invent a second GP parser. Times for aligning human keepers stay on the trusted clock (sync `clock_ratio` / GPIF seconds).
- If `notes == "pack"`: build the same cell shape from the pack — primary guitar-category track (lowest mean pitch, same rule figures already uses), `bar_fp` runs, shortest repeating 2/3/4-bar cell per `figure_id`. Seconds from pack audio clock (`start_sec_audio` / `audio_sec`). No GP-style A/B letters invented.
- If both GP and pack exist: **notes from GP**, **kicks/pulse/meter from pack** (those are Guess/figures, not extract cells). Extract does not flatten pack kicks into riff cells.
- Human keepers still override role on cells that fall inside a heard box (existing `load_human_sections` / `load_section_rows` + `_BOO_LAB_TO_ENGINE_ROLE`). Pulse/blast map to `None` for the engine, unchanged.
- Zero cells must not blank an existing `data/riffs.jsonl`.
- Still never write `sections.jsonl`.

Tests with the existing pack fixture `tests/fixtures/tabnotes_tiny/` (do not add The New Reign zip to git):
- pack-only → at least one cell, 2–4 bars, has pitch/string or midi, source/path stamped pack
- gp-only fixture `tests/fixtures/tiny.gp` still produces cells the old way
- both present in a fake plan → extract uses gp notes, not pack notes

Commit: `boo-lab: extract cells from GP notes or pack notes`
Stop.

---

## Job 4 — compare + adapt see pack/marker drafts

`compare.DRAFT_SOURCES` and `adapt.DRAFT_SOURCES` omit `gp-marker`, `tabnotes-density`, `tabnotes-structure`, `tabnotes-phrase` (and `blast-hint` if compare is scoring roles). After a human accepts those drafts, learn/adapt ignore them.

- Add those sources to **both** sets (compare used for F@0.5; adapt used for pairing).
- `figure-hash` stays out of adapt pairing (identity draft, not a section stencil) unless compare already treats it — do not start scoring hashes as structure.
- `keeper-model` stays in compare if it is already there; do not add it to adapt pairing unless it is already paired (it is a draft; pairing it is OK if compare has it — pick one rule and test it: adapt pairs any non-keeper source that compare scores, except `figure-hash`).
- Holdout still does not vote (`learn`) and still does not teach a mixed album (`adapt`).
- Never write keepers.

Tests:
- compare counts a `tabnotes-structure` draft against a keeper
- adapt `rebuild_album` forms a pair from a `gp-marker` draft and a heard keeper within 3s
- `figure-hash` does not enter adapt pairs

Commit: `boo-lab: compare/adapt score pack and marker drafts`
Stop.

---

## Job 5 — USER.md Part A only

Fix operator copy. Do not rewrite Part B, LAW, CURRENT, README except a one-line pointer if Part A already says “see CURRENT”.

- Unsmash the Mark paragraph: zoom / A–B loop / click-away / drag edges are separate sentences.
- Keys listed once.
- VAL: holdout songs do not train and do not vote `prefer=`. You may still open and pin them. Rebirth is VAL and already pinned; leave it. New work is non-VAL tracks.
- One short “Guess” line: Guess is a stencil. Markers first when the tab is on-clock. Do not Guess a song you already Saved. Do not Save a hash flood — delete hashes, keep letters, listen, heard, Save.
- Do not add pixel specs, commit hashes, or intern novels.

Commit: `boo-lab: USER.md Part A readable`
Stop.

---

## Checklist (tick as you finish; one per turn)

- [x] Job 1 figure_id default
- [x] Job 2 one precedence helper
- [x] Job 3 extract notes source
- [ ] Job 4 compare/adapt sources
- [ ] Job 5 USER.md Part A

## After job 5 the human does this — you do not

1. Smoke click: Guess on The New Reign. Do not Save if it is a hash flood. If flood, a **later** turn may tighten the existing marker-first cap only — do not pre-empt that.
2. Human pins 5 non-VAL tracks.
3. Only then: prove cells are 2–4 bars, export-bank, one engine song.

If you finish job 5 and the human has not pinned yet, stop and say:
`NOW pass done. Waiting on Guess smoke + 5 non-VAL keepers.`

## If blocked

One paragraph, then stop. No workaround that writes keepers, walks `C:\Users\RIGGUSPIG\...`, or adds an intern.

Start now at Job 1.

======= END PROMPT =======
