# Status

Canonical detail: **CURRENT.md**; commands in **README.md**.

<!-- status:counts:start -->
## Counts (from disk)

- keepers: 0 row(s) across 0 track(s)
- holdout: 7 song(s) reserved
- identity: 71 row(s)
- audit warnings: 8
- prefer=: none
- drafts: 1659 row(s); sources: msa-draft, songformer-draft, tabnotes-density
- sync: 20 ok / 54 row(s)
- map.csv: 72 row(s)
- figures: 659 row(s) across 41 track(s)
- tempo hints: 2 row(s) across 1 track(s)
<!-- status:counts:end -->

**Now:** Live keepers are empty until a human Saves a heard box (the six invalid Rebirth rows were deleted; Rebirth stays VAL/holdout). GP7 `.gp`/`.gpx` extract reads GPIF first; figure clusters fuzzy-merge by `bar_fp` ingredient Jaccard (`FIGURE_JACCARD` 0.80); Guess drops unique hashes once a repeating figure exists. **597 tests** pass (`pytest -q`).
