# CURRENT

task: X.10
phase: cross-cutting
status: DONE
last_pytest: 482 passed in 13.03s
note: New preset "progressive" -- a real Periphery-styled melodic technical djent, the first preset to actually adopt X.6d's major-family scales (lydian, added but unused until now). Uses djent's own real mechanisms (group=3 displacement, euclid kick, octave stabs) with lydian's bright color instead of djent's deliberately un-melodic root/5th vocab. Calibrated against the real user-supplied reference track (X.7): drop_a_7 tuning chosen because its open low string is pitch class A, matching the track's real measured A-major key; lydian chosen over plain major for the track's bright/articulate tone. Verified real generated output is genuinely scale-legal (every pitch class fell within A-lydian's exact interval set, zero exceptions). Also fixed the stale "periphery" alias (presets.ALIASES) that pointed at "chill" as a proxy since no real match existed -- now points at "progressive". Two tests updated to match (test_presets.py, test_song.py). 482 passed in 13.03s (up from 477).
updated: 2026-09-08
