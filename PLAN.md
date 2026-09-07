# PLAN

## Architecture
```
preset JSON → Fretboard + Scale + RNG(seed)
     → Rhythm layer (cells / tile-polymeter / polyrhythm / blasts)
     → Pitch layer (VoiceLeader + motif contour)
     → Structure (sections, flatten+pickup, judge)
     → MIDI / preview
     → Reaper buses (gtr/bass/drums separate) + NAM/sfizz
     → Editor talks to engine over localhost
```

## Built vs intended
- Built: Phase 0 (repo), Phase 1 (tonal+presets: fretboard, scales, tunings, presets, VoiceLeader/shade/ARC, chord solver), Phase 2 (rhythm: two-layer gen, polymeter, polyrhythm, tuplets, blasts, shared rhythm id, IRVD). 159 tests passing on `main`. Phases 3-5 (motif, drums, bass) in progress. Reference code exists under `/reference`. Assets exist under `/assets`.
- Intended: engine complete through Phase 7 before editor or mix polish.

## Phases (exit test)
0. Repo + pytest hello — `pytest` collects ≥1 pass; assets present. **DONE.**
1. Tonal+presets — unplayable note rejected; invalid JSON rejected; glob loads every preset; scales unique; VoiceLeader/shade/ARC ported and density derived not settable; chord-shape solver returns real fingerings only. **DONE (159 passed).**
2. Rhythm — seed-identical; 7-into-16 tile drifts; polyrhythm ≠ tile fn; tuplets real grids; zero-weight blast type never picked; IRVD matches the real `phrase_plan` source exactly. **DONE (159 passed).**
3. Motif — same contour at two roots; develop keeps rhythm/pitch length equal; cross-section theme id reused; call-and-response references another part's hits; chord solver actually called from the riff path.
4. Drums — roles map + fallback (no China sample -> falls back to a configured substitute); kick locks guitar accents on breakdown fixture; fills/blasts reuse a shared rhythm id.
5. Bass — own fretboard (not a copy of guitar's); follows guitar's rhythm exactly; own playability via its own `pitch_to_fret`, falls back to nearest reachable octave rather than raising or fabricating.
6. Structure — weighted form incl. an atmospheric-interlude section type; flatten+pickup; wired modulation; judge fails a bad fixture; tempo curve exists as internal song data even though Reaper export stays one constant tempo (§17.5).
7. Atmosphere — GM pad/hit first; synth copies motif contour.
8. Reaper — separate buses; one FX chain applies; no premix; reapy-boost (not unmaintained reapy); Surge XT + Supermassive per §14.1.
9. Editor — timeline + guided sliders + preview; section-level save/load presets distinct from song-level style presets.
10. Export — MIDI stems + song JSON + full export matrix (tab/notation PDF, .rpp) per §14.2 items 10-11.

## Non-goals
Vocals. Audio-model-as-writer. Visible Reaper as the editor. Mix heroics before Phase 3 data is real.
