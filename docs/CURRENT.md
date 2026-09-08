# CURRENT

task: X.12
phase: cross-cutting
status: DONE
last_pytest: 499 passed in 13.18s
note: Real, critical bug fix: the tempo_map's metric-modulation half-time (X.6c) modulated once at the first build->breakdown transition and NEVER REVERTED, so any song revisiting the breakdown role (real for any longer song) got stuck at half tempo for the rest of the song. Found via direct listening feedback on a 16-section demo ("drums are too slow... its not really metal") -- confirmed by inspecting the real tempo_map (14 of 16 sections locked at 76 BPM instead of 152), which also explained "no solos" (they were real and present, just playing at half-speed since both solo sections landed inside the permanently-halved zone). Fixed song._compute_tempo_map to apply the real half-time modulation independently to every breakdown-role section and revert to full base_bpm for every other role, including immediately after a breakdown. Removed the now-obsolete _build_to_breakdown_index; rewrote the tempo-map tests to verify real per-section modulation AND real reversion. 499 passed (down 1 from 500 due to test consolidation, not reduced coverage). Regenerated and sent the corrected demo.
updated: 2026-09-08
