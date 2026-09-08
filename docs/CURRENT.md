# CURRENT

task: P8.1 (superseded -- real .rpp generation, not live reapy)
phase: 8
status: DONE
last_pytest: 477 passed in 22.27s
note: engine/reaper_project.py -- song_to_rpp(song, path) writes a complete, directly-openable Reaper .rpp project entirely offline. Investigated the scope doc's originally-chosen reapy/reapy-boost live bridge first: made real progress (fully headless one-time bridge activation via HTTP-triggering Reaper's own web control surface, found and fixed two real upstream bugs), but the connection stayed unreliable in this environment with no further diagnostic visibility available. Verified with the user that nothing Phase 8 needs actually requires a live connection (REAPER's real -renderproject CLI flag handles rendering); pivoted to static .rpp generation. Built against REAL ground truth: had REAPER itself import this project's own song_to_midi output and save as .rpp, then reverse-engineered every field from that real file (including base64-decoding the <X> track-name block to confirm it's the standard MIDI meta-event, not assumed). Reuses midi_export's real event-extraction functions. VERIFIED END TO END: generated project opened in the user's real installed Reaper, confirmed via screenshot -- 5 correctly-named tracks, real note content, correct tempo, no errors. 477 passed (up from 464).
updated: 2026-09-08
