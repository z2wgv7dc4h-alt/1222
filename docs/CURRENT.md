# CURRENT

task: X.8
phase: cross-cutting
status: DONE
last_pytest: 450 passed in 10.76s
note: Wired preset.feel (validated since Phase 1, never consumed by generation until now). Investigated the real "Metalerator" reference source (reference/metalerator/ -- confirmed by its own README to be a dedicated metalcore generator, not generic) for a genuinely portable technique rather than inventing one: its real breakdown generator's weighted duration table (biased toward 8th/quarter over 16ths) and its "no isolated single 16th" pairing rule. Ported both into rhythm.py (duration_bias_for_feel/FEEL_DURATION_WEIGHTS/FEEL_NO_SINGULAR_SHORT, new opt-in generate_rhythm params, default-None fully backward compatible), threaded through motif.py and wired at song.py's preset.feel call site. Only "breakdown" (metalcore) has real ported data; other feel names intentionally stay uniform (no invented tables). Real A/B test against actual compose_song output (metalcore vs. an unmapped-feel variant) proves the 16th-note share measurably drops. 450 passed in 10.76s (up from 443).
updated: 2026-09-08
