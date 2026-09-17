# Law

Labelling lab. Not the generator.

- Roles: intro, build, riff, hook, breakdown, solo, chill, pulse, outro.
- Human `sections.jsonl` beats Guess, GP markers, Demucs, librosa.
- Keepers are `heard`. Machines may draft (`data/drafts.jsonl`); they never label.
- `boo-lab structure` never writes `sections.jsonl` — drafts only.
- Overlap **different** roles. Do not stack the same role on the same seconds.
- Pulse = named synth/keyboard figure, not “keys are audible.”
- Breakdown = function (usually drums half-time), may sit on the same guitar as Riff.
- GP7 / Songsterr `.gp` is not a marker source. Prefer `.gp5`.
- Do not rename FLACs. Match tabs in `map.csv` instead.
- Do not train a song model on raw mixed FLACs.
- Do not put audio, Guitar Pro, or tokens in git. `data/` labels are fine.
- Do not scrape tabs.

New bands go in `audio-corpus/<band>/`, tabs in `gp-tabs/gp5/<band>/`.
