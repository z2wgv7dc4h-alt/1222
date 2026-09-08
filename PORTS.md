# Ports — read one section per task

Paths are under `/reference/`.

## Ww / Forge — `ww-forge-prior-attempt/engine/`

| Symbol | File | Port as |
|---|---|---|
| `VoiceLeader` | `theory.py` | pick / walk / move / stab. Do not rewrite. **Ported (P1.10, DONE).** |
| `shade()` | `theory.py` | 0–1 dissonance reweight; never zero an interval. Corrected from `style_packs.py` (only holds PACKS/VOCAB) after reading the file. **Ported (P1.10, DONE).** |
| IRVD | `theory.py` (`phrase_plan`) | Intro 1 bar; Destruction = `bars // 4` floor, min 1; remainder splits Rep/Var, odd bar to Variation. Corrected from `style_packs.py` -- real source found via a `riff_engine.py` comment ("see theory.phrase_plan"). **Ported (P2.7, DONE).** |
| ARC | `theory.py` | energy/register/dissonance/start-degree. density = `0.28 + 0.62 * energy`. Corrected from `style_packs.py`. **Ported (P1.10, DONE).** |
| tunings | `tab_score.py` (`TUNINGS`) | `drop_g_7` BoO, `drop_ab_7` Periphery, `drop_a_7` SOTS, `drop_b_7` VoM, `drop_e_8` (8-string, SoI-ish), `drop_c_6`, `standard_6`. MIDI from source. **Ported (P1.6, DONE).** |
| `pitch_to_fret` | `tab_score.py` | lowest string, then `abs(fret_diff)+abs(string_diff)*2`. **Ported (P1.2, DONE).** |
| scales | `theory.py` (`SCALES`) | add `cluster` (0,1,3,6,7,8,11) and `power` (0,5,7). Corrected from generic "packs" -- the reference `SCALES` dict lives in `theory.py`; this project's own `scales.py` is the single source of truth per anti-patterns.md, so `natural_minor` there resolves to this project's `minor`. **Ported (P1.4, DONE).** |
| presets | `style_packs.py` (`PACKS`, `VOCAB`, `ALIASES`) | ids ported from the source: groovy, djent, chill, tech, melodic (`slam` was removed post-port per user direction -- this project targets djent/deathcore/metalcore/technical deathcore, not slam). `metalcore` and `deathcore` were added afterward as NEW presets, not ported (not in the original source) -- designed from scratch, documented as such. Bands only in descriptions. Real per-style bpm/bars/feel/open_chance/kick/group/pedal live in `PACKS`; weighted interval vocab + motion live in `VOCAB`; old band-linked ids resolve via `ALIASES`. **Ported (P1.7, DONE); metalcore/deathcore added later.** |
| `keys_gen.py` | same | GM 90 pad, GM 56 orch hit. Pad root/5/8; stab + m10. |
| song JSON | `song_writer.py` | `{bpm, pack, tuning_key, sections:[{letter,style,bars,seed,pack,guitar,drums,tuning_key}]}` |
| flatten+pickup | `song_writer.py` (`flatten`, `pickup`) | `pickup`: last 2 slots of prev copy first 2 of next. `flatten`: concatenates all sections' guitar/bass/drums, inserting a bridge between each pair and a crash (note 49) on the first drum slot of every section after the first. Corrected from generic "packs". |
| judge/retry | `riff_engine.py` (`judge`) | `hits`=non-empty guitar slots; `pms`=hits with velocity<110 (palm-muted); `kicks`/`locked`=drum slot has note 36 (kick), locked when it coincides with a muted guitar hit; `pm_ratio=pms/hits`, `kick_lock=locked/max(1,pms)`; `ok = hits>=4 and 0.25<=pm_ratio<=0.95 and kick_lock>=0.25`. Reroll up to 6 seeds when not ok. Corrected from generic "packs". |

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
- 123 / first Claude Code: treat as a bug-pattern cautionary reference only, do not extend it. (A `docs/RHYTHM_ENGINE_FIXES.md` was referenced here previously; it does not exist anywhere in this repo or `/reference` -- likely lives only inside the separate `123` repo itself, which isn't checked out here. Unverified; don't chase it.)
