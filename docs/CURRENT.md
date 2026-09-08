# CURRENT

task: X.14
phase: cross-cutting
status: DONE
last_pytest: 506 passed, 1 skipped in 12.73s
note: Real 4-state theme-development rotation. Root cause of real listening feedback ("not much is going on"): ThemeRegistry keys a base theme by ROLE alone, and every occurrence of a role for the whole song only alternated between 2 pitch states (base/invert). motif.transpose already existed, real and tested, but was never wired into this rotation. Added song._develop_theme: real 4-state rotation (base/invert/transpose+2/transpose+invert), safe and length-preserving. Verified against real generated output: a role recurring 6 times went from a 2-state ceiling to 4 real distinct states. 506 passed (up from 504). Sent updated demo. Honest scope note: this addresses pitch/harmonic repetition; rhythm-level repetition (same base cell reused per role, just pitch-shifted) is a separate, deeper, not-yet-attempted question. Also confirmed with the user that they've been listening to .mid demos via Windows' default GS Wavetable synth, which likely explains a large share of "weird/basic" independent of composition quality -- real instrument setup (NAM + sfizz in Reaper) still pending, tied to the already-tracked P8.3 FX-chain work.
updated: 2026-09-08
