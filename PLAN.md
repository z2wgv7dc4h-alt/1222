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
- Built: nothing in this clean repo. Reference code exists under `/reference`. Assets exist under `/assets`.
- Intended: engine complete through Phase 7 before editor or mix polish.

## Phases (exit test)
0. Repo + pytest hello — `pytest` collects ≥1 pass; assets present.
1. Tonal+presets — unplayable note rejected; invalid JSON rejected; glob loads every preset; scales unique.
2. Rhythm — seed-identical; 7-into-16 tile drifts; polyrhythm ≠ tile fn; tuplets real grids.
3. Motif — same contour at two roots; develop keeps rhythm/pitch length equal; cross-section theme id reused.
4. Drums — roles map + fallback; kick locks guitar accents on breakdown fixture.
5. Bass — own fretboard; follows guitar rhythm, own playability.
6. Structure — weighted form; flatten+pickup; wired modulation; judge fails a bad fixture.
7. Atmosphere — GM pad/hit first; synth copies motif contour.
8. Reaper — separate buses; one FX chain applies; no premix.
9. Editor — timeline + guided sliders + preview.
10. Export — MIDI stems + song JSON.

## Non-goals
Vocals. Audio-model-as-writer. Visible Reaper as the editor. Mix heroics before Phase 3 data is real.
