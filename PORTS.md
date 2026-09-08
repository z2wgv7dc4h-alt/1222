# Ports — read one section per task

Paths are under `/reference/`.

## Ww / Forge — `ww-forge-prior-attempt/engine/`

| Symbol | File | Port as |
|---|---|---|
| `VoiceLeader` | `theory.py` | pick / walk / move / stab. Do not rewrite. **Ported (P1.10, DONE).** |
| `shade()` | `theory.py` | 0–1 dissonance reweight; never zero an interval. Corrected from `style_packs.py` (only holds PACKS/VOCAB) after reading the file. **Ported (P1.10, DONE).** |
| IRVD | `theory.py` (`phrase_plan`) | Intro 1 bar; Destruction = `bars // 4` floor, min 1; remainder splits Rep/Var, odd bar to Variation. Corrected from `style_packs.py` -- real source found via a `riff_engine.py` comment ("see theory.phrase_plan"). **Ported (P2.7, DONE); actually WIRED (X.19, DONE)** -- the P2.7 port sat completely unconsumed (found via a whole-engine grep) until X.19 built `motif._generate_irvd_motif` to call it. |
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

## Metalerator — `reference/metalerator/metalerator/`

| Symbol | File | Port as |
|---|---|---|
| breakdown duration weights | `rhythm_guitar/breakdown/default_melodic.py` (`RGuitarDefaultMelodicBreakdown.randomize_duration`) | real [0.25,0.5,1,2] draw weights, adapted to this project's [0.25,0.5,1.0] vocab. **Ported (X.8, DONE)**, wired for every preset via `rhythm.FEEL_DURATION_WEIGHTS`. |
| no-isolated-16th rule | same file, companion rule | a lone 0.25 draw is never followed by a longer one -- forces pairing. **Ported (X.8, DONE)** via `rhythm.FEEL_NO_SINGULAR_SHORT`/`no_singular_short`. |
| snare styles | `drums/snare/snare.py` (`Snare.snare_step`/`snare_half_step`/`snare_double_time`) | `step`=beat 3 of every bar (`i%4==2`, half-time, not generic "2 and 4"); `half_step`=downbeat of every 2nd bar (`i%8==4`); `double_time`=every beat except the first (`i%1==0 and i!=0`). **Ported (X.9, DONE)**, wired for every preset via `drums.snare_pattern_for_role`. |
| double bass kick | `drums/kick/kick.py` (`Kick.double_bass`) | continuous straight-16th pulse, four hits/beat unconditionally. **Ported (X.11, DONE)** as `drums._kick_double_kick`, used as the `build`/`solo` role overlay for every preset. |
| crash-on-pattern-change | `drums/breakdown/default_melodic.py` (`should_add_opening_cymbals`) | fires a crash when the kick/snare pattern differs from the previous section's. **Ported (X.13, DONE)** as `drums.add_transition_crash`/`song._develop_theme`'s role-change check, generalized to this project's role-based arrangement unit. |

Snare ghost notes (quiet grace-note hits around the main snare) are a real Metalerator technique not yet ported -- doesn't fit this project's fixed-cell-array model without a larger rework. Section pipeline concept, riff-follows-bass, and the 97-103 velocity band remain unported ideas only.

## Keep ideas only
- Anvil: optional dependency-free WAV preview later.
- react-chords: ignore; VexFlow is tab target.
- 123 / first Claude Code: treat as a bug-pattern cautionary reference only, do not extend it. (A `docs/RHYTHM_ENGINE_FIXES.md` was referenced here previously; it does not exist anywhere in this repo or `/reference` -- likely lives only inside the separate `123` repo itself, which isn't checked out here. Unverified; don't chase it.)
