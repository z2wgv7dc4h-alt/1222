# CURRENT

task: X.13
phase: cross-cutting
status: DONE
last_pytest: 504 passed, 1 skipped in 12.75s
note: Real hihat variation (open-hat accents + section-transition crashes), grounded in a real finding: ran demucs on a real user-supplied reference track, then classify_drum_onsets on the isolated drum stem -- cymbals/hihat were 84% of all detected drum onsets, by far the most constantly-present element in a real mix, while the engine's hihat (X.11) had zero variation. Added drums.apply_hihat_accents (real open-hat accents at the same structural-accent positions octave stabs already use) and drums.add_transition_crash (real crash at a section's opening when its role changes, ported from Metalerator's real "crash on pattern change" technique). Wired into song.py for every preset. 504 passed, 1 skipped (up from 499). Regenerated and sent the demo: 14 real crashes, 20 real open-hat accents, 311 closed hihat hits. Guitars ("too simple") flagged by the user as still open, not yet investigated.
updated: 2026-09-08
