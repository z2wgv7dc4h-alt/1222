# PROTOCOL — pinning rules

Human pins: `data/sections.jsonl` (keepers). Machine drafts: `data/drafts.jsonl` — never keepers.

## A keeper box

- Written by the studio **Save** only, keepers only: `source` is `human` or `guess-accepted`
  **and** `heard=true`. Unheard boxes are dropped; `guess` / `msa-draft` / `songformer-draft`
  are dropped (a heard draft becomes `guess-accepted`).
- Fields: `start end role layer form figure_id unique instrument start_bar end_bar source heard`.
- Identity all three: `form` = large-scale letter (`A`, `B`, `A'`); `figure_id` = small figure
  (`riff-A`; a returning figure keeps its id); `role` = function
  (`intro build riff hook breakdown solo chill pulse outro`).
- `unique=true` for a single-use / through-composed figure; do not reuse that `figure_id`.
- `instrument` (`rhythm`/`lead`/`bass`/`drums`/`synth`/`vocal`/`mix`) when two guitars differ.
- `start_bar`/`end_bar` = 1-based GP measures, filled on Save only when the GP5 is the same cut
  (`match=yes`); never guessed from seconds.

## Overlap

- Figure roles (`riff hook solo pulse`) and function roles (`intro build breakdown chill outro`)
  **may overlap each other**.
- Two boxes of the **same** role overlapping by more than 50 ms is rejected with the pair listed.

## Rules

- Prefer GP5 for extract; GP7 is eyes / export-to-GP5.
- Holdout tracks stay unpinned.
- Old pins without `heard` are not keepers until `boo-lab hear --album X --track Y`
  (one track, never the whole catalog).
- Session: one album side per sitting. Stop when you cannot name the figure in five words.
