# CURRENT

task: X.9
phase: cross-cutting
status: DONE
last_pytest: 464 passed in 10.96s
note: Real snare backbeat, wired for EVERY preset (not metalcore-specific) -- closes a real gap: this engine had kick + blast/fill patterns but zero snare/hihat layer. Ported from the same real reference source as X.8 (reference/metalerator/metalerator/drums/snare/snare.py): "step" (half-time, beat 3 of every bar -- checked the real source, not the generic "2 and 4"), "half_step" (once per 2 bars), "double_time" (every beat except the section's first). Built on the same real cell-timeline mechanism two_step's kick style already used, extracted into shared helpers (_cell_starts/_time_to_cell_index/_cyclic_hit_indices) with two_step refactored onto them -- no duplicated logic. Wired via a real per-role dispatch (drums.snare_pattern_for_role): breakdown/intro/outro get the half-time backbeat, build/solo get double_time, chill/interlude silent (matching lead_mode's existing judgment call for those roles). Wired into song.py (section["snare"]) and midi_export.py's Drums track (real GM 36/38 notes). 464 passed in 10.96s (up from 450).
updated: 2026-09-08
