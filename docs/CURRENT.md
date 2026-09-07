# CURRENT

task: P4.1-P4.3, P5.1-P5.2
phase: 4-5
status: DONE
last_pytest: 189 passed in 0.30s
note: Phase 4 (Drums) and Phase 5 (Bass) both complete, built in parallel worktree agents alongside Phase 3 (Motif, still in progress). Drums: role->kit-MIDI map for the real SFZ kit with a wired CHINA->CRASH_2 fallback (no sample on this kit), kick-follows-guitar, blast fills (traditional/gravity/hammer) via the shared RhythmRegistry. Bass: derives its own tuning from the guitar's (anchors the bass's TOP string an octave below the guitar's lowest, then perfect 4ths down -- guarantees the bass sits below the guitar even for wide extended-range tunings), follows the guitar's rhythm exactly but resolves every hit to its own real, playable (string,fret) via the bass's own Fretboard, falling back to the nearest reachable octave rather than raising or fabricating. Also extracted a much larger real MIDI reference corpus (1967 files across jj_dreaming/jj_lakeside/jj_lamb/whack_breakdown, from a zip the user supplied) into reference/midi-corpus/ (gitignored) for the still-open P4.4.
updated: 2026-09-08
