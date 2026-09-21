# boo-lab bot list â€” 2026-09-21

Work only in `tools/boo-lab`. Do not touch `engine/` except existing `riff_bank` import. Do not train. Do not write `data/sections.jsonl` keepers. Do not Guess. Do not rename FLACs. Do not commit FLACs, GP, stems, tokens, `.venv`, `work/`.

Law that must stay true after every box:
- Keepers = `source` in `{human, guess-accepted}` AND `heard=true`.
- Machines write drafts only (`data/drafts.jsonl` and friends).
- `schema.stamp_box` / `is_keeper` / `canonical_role` stay fail-closed.
- Every `sections.jsonl` write stays atomic (`write_jsonl_atomic`).
- GP7 `.gp`/`.gpx` is read natively. No GP7â†’GP5 conversion.
- Tests must pass. Add a test for every behavior change.

Stop after each P0 box. Commit that box only. Do not invent a new intern / draft source.

---

## P0 â€” stop the bot from making it worse

- [ ] **P0.1 Freeze surface.** Do not add draft sources, intern steps, CLI commands, or studio buttons in this pass unless a P0/P1 box names that file. Kill any in-progress â€œanother internâ€ branch.

- [x] **P0.2 Confirm pytest count from disk.** `cd tools/boo-lab && .venv/Scripts/python -m pytest -q`. Write the real number into `STATUS.md` counts only after it runs. Do not type a remembered â€œ389â€.

- [ ] **P0.3 Do not relabel Rebirth.** `data/sections.jsonl` (6 Rebirth rows) and `data/holdout.csv` stay as-is unless a later human box says otherwise.

---

## P1 â€” schema is one vocabulary

The live bug: Guess/extract emit `gp-marker` and figures emit `figure-hash`, but `schema.SOURCES` does not include them. Save 400s an unknown source. A heard marker box cannot become a keeper.

- [x] **P1.1 Single source set.** In `src/boo_lab/schema.py` add every source the code actually emits, and nothing else:
  - keepers: `human`, `guess-accepted`
  - drafts: `guess`, `msa-draft`, `songformer-draft`, `keeper-model`, `tabnotes-density`, `tabnotes-structure`, `tabnotes-phrase`, `blast-hint`, `gp-marker`, `figure-hash`
  - `adapt` is a stamp field, never a `source`. Leave it that way.
  - Update `LAW.md` / `USER.md` Part B / `CURRENT.md` â€œRead this firstâ€ to the same list. One list. No extras.

- [x] **P1.2 Save promotes every non-keeper source.** `annotator.py` already does `SOURCES - KEEPER_SOURCES` â†’ `guess-accepted` when `heard`. Add a test that a heard `gp-marker` box and a heard `figure-hash` box Save as `guess-accepted` and land in `sections.jsonl`. Unknown source still 400s the whole save.

- [x] **P1.3 `load_section_rows` really is the one reader.** Replace ad-hoc `sections.jsonl` parsers in:
  - `extract.load_human_sections`
  - `adapt._read_jsonl` (the sections path only)
  - `audit.py`
  - `hear.py` may keep its own pass (it must rewrite `heard`), but keeper filtering after the rewrite goes through `is_keeper`
  - Saveâ€™s â€œother tracksâ€ loop may keep a raw parse (it must preserve non-keeper rows on other tracks). Add a comment why.
  Grep after: the only `json.loads` of `sections.jsonl` should be schema, Save-other-tracks, hear, and tests.

- [x] **P1.4 Stop inventing figure identity on blank Save.** `stamp_box` today forces `figure_id="{role}-A"` and `form="A"`. For function roles (`intro/build/breakdown/blast/chill/outro`) empty `figure_id` must stay empty unless the human typed one. Figure roles (`riff/hook/solo/pulse`) may default `"{role}-A"` only when blank. Add tests. Do not rewrite the existing 6 Rebirth rows.

- [x] **P1.5 Blast in the â€œall rolesâ€ test.** `tests/test_schema.py` `test_canonical_role_returns_none_for_unmappable` iterates roles and includes `blast`. Include every member of `ROLES`.

---

## P2 â€” docs stop lying

Living docs after this pass: `USER.md` (operator), `LAW.md` (rules), `CURRENT.md` (short contract), `README.md` (install + commands), `STATUS.md` (generated counts), `CHANGELOG.md` (dated history). Nothing else claims to be source of truth.

- [x] **P2.1 LAW.md â€” fix false rules.**
  - â€œStudio Save is the only writer of `sections.jsonl`â€ is false. Writers are: studio Save, `boo-lab hear`, album-remove. List them. Machines still never write keepers.
  - Sources list = P1.1.
  - Keep: machines never label; GP7 native; no FLAC rename; no audio/GP/tokens in git.

