# Law

Labelling lab. Not the generator.

- Roles: intro, build, riff, hook, breakdown, solo, chill, pulse, outro.
- Human `sections.jsonl` beats Guess, GP markers, Demucs, librosa.
- Keepers are `heard`. Machines may draft (`data/drafts.jsonl`); they never label.
- `boo-lab structure` never writes `sections.jsonl` — drafts only.
- Figure hashes (`figures.jsonl`, `source=figure-hash`) are drafts; they never write `sections.jsonl`.
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
