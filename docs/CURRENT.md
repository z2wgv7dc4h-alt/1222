# CURRENT

task: P10.1
phase: 10
status: DONE
last_pytest: 443 passed in 11.19s
note: engine/midi_export.py -- real Standard MIDI File export from a composed song, the file Reaper actually imports. Real per-section tempo track from song["tempo_map"] (X.6c), two double-tracked guitar takes, bass (own fretboard), lead (harmony-mode timed hit-for-hit against the rhythm motif's own cells; solo-mode timed at the exact even-8th-note spacing song.py's own note-count math implies, plus the legato tail's real per-note durations), and drums (real GM kick note via drums.note_for_role). Deliberately excludes section["fill"] since song.py never actually blends it into the assembled drum track -- exporting one would be new arrangement logic, not wiring. Tests cross-check pitches/hit-counts/tempo/drum-notes against the real song data (not just "a file was written"), plus 2 bad-input rejections. 443 passed in 11.19s (up from 428).
updated: 2026-09-08
