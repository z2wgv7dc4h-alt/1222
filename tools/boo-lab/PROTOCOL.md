# PROTOCOL

Human pins: `data/sections.jsonl`
Machine drafts: `data/drafts.jsonl` (`boo-lab structure` — never overwrites pins)

- Figure roles (`riff hook solo pulse`) may overlap function roles (`intro build breakdown chill outro`).
- Same role on the same seconds is a mistake. `boo-lab audit` lists those.
- Pack only slices keeper boxes (`human` / `guess-accepted` / legacy untagged).
- Prefer GP5 for extract. Keep GP7 as a score you read. Export GP7 → GP5 if needed.
- Holdout tracks stay unpinned until you evaluate Guess.
- A keeper box is heard. Unheard drafts are dropped on Save.

## Old pins, drafts, compare

Old pins predate the `heard` flag: after you re-listen one track, flip its
already-keeper rows with `boo-lab hear --album X --track Y` (single track
only — never the whole catalog). Machine drafts for an album come from
`boo-lab structure --album X` (needs allin1; writes `data/drafts.jsonl`
only, never `sections.jsonl`), then score those drafts against the keepers
with `boo-lab compare --album X`. `boo-lab beats --album X` writes the
beat/downbeat grid. The interns are optional: `pip install -e ".[intern]"`
(allin1, beat-this, jams, mir_eval) — never default dependencies.
