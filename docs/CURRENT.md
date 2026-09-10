# CURRENT

task: real reference-corpus analysis + preset calibration ("feed songs, learn")
phase: cross-cutting (§17.6 preset-calibration workflow, now a real standalone tool)
status: DONE
last_pytest: engine/ 654 passed, 1 skipped; editor/backend/ 34 passed
note: Direct continuation of the same-day listening-feedback loop. After the real pedal-guitar architecture landed, user: "I think it needs me to be able to feed you songs and you learn from that." This formalizes the session's own ad hoc reference-MIDI analysis into a real, tested, standing capability, closing scope §17.6's own "not yet a standalone tool" gap.

New `engine/reference_vocab.py`: real, format-agnostic per-song analysis across THREE real input formats -- MIDI (`pretty_midi`), Guitar Pro `.gp*` (`pyguitarpro`, confirmed already installed), and audio (`librosa`/`audio_vocab.py`, with a real note-level vocabulary too via `basic_pitch` -- also already installed -- honestly flagged `structural_only` when transcription isn't available/fails). Real Krumhansl-Schmuckler key correlation reused directly from `audio_vocab.py`'s own profile arrays. A real, accumulating local corpus cache (`engine/data/reference_corpus.json`, committed -- derived statistics only, same precedent as the already-committed `midi_vocab.json`, never the source songs' own notes). `build_preset_from_corpus` averages real per-song interval vocabulary (one vote per song) and writes a real preset JSON file, auto-discoverable via the existing preset glob.

User separately confirmed looking up MIDI/tab files online for compositional-style research (personal, non-commercial, never reproduced in output) is fine, then asked for "as many as possible." Found gtptabs.com's real, freely-downloadable Guitar Pro archive; downloaded 16 real files across Born of Osiris/Veil of Maya/Infant Annihilator (stating filename/source/size per the download-permission rule), 11 of which parsed successfully (5 used a GPX sub-format this pyguitarpro version can't decompress -- dropped, not forced). Fed all 11 plus the user's original reference MIDI into the real corpus (12 references total) and built a real, corpus-calibrated preset (`labyrinth.json`: drop-G 7-string per scope's own real BoO tuning citation, phrygian, 172bpm real averaged tempo, real averaged interval vocab). Updated the stale `"boo": "djent"` alias (a leftover never actually calibrated against Born of Osiris) to point at it.

Caught and fixed two real bugs during implementation: `pretty_midi.estimate_tempo()` raising on a too-sparse file (now a real, honest `None` fallback) and numpy scalar types leaking into JSON-serialized results (explicit `float()`/`int()` casts added). `engine/tests/test_reference_vocab.py`: 12 new tests, synthetic self-constructed MIDI/GP/audio fixtures only (mirrors `test_audio_vocab.py`'s own documented strategy) -- never a real copyrighted file committed as a fixture.

Verified against real generated output: regenerated the demo song on `labyrinth` and rendered it via the existing fluidsynth+GeneralUser-GS pipeline, sent to the user.
updated: 2026-09-10

Remaining: Periphery references (gtptabs.com's Periphery page returned a persistent 502 from their own server -- not something to retry-hammer; worth trying again later or a different source), the 5 GPX files this pyguitarpro version can't decompress, and the broader remaining gaps from the earlier scope re-read (P10.2 Song JSON, small unwired devices, §17.2 dense-passage flagging, Phase 8's real audio-render pipeline beyond `.rpp`).
