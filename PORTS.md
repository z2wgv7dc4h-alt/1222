# Ports — read one section per task

Paths are under `/reference/`.

## Ww / Forge — `ww-forge-prior-attempt/engine/`

| Symbol | File | Port as |
|---|---|---|
| `VoiceLeader` | `theory.py` | pick / walk / move / stab. Do not rewrite. |
| `shade()` | `style_packs.py` | 0–1 dissonance reweight; never zero an interval. |
| IRVD | `style_packs.py` | Intro 1 bar; Destruction last quarter; rest Rep/Var. |
| ARC | `style_packs.py` | energy/register/dissonance/start-degree. density = `0.28 + 0.62 * energy`. |
| tunings | `theory.py` / packs | `drop_g_7` BoO, `drop_ab_7` Periphery, `drop_a_7` SOTS, `drop_b_7` VoM, `drop_e_8` (8-string, SoI-ish), `drop_c_6`, `standard_6`. MIDI from source. |
| `pitch_to_fret` | `tab_score.py` | lowest string, then `abs(fret_diff)+abs(string_diff)*2`. |
| scales | packs | add `cluster` (0,1,3,6,7,8,11) and `power` (0,5,7). |
| presets | packs | ids: groovy, djent, chill, tech, slam, melodic. Bands only in descriptions. |
| `keys_gen.py` | same | GM 90 pad, GM 56 orch hit. Pad root/5/8; stab + m10. |
| song JSON | packs | `{bpm, pack, tuning_key, sections:[{letter,style,bars,seed,pack,guitar,drums,tuning_key}]}` |
| flatten+pickup | packs | last 2 cells of A ← first 2 of B. |
| judge/retry | packs | hit count, PM ratio, kick-lock; reroll ≤N seeds. |

## djent-master — `djent-master/src/generic/scripts/app/utils/`

| Symbol | File | Port as |
|---|---|---|
| two-layer | `sequences.js` | rhythm = when/rest; timbre = what + stickiness. |
| cell-tile polymeter | `loopSequence` | odd cell tiled into longer span, last tile truncated. Not 3:4 over one bar. |
| metric polyrhythm | separate fn | two fixed grids over one bar. Different name + tests. |
| shared sequence | utils | instruments share a rhythm id; pitch independent. |

## Keep ideas only
- metalerator: section pipeline concept, riff→bass, kick-follows-guitar in breakdowns, velocity band 97–103. Do not run the app.
- Anvil: optional dependency-free WAV preview later.
- react-chords: ignore; VexFlow is tab target.
- 123 / first Claude Code: `docs/RHYTHM_ENGINE_FIXES.md` as a bug-pattern note only.
