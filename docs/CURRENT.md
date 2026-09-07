# CURRENT

task: X.1 (song.py integration) + Phase 7 bookkeeping
phase: cross-cutting
status: DONE
last_pytest: 313 passed in 2.95s
note: Phase 7 (Atmosphere) merged. Then did a full review pass and found the biggest real gap so far: every phase (1-7) built and pytest-verified its own mechanism in isolation, but nothing had ever taken a real Preset (presets.load_all_presets) and threaded it through one real end-to-end generation run. Built engine/song.py::compose_song(preset_id, seed) closing this -- wires tuning/Fretboard/Scale, section sequence, per-section motif+arc modulation, double-tracked rhythm guitar, lead guitar (theory.VoiceLeader via lead.py -- also previously unwired anywhere), kick+vocabulary-informed fills, bass locked to guitar rhythm, atmosphere pad/stabs, and judge/retry -- a real four-piece band (2x rhythm guitar + lead + bass) plus drums and atmosphere per section. engine/tests/test_song.py exercises this for every real preset and passed on the first run, confirming independently-built modules actually compose correctly. Also found and fixed: pyproject.toml still declared zero dependencies even though drums.py (imported almost everywhere) now hard-imports midi_vocab->mido at module level -- added mido>=1.3.0 to pyproject.toml to match requirements.txt. Remaining honest gap, tracked as X.2: preset.kick/group/pedal/octave_stab are validated but nothing branches on them yet (kick_follows_guitar is one fixed algorithm regardless of a preset's kick style name; djent's 3-against-4 grouping and pedal-note behavior aren't implemented).
updated: 2026-09-08
