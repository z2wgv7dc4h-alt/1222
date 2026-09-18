# Law

Labelling lab. Not the generator.

- Roles: intro, build, riff, hook, breakdown, solo, chill, pulse, outro.
- Human `sections.jsonl` beats Guess, GP markers, Demucs, librosa.
- Keepers are `heard`. Machines may draft (`data/drafts.jsonl`); they never label.
- `boo-lab structure` never writes `sections.jsonl` — drafts only.
- Figure hashes (`figures.jsonl`, `source=figure-hash`) are drafts; they never write `sections.jsonl`.
- Learn/rank may choose a draft intern; it still never labels (never writes `sections.jsonl`).
- `boo-lab interns` only orchestrates the existing intern steps (structure/beats/drums/vocals/lyrics/sync/extract/figures/compare/learn/status); it inherits their law and never writes `sections.jsonl`.
- Pin layer vs cell layer: human boxes + `figure_id` are the pin layer (a repeat may be one box or many boxes sharing an id). Extract/bank stores the shortest repeating cell inside that figure (2–4 bars). Pack slices the human box for listening. Do not dump a 40 s riff box into the bank as one fragment.
- GP7 / Songsterr `.gp` is not a Guess marker clock. Prefer GP5 for markers. GP7 MAY feed extract and figure hashes after a deterministic export-to-GP5. Guess still drops markers when `sync_ok` is false.
- Overlap **different** roles. Do not stack the same role on the same seconds.
- Pulse = named synth/keyboard figure, not “keys are audible.”
- Breakdown = function (usually drums half-time), may sit on the same guitar as Riff.
- GP7 / Songsterr `.gp` is not a marker source. Prefer `.gp5`.
- Do not rename FLACs. Match tabs in `map.csv` instead.
- Do not train a song model on raw mixed FLACs.
- Do not put audio, Guitar Pro, or tokens in git. `data/` labels are fine.
- Do not scrape tabs.

New bands go in `audio-corpus/<band>/`, tabs in `gp-tabs/gp5/<band>/`.

## Quality bar

- A keeper is a **heard**, human or `guess-accepted` box a person can defend out loud: this
  figure/function, this `role` + `figure_id`, these seconds, on this mix.
- The studio **Save** is the only writer of `sections.jsonl`; it drops unheard boxes.
- Two boxes of the **same** role overlapping on the same seconds refuse the whole Save.
- Machines never write `sections.jsonl` (`structure`, Guess, learn/adapt and Pack are drafts or reads).
- Holdout / **VAL** songs do not vote for `prefer=` and are not training data.
- Rebirth is labelled holdout by design — its keepers are real but held out of training and `prefer=`.
- Prefer GP5 for markers; GP7 is eyes / export-to-GP5.
- A returning figure keeps its `figure_id`; a new idea gets a new id.
- Do not train on raw mixed FLACs. Do not scrape tabs.
