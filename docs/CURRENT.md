# CURRENT

task: X.11
phase: cross-cutting
status: DONE
last_pytest: 500 passed in 12.59s
note: Real hihat/cymbal layer + varied kick overlay for build/solo sections -- direct response to real listening feedback that generated drums felt basic (no cymbals at all, generic occasional kicks). Closed a total gap: through X.9 the engine had kick+snare but zero cymbal content anywhere. Added generate_hihat_pattern/hihat_pattern_for_role (real steady 8th-note pulse, wired for every preset, silent only for chill/interlude) and _kick_double_kick (ported from Metalerator's real double_bass) registered as a new "double_kick" style, plus kick_pattern_for_role/_ROLE_KICK_OVERRIDE_CHOICES so build/solo sections always get a real, varied double_kick-or-blast overlay (picked per section via real rng) regardless of the preset's own kick field. Wired into song.py, midi_export.py, and reaper_project.py's Drums track. Generated and sent two real demos including a 16-section/3:09 song (up from 8-section/1:28) testing whether length also helps. 500 passed in 12.59s (up from 482).
updated: 2026-09-08
