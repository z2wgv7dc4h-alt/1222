# CHANGELOG

Dated 2026-09-22. Older notes are in git (`git log -- tools/boo-lab/CHANGELOG.md`).

## 2026-09-22 — coach + next-act + new pin loops

- One muted coach line under the pins names the single next action; one `.next-act`
  outline marks the control it points at. Errors still win.
- A role pin (or 1 2 3 T 4 I B C P) creates a box and starts its A–B loop; the next
  figure letter is chosen by default (type the old id to reuse).
- Docs: USER Part A, the How panel, README Start, and CURRENT now state the coach,
  the Snap default, and the Guess brakes.

## 2026-09-22

- Empty gold is legal: `data/sections.jsonl` may have zero keepers until a human
  Saves a heard box. Keepers = `source in {human, guess-accepted}` AND `heard=true`.
- Rebirth is VAL (`data/holdout.csv`); its old rows were removed and are not restored.
  `data/rebirth-sections.jsonl` is a dead snapshot, never read as keepers.
- GP7 `.gp`/`.gpx` is read natively as GPIF; `.gp5` is not converted. One comparable-key
  normalizer (`normalize.track_key`) backs loose matching.
- Intern `extract` is skipped when there are zero keepers; pack / drums / vocals / jams
  read keepers only.
- Studio: double-click = zoom + A–B loop (never toggles heard); the song list shows
  VAL / off-clock / mix / album badges; the How panel is the Part A Mark list.
- Compare scores on VAL are diagnostics, not votes; VAL songs never vote `prefer=`.
- Quality gates warn in `audit.py`; they never label or block Save.
- Album-remove requires typing the album name; git push is labels only.
- Re-run `pytest -q`; do not freeze a test count in docs.

Contract: `CURRENT.md`. Operator: `USER.md`. Rules: `LAW.md`.
