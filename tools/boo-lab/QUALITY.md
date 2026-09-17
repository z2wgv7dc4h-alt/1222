# boo-lab quality bar

Goal: say “this guitar figure, this drum function, this named pulse, this GP5 bar, on this
stereo mix, heard by a human.” If a row cannot survive that sentence, it does not ship.

## The five-field sentence (extended)

Every keeper box has all five:

1. **Identity** — album, track, start, end (seconds, 2 dp), plus `form` (large letter) and
   `start_bar`/`end_bar` when the GP5 is the same cut.
2. **Layer** — `figure` or `function`; overlap allowed only across layers.
3. **Object** — `role` + `figure_id` (a returning figure keeps the same `figure_id`), plus
   `unique` for a single-use figure and `instrument` when two guitars differ.
4. **Provenance** — `source=human` or `guess-accepted`, plus `heard=true`.
5. **Witness** — a Pack clip exists and was played.

Missing any one → not a keeper. Drafts may exist. They are not the set.

## Hard gates (fail closed)

- Same role, overlapping seconds → reject (`audit`).
- Box shorter than 1 s → reject unless it is a real sting you can name.
- `match=yes` without a file `pyguitarpro` opens as GP3/4/5 → reject.
- `.gp` / `.gpx` named `.gp5` → reject (content sniff).
- Holdout track in `sections.jsonl` → reject.
- `structure` writing `sections.jsonl` → banned.
- Unheard Guess / MSA / SongFormer box saved as human → reject.
- Extract / Pack reading `source=guess`, `msa-draft`, or `songformer-draft` → reject.
- Keeper box with `heard` missing → not a keeper until `boo-lab hear` (per track).

## The sentence you are allowed to say

“This is a single-annotator, holdout-gated, GP5-matched, overlapping figure/function corpus of
albums I own, with Pack witnesses and a test–retest log. Machines may draft. They do not label.”

Until the gates are green on disk, do not say cutting-edge. Say building.
