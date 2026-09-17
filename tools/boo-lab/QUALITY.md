# boo-lab quality bar

Goal: the first public-grade metal structure corpus that can say
“this guitar figure, this drum function, this named pulse, this GP5 bar,
on this stereo mix, heard by a human.” Harmonix cannot write that sentence.
Sargon cannot. SongFormer cannot.

If a row cannot survive that sentence, it does not ship.

## Unprecedented means

Not “more models.” It means every keeper box has all five:

1. **Identity** — album, track, start, end (seconds, 2 dp).
2. **Layer** — `figure` or `function` (overlap allowed only across layers).
3. **Object** — `role` + `figure_id` (`riff-A` stays `riff-A` when it returns).
4. **Provenance** — `source=human` or `guess-accepted`, plus `heard=true`.
5. **Witness** — a Pack clip exists and was played.

Missing any one → not a keeper. Drafts may exist. They are not the set.

## Hard gates (fail closed)

- Same role, overlapping seconds → reject (`audit`).
- Box shorter than 1 s → reject unless it is a real sting you can name.
- `match=yes` without a file that `pyguitarpro` opens as GP3/4/5 → reject.
- `.gp` / `.gpx` named `.gp5` → reject (content sniff).
- Holdout track in `sections.jsonl` → reject.
- `boo-lab structure` writing `sections.jsonl` → that binary is banned.
- Unheard Guess or MSA box saved as human → reject.
- Extract / Pack reading `source=guess` or `msa-draft` → reject.

## Protocol (SALAMI discipline, metal words)

Pin in this order, one album at a time:

1. Confirm the FLAC is the studio cut the tab describes (not live, not instrumental-only unless labeled).
2. Find the first clean statement of each guitar figure. Box it. `figure_id=riff-A`.
3. When that figure returns, new box, **same** `figure_id`.
4. If drums change function on the same guitar, overlap `breakdown` (or `build` / `chill`). Do not clone the riff box.
5. Pulse only if you can name the loop in five words.
6. Hook only if something is singable or is the chorus guitar hook. Loud ≠ hook.
7. Save. Run `audit`. Fix overlaps. Pack. Listen to 3 random clips cold.

A week later, re-pin one track without looking. Write disagreements in `data/agree.jsonl`:
`{track, boundary_err_sec, role_agree, figure_id_agree, note}`.
That file is your inter-annotator stand-in. Two people is better.

## What “done” is for an album

Not 100% Guess overlap. This:

- Every non-holdout track you care about has keeper boxes.
- `audit` same-role overlaps = 0.
- Heard ≥ 80% of keeper boxes.
- Pack index has a mix clip per keeper box.
- GP5 `match=yes` tracks: you checked one riff box against the tab by ear.
- Holdout tracks: zero pins.

One album at that bar beats a full discography of Guess.

## Interchange (when the album is done, not before)

Export keepers to JAMS, two annotations per file:

- `segment_open` / custom namespace `segment_lab_figure` — riff, hook, solo, pulse + `figure_id`
- `segment_lab_function` — intro, build, breakdown, chill, outro

Then you can run `mir_eval` hit-rate at 0.5 s and 3 s against Guess/allin1/SongFormer
**without letting those models into the jsonl.** That comparison is how you prove
the set is stricter than SOTA, not how you build the set.

## Machines (interns)

| Tool | Allowed to do | Forbidden |
|---|---|---|
| Guess (GP5 + drums) | Draft boxes in the UI | Write keepers |
| allin1 / SongFormer | `drafts.jsonl` only | Name a riff |
| Demucs | Stems for Pack / Guess drums | Structure labels |
| WhisperX | Lyric lane | Riff identity |
| GP7 | Your eyes; optional export-to-GP5 | Extract input until a GP7 parser is a separate, tested ticket |

## Scope that would *lower* quality

- Pinning every band before one album is clean
- GP7 parser month
- Training on mixed FLACs
- Auto figure_id
- More Guess backends so drafts “look complete”
- Labyrinth / writer work that consumes dirty pins

## The sentence you are allowed to say

“This is a single-annotator, holdout-gated, GP5-matched, overlapping
figure/function corpus of albums I own, with Pack witnesses and a
test–retest log. Machines may draft. They do not label.”

Until the gates are green on disk, do not say cutting-edge. Say building.