- [x] **P2.2 USER.md Part A â€” make it readable.**
  - Fix the smashed â€œMarkâ€ paragraph (zoom / Aâ€“B loop / click-away / drag edges are separate sentences).
  - Keys printed once.
  - VAL: â€œdo not use VAL songs to train or to vote `prefer=`. You may still pin them. Rebirth is VAL and is already pinned; leave it.â€
  - Do not tell a new operator that VAL songs must never be opened. That contradicts the only gold file.

- [x] **P2.3 CURRENT.md â€” cut to a contract.** Move dated session notes (â€œLocal 2026-09-21 docs passâ€, commit hashes, pixel widths, Guess novel, predictor manifesto) into `CHANGELOG.md`. What stays in CURRENT:
  - keepers / drafts / writers
  - box fields
  - roles + overlap law
  - paths as *placeholders* not `C:\Users\RIGGUSPIG\...`
  - start commands without a username
  - data-written table
  - â€œmachines never labelâ€
  Target: well under 200 lines.

- [x] **P2.4 STATUS.md â€” counts only + one â€œnowâ€ paragraph.**
  - Delete the duplicated `# Status â€” 2026-09-21` header.
  - Counts block is whatever `boo-lab status` writes.
  - One short â€œnowâ€ blurb. Historical intern novels belong in CHANGELOG.
  - Test count = pytest output from P0.2.

- [x] **P2.5 README.md**
  - Replace absolute `C:\Users\RIGGUSPIG\...` with `<LAB>`, `<CORPUS>`, `<GP>`.
  - Command table matches `cli.py` subparsers (no ghost commands, no missing ones).
  - Thin install vs studio extras stated honestly (see P3.1).

- [x] **P2.6 Strip UTF-8 BOM** from `CURRENT.md`, `STATUS.md`, `README.md`, `CHANGELOG.md`, `constraints.txt`, `src/boo_lab/pack_snapshot.py`. Files stay UTF-8.

---

## P3 â€” install actually launches the studio

- [x] **P3.1 Declare real dependencies in `pyproject.toml`.**
  - core (pin + Save, no UI): `librosa`, `soundfile` (already)
  - new extra `studio`: `fastapi`, `uvicorn`, `python-multipart`
  - document that `guitarpro` is required for GP5 paths (put it on `studio` or a `gp5` extra â€” pick one and use it in setup.bat)
  - `setup.bat` installs `.[studio]` as well as intern/pitch/align
  - README thin path: `pip install -e ".[studio]"` is the minimum that can open http://127.0.0.1:8765

- [x] **P3.2 `[project.scripts]`** `boo-lab = "boo_lab.cli:main"` so docs that say `boo-lab doctor` are not prose.

- [x] **P3.3 `.env.example` placeholders only.**
  ```
  BOO_FLAC_ROOT=
  BOO_GP_ROOT=
  ```
  Comment: corpus root is `audio-corpus`, not a band folder.

- [x] **P3.4 Delete or neutralize machine-local leftovers.**
  - `src/boo_lab/WHERE.txt` â€” delete, or rewrite to placeholders. It still sets FLAC root to `born_of_osiris` (the ingest footgun).
  - `src/boo_lab/INSTALL.bat` â€” delete (root `INSTALL.bat` + `setup.bat` are enough) or make it call `setup.bat` with no hardcoded user path.
  - Grep `RIGGUSPIG` under `tools/boo-lab`. After this box the only hits should be CHANGELOG history if you insist on leaving old notes; prefer zero hits in code and operator docs.

- [x] **P3.5 `guess._gp5_roots()` â€” env only.** Remove the hardcoded `C:\Users\RIGGUSPIG\Desktop\god-tier-metal\...` fallbacks. Roots come from `BOO_GP_ROOT` (+ `gp5/` and `gp7/` children). Test with a fake env path. No Desktop walk.

---

## P4 â€” stop publishing the machine

- [x] **P4.1 `data/map.csv` is local-only.** Add it to `tools/boo-lab/.gitignore`. Stop committing absolute FLAC/GP paths and SHA-256 of a private corpus. Keep a `data/map.csv.example` with headers only (`album,track,...` â€” match `catalogue.FIELDS`).
  - If the operator needs the live map, it is regenerated by `boo-lab scan` + `hash`.
  - Do not put the current 71-row file back.

- [x] **P4.2 `gitutil.push_lab` â€” do not `git add -A` `data/`.** Add source + tracked label files explicitly (`sections.jsonl`, `holdout.csv`, `CATALOG.md` if still tracked). Never add `map.csv`, drafts, adapt, intern_rank. Push stays best-effort. Add a test that a fake repo with `map.csv` dirty does not stage it.

- [x] **P4.3 Confirm `.gitignore` covers:** `data/map.csv`, `data/drafts.jsonl`, `data/beats.jsonl`, `data/sync.jsonl`, `data/figures.jsonl`, `data/adapt.json`, `data/tabnotes/`, `work/`, `*.gp*`, `*.flac`. Example/fixture exceptions stay.

---

## P5 â€” studio / Save correctness (no redesign)

