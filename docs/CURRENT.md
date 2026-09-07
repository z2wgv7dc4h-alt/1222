# CURRENT

task: P1.3
phase: 1
status: DONE
last_pytest: 10 passed in 0.03s
note: Ported pitch_to_fret onto Fretboard (from reference/ww-forge-prior-attempt/engine/tab_score.py) - lowest-string preference, then abs(fret_diff)+abs(string_diff)*2 cost from prev position. Deviates from source: raises ValueError on an unplayable pitch instead of fabricating a fret position. Added prefer-lowest-string, cost-minimization, and unplayable-rejection tests.
updated: 2026-09-08
