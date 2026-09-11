# DECISIONS

Facts only. Overturned lines stay here so nobody “rediscovers” them.

## Keep

- Symbolic writer, fretboard-legal notes, seeded RNG, no vocals.
- Do not edit Ww. Do not extend `123`.
- Steal methods, not datasets. No Songsterr automation (declined twice).
- No DadaGP/ProgGP without author access (gated).
- Reaper is the renderer. Editor is not Reaper.
- Guided = same params as Pro.
- Slam preset removed. IA devices (blasts, pinch, half-time) may exist as devices.
- Power chords fatten at **MIDI export only**. Judge/bass see one pitch.
- X.35 70% verbatim theme reuse.
- Labyrinth = BoO listening preset. Bank is the writer for that preset’s main riff.
- P8.1 static `.rpp` instead of live reapy daemon.

## Kill / ghetto

- Audio model as composer (Suno etc.).
- Local Transformer on ~70 songs (`riff_model.py`) — v20 was nonsense. File may stay; no import from `song.py`.
- Growing Markov as the product path.
- Role-bag 1-bar collage as “BoO.”
- Silent Markov when a labyrinth role has no fragments — must become hard-fail or drop the role.
- `/next` walking a novel. Queue is `TASKS.md` ## Now only.
- “Have you used all data?” as a session starter.

## Scope vs reality

Scope said: every note from theory, no pre-made MIDI.  
Labyrinth bank **is** pre-made GP bars. That is the product for BoO. Other presets may stay theory/Markov and must be labelled as such.

## Listen vs tests

Pytest proves wiring. User ear proves a riff. STATUS may not tick “sounds like BoO.”