Chrome stays. No new buttons. No layout pass.

- [ ] **P5.1 Heard `gp-marker` / `figure-hash` round-trip in the studio API tests** (ties to P1.2). `POST /api/sections/{id}` with those sources + `heard=true` â†’ 200, `guess-accepted`, other tracks untouched.

- [x] **P5.2 Save side-effects stay non-fatal and logged.** `learn.record`, `adapt.rebuild_*`, `predict.maybe_train_on_save` are already `except Exception: pass`. Print a one-line `save-hook failed: adapt: ...` on failure so a silent no-op is visible in the studio process log. Do not fail the Save. Do not start training if `BOO_PREDICT_SAVE_TRAIN=0`.

- [x] **P5.3 `__init__._install_phrase_retune`.** Bare `except Exception: pass` hides a failed monkeypatch. Log the exception. If `phrase_spans` is required, fail import. If optional, say so in CURRENT one line.

- [x] **P5.4 USER / How copy already matches pin-then-drag.** Do not restyle `#wave` / pins / How drawer.

---

## P6 â€” predictor honesty

- [x] **P6.1 Name the scaffold.** `predict.py` / CURRENT / USER: v1 is a scaffold. It must not claim â€œexponentially smarterâ€ or â€œnorth starâ€ in operator copy. Operator line: â€œoptional draft source `keeper-model`. Needs non-holdout keepers before it is useful. Rebirth-only labs skip train unless `holdout_fallback` is explicit.â€

- [x] **P6.2 Default: do not train on holdout-only gold.** `holdout_fallback` stays opt-in (flag or env). A lab whose only keepers are VAL does not fine-tune on Save. Test that.

- [ ] **P6.3 No new heads, features, or intern steps.** Do not widen the Conv1d. Do not add columns.

---

## P7 â€” extract / engine boundary

- [x] **P7.1 `extract.load_human_sections` uses `load_section_rows`.** Keep `_BOO_LAB_TO_ENGINE_ROLE` (riffâ†’verse, hookâ†’chorus, pulse/blastâ†’None). Add a test that a pulse keeper is dropped for the engine and a riff keeper becomes verse.

- [x] **P7.2 Leave `sys.path` engine import.** Do not invent a second GP parser. Do not import `riff_model.py`.

---

## P8 â€” leftover code to delete, not wrap

- [ ] **P8.1 `gpif_to_gp5` remains unused.** Do not wire it. If CURRENT still says â€œstays unused,â€ that is enough. Do not add a CLI flag that writes GP5 from GP7.

- [ ] **P8.2 `data/remap_gp5.py`.** If unused by CLI/tests, delete or move under `tools/boo-lab/scripts/` and do not import it.

- [ ] **P8.3 Duplicate rebirth file.** `data/rebirth-sections.jsonl` vs `data/sections.jsonl` â€” if identical, document â€œreference snapshot, not the writer path.â€ Do not let any command write both.

---

## P9 â€” tests the bot must add (minimum)

- [ ] `test_schema.py`: SOURCES contains `gp-marker` and `figure-hash`; blast in all-roles; empty figure_id on function roles.
- [ ] `test_annotator.py` (or existing save tests): heard gp-marker â†’ guess-accepted; unknown source â†’ 400 whole save; other-track rows preserved.
- [ ] `test_guess.py`: `_gp5_roots` does not contain `RIGGUSPIG` or a hardcoded Desktop path.
- [ ] `test_gitutil.py`: `map.csv` not staged by `push_lab`.
- [ ] `test_predict.py`: Save train skipped when only holdout keepers exist and fallback is off.
- [ ] `test_extract.py`: load_human_sections goes through keeper law + role map.

Run `pytest -q` at the end of every box that touches `src/` or `tests/`.

---

## Do not do

- Do not pin more songs. That is the human.
- Do not run `interns` / Demucs / WhisperX / SongFormer in CI.
- Do not â€œfixâ€ Rebirth times.
- Do not add `lead` as a role. `lead` is an instrument.
- Do not invent `riff-blast-A`.
- Do not convert GP7 to GP5.
- Do not rename FLACs.
- Do not scrape tabs.
- Do not touch Forge/`Ww`.
- Do not expand CURRENT back into a diary after P2.3.

---

## Suggested `/next` order

1. P0.2 pytest number
2. P1.1 + P1.2 + P1.5 (schema + Save + tests)
3. P1.3 one-reader
4. P1.4 figure_id default
5. P3.5 guess roots
6. P3.1â€“P3.3 install truth
7. P3.4 + P2.6 path/BOM strip
8. P4.1â€“P4.3 git hygiene
9. P2.1â€“P2.5 docs
10. P6.1â€“P6.2 predictor copy + holdout default
11. P7.1 extract reader
12. P5.2â€“P5.3 log hooks
13. P8 leftovers
14. Final pytest + `boo-lab status` counts

One box per turn. Push if origin exists. Do not start the next box in the same turn.
