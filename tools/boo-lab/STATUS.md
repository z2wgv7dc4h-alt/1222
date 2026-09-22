# Status

Canonical detail: **CURRENT.md**; commands in **README.md**.

<!-- status:counts:start -->
## Counts (from disk)

- keepers: 6 row(s) across 1 track(s)
- drafts: 1659 row(s); sources: msa-draft, songformer-draft, tabnotes-density
- sync: 20 ok / 54 row(s)
- map.csv: 72 row(s)
- figures: 659 row(s) across 41 track(s)
- tempo hints: 2 row(s) across 1 track(s)
<!-- status:counts:end -->

**Now:** GP7 `.gp`/`.gpx` extract reads GPIF first (cell hits carry hammer/dead); figure clusters fuzzy-merge by `bar_fp` ingredient Jaccard (`FIGURE_JACCARD` 0.80), and Guess drops unique hashes once a repeating figure exists. **524 tests** pass (`pytest -q`).
