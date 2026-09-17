# PROTOCOL

Human pins: `data/sections.jsonl`
Machine drafts: `data/drafts.jsonl` (`boo-lab structure` — never overwrites pins)

- Figure roles (`riff hook solo pulse`) may overlap function roles (`intro build breakdown chill outro`).
- Same role on the same seconds is a mistake. `boo-lab audit` lists those.
- Pack only slices keeper boxes (`human` / `guess-accepted` / legacy untagged).
- Prefer GP5 for extract. Keep GP7 as a score you read. Export GP7 → GP5 if needed.
- Holdout tracks stay unpinned until you evaluate Guess.
- A keeper box is heard. Unheard drafts are dropped on Save.
- Identity on every keeper: `form` (large unit letter, default `A`) + `figure_id` (small,
  e.g. `riff-A`) + `role` (function) — all three on one box.
- `unique=true` for a single-use / through-composed figure; never reuse that `figure_id`.
- `instrument` (`rhythm`/`lead`/`bass`/`drums`/`synth`/`vocal`/`mix`) when two guitars differ.
- `start_bar`/`end_bar` = 1-based GP measures, filled only when the GP5 is the same cut
  (`match=yes`); never guessed from seconds.
- Session rule: one album side per sitting. Stop when you cannot name the figure in five words.
  Do not `hear`-migrate a track you did not re-listen.

## Old pins, drafts, compare

Old pins predate the `heard` flag: after you re-listen one track, flip its
already-keeper rows with `boo-lab hear --album X --track Y` (single track
only — never the whole catalog). Machine drafts for an album come from
`boo-lab structure --album X` (needs allin1; writes `data/drafts.jsonl`
only, never `sections.jsonl`), then score those drafts against the keepers
with `boo-lab compare --album X`. `boo-lab beats --album X` writes the
beat/downbeat grid. The interns are optional: `pip install -e ".[intern]"`
(allin1, beat-this, jams, mir_eval) — never default dependencies.

## File/tab witnesses

`match=yes` means you believe the cut. `sync_ok` (`boo-lab sync --album X --track Y`) means
the machine agrees the tab's clock is within 350 ms of the audio. Pins without `sync_ok` are
still valid if you heard them; extract users should prefer `sync_ok` tracks. `flac_sha256` in
`map.csv` pins a row to the exact file — `scan` hashes on rewrite and `boo-lab hash [--album]`
fills empties without rehashing.
