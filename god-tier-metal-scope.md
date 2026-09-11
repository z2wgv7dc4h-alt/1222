<!-- BOTS: do not read this file end to end. Open one heading named by the ticket. Scope line "no pre-made MIDI" is overturned for labyrinth — see docs/DECISIONS.md. -->

# God Tier Metal — Djent / Tech-Deathcore Generation & Production Suite — Project Scope

## Goal
Build **God Tier Metal**, an original, from-the-ground-up djent/tech-deathcore/
progressive-deathcore generation and production tool — targeting Infant Annihilator
and Born of Osiris quality — spanning music-theory-driven composition, a
section-based drag-and-drop editor, and a full studio-quality Reaper render
pipeline. `metalerator` was the original seed/reference and is retained in §1 as
prior art we're building past, not as the project's identity. Everything downstream
(§2 onward) is our own design, informed by but not bound to any single source repo
reviewed along the way (djent-master, Anvil, react-chords, user-supplied drum kit,
etc).

Target: Python generation engine (local), React/TS editor UI (local), Reaper as the
studio-quality render backend via `reapy`. All musical content — every note, rhythm,
and chord voicing — is derived programmatically from music theory and the defined
fretboard/tuning model; nothing is sourced from pre-made MIDI, loops, or chord
lookup tables.

---

## 1. What we're keeping from `metalerator` as-is (it already works)

- Overall data model: notes as `{pitch, duration, position}` dicts, position in
  quarter-note units, written via `midiutil`.
- Palm-mute trigger note convention (12/14 for Ample Metal Hellrazer keyswitches).
- Section pipeline concept (intro → verse → pre-chorus → chorus → breakdown → outro),
  though the *implementation* becomes data-driven instead of hardcoded (see §5).
- Velocity humanization band (~97–103) as a baseline — will be extended, not replaced.
- Riff→bass derivation (bass doesn't compose independently, it follows guitar) — keep
  this, it's correct practice for the genre.
- Kick-follows-guitar-accent convention in breakdowns — keep, it's genre-accurate.
- Scale-as-interval-steps + `fill_scale()` approach — keep the mechanism, expand the
  scale library (§2).

## 2. Tonal/Harmonic layer — gaps to close

Current: 4 diatonic-family scales (minor, phrygian, harmonic minor, dorian, melodic
minor), one static root per song, fixed pitch range (root 29–38).

Add:
- **Dissonant/chromatic material**: chromatic runs, tritone/minor-2nd interval bias
  mode for slam sections (Infant Annihilator signature), whole-tone or locrian options
  for "wrong note" tension.
- **Extended range**: support down to ~8-string territory (lower floor than 29).
- **Key/tonal-center modulation** across sections — not just "same root all song."
  Needs a concept of "home key" vs "modulated key" per section, with controlled
  return.
- **Modal interchange** for choruses/leads (borrowing chords/notes from parallel
  major/minor) — this is a big part of what makes Born of Osiris sound "smarter"
  than straight minor-scale riffing.
- Style-gated scale palettes: slam presets restrict to chromatic/phrygian-dominant;
  prog presets open up to more color (lydian, harmonic major, etc).

## 3. Rhythm/Meter layer — gaps to close

Current: implicit 4/4 only, no tempo automation, no tuplets, no polymeter.

Add:
- **Time-signature-aware bar generation** (7/8, 5/4, 6/8, mixed-meter bars).
- **Polymeter/polyrhythm support**: e.g., a riff that repeats a 3-note or 5-note
  rhythmic cell against a 4/4 drum bed until it realigns (classic djent/Meshuggah-style
  device, core to Born of Osiris).
- **Tuplets** (quintuplets/septuplets) for fills and tech runs — currently only
  triplets exist, and only in one drum fill type.
- **Tempo automation**: mid-song tempo drops for slam breakdowns, tempo ramps for
  build-ups. Currently tempo isn't touched by the generator at all (left to the DAW).
- **Blast-beat family expansion**: traditional, gravity-blast-style (alternating
  kick/snare within a beat), and hybrid half-time-blast — current code has exactly 2
  blast variants at deliberately low probability; for Infant Annihilator-tier output
  blasts need to be a first-class, well-developed mode.

## 4. Riff-writing layer — gaps to close

Current: per-bar note choice is a probability roll (65/35 root-vs-high-note) constrained
by a "no more than 2 consecutive high notes" rule, re-rolled fresh per section with only
mechanical repetition-variation (octave drops, occasional last-chord swap).

Add:
- **Motif system**: generate a short thematic cell once (rhythm + contour, not fixed
  pitches) and *develop* it across sections (transposition, augmentation/diminution,
  inversion, fragmentation) instead of every section rolling independently. This is the
  single highest-leverage change for making songs sound "composed" rather than
  "generated."
- **Groove-grammar for djent/slam chugging**: named rhythmic cells (e.g., "3-3-2
  sixteenth grouping," "gallop," "stutter-chug") that can be sequenced and varied,
  replacing the flat per-eighth-note coin flip.
- **Call-and-response between guitar and drums/lead** — currently each instrument is
  generated in near isolation (bass/drums derive from guitar, but guitar never reacts
  to them).
- **Real lead composition**: current "lead" is literally the rhythm riff transposed up
  an octave. Needs actual phrase-based melodic writing — target-note (chord-tone)
  landing on strong beats, passing/neighbor tones elsewhere, occasional wide
  sweep-style interval leaps for technicality.
- **Slam-specific devices**: pinch-harmonic accent simulation, low open-string chromatic
  "creep," sudden half-time drops.

## 5. Song-structure layer — gaps to close

Current: `generate_main.py` is a hardcoded linear call sequence — same shape every song,
only *contents* of each section vary.

Add:
- **Structure as data**: represent song shape as a sequence/graph of section types with
  weights and constraints, so different runs can produce different arrangements
  (e.g., allow interludes, false endings, double breakdowns, intro reprises).
- **Style presets** (data bundles, à la djent's Tesseract/Sworn-In/Thall presets):
  `slam`, `tech-deathcore`, `progressive`, `classic-metalcore` — each preset sets scale
  palette, tuning range, meter complexity, motif-development aggressiveness, blast-beat
  frequency, synth/atmosphere usage, etc. This is the direct, most valuable idea to
  port from djent.
- **Tech/atmospheric interlude section type** — quiet or ambient/synth-led bridge,
  not present at all currently.

## 6. New instrument layer

- **Synth/keys track**: pads, arpeggios, orchestral hits — genuinely absent today
  (current "ambient" is just a quiet guitar layer). This is close to mandatory for
  Born of Osiris atmosphere.
- Possibly a second rhythm guitar track for harmony/unison doubling on leads.

## 7. Open questions to resolve before coding starts — STATUS

1. **Tuning representation** → **RESOLVED (§9.8): explicit fretboard model.** Represent
   guitar as `(num_strings, tuning: list[open_string_pitch], fret_range)`. A "note" is
   chosen as `(string_index, fret)` and resolved to a MIDI pitch via
   `tuning[string_index] + fret`. This naturally supports drop tunings, 7/8-string
   ranges, and constrains riffs to physically playable shapes. Bass derives from the
   same fretboard concept, one or two strings lower register.
2. **Config format** → decide now: **JSON for presets** (style bundles, à la djent),
   **Python dataclasses for the engine's internal types** (rhythm cells, fretboard,
   scale objects). Presets-as-JSON makes them easy to author/diff/share without
   touching code; the engine reads JSON into dataclasses at load time.
3. **Motif representation** → decide now: a motif is `{rhythm_cell, pitch_contour}`
   where `rhythm_cell` is the output of the rhythm layer (§8.1, a list of
   `{duration, is_rest}`) and `pitch_contour` is a list of **scale-degree deltas**
   (not absolute pitches) aligned to the non-rest hits — e.g. `[0, 0, +2, -1]` meaning
   "root, root, up a step, down a step" relative to whatever fretboard
   position/key-center is active when the motif gets applied. This is what makes
   transposition/development possible: apply the same contour against a different
   root/fretboard position/scale and it's a variation, not a copy.
4. **Time-signature scope** → **RESOLVED (§8.2): superseded.** We don't need a curated
   n/d meter list — the cell-length-vs-total-length tiling mechanism produces
   polymeter/odd-cycle effects directly. We'll still track a nominal time signature
   per section for drum-fill/accent logic and DAW-friendliness, but it's bookkeeping,
   not the generative mechanism.
5. **Priority order** → see updated build order below (§8 addendum), now sequenced
   around the rhythm engine as the earliest foundational piece.
6. **(from §9) Rhythm engine adoption** → **RESOLVED: port djent's two-layer model.**
7. **(from §9) Fretboard modeling** → **RESOLVED: adopt.** (same as §7.1 above)

**Remaining open item before coding:** none blocking — §2 (config format) and §3
(motif representation) above are now decided as defaults. Flag here if either should
be reconsidered; otherwise these are locked for v1.



---

## 8. Concrete techniques mined from `djent-master` (full source reviewed)

Source: RossMcMillan92/djent (React/Redux/Web Audio, JS). Full `src/` read directly.
`DjentSync` (a separate, unrelated small PHP/JS repo) was also reviewed and found to
have no reusable compositional technique — it's a non-functional live-jam demo using
deprecated Web Audio calls and amplitude-threshold triggering, not real pitch/meter
detection. Not incorporated further.

### 8.1 Two-layer generation model (adopt this as our core riff-engine architecture)

- **Rhythm layer**: `generateSequence({totalBeats, allowedLengths, hitChance})` —
  recursively picks random note-lengths from a weighted pool until they sum to exactly
  `totalBeats`, correcting the final note to land exactly on the boundary. Each hit
  independently rolls `hitChance` to decide rest-vs-note. `allowedLengths` supports
  triplet/dotted multipliers. This subsumes and generalizes metalerator's
  `randomize_duration()`.
- **Timbre/pitch layer**: applied *after* rhythm is fixed — for each active hit, choose
  from a weighted pool of pitch/articulation choices, but hold the same choice for a
  configurable number of beats (`repeatHitTypeForXBeat`, "each sample will repeat for
  X beats") before rerolling. This is a cleaner replacement for metalerator's ad hoc
  "no more than 2 consecutive high notes" rule — one tunable knob instead of a
  hardcoded constraint.
- **Port plan**: implement as `generate_rhythm(total_beats, allowed_lengths, hit_chance)
  -> list[{duration, is_rest}]` and `generate_pitch_layer(rhythm, weighted_choices,
  stickiness_beats) -> list[pitch]`, fully decoupled functions, usable by every
  instrument (guitar, lead, synth) against different pitch pools.

### 8.2 Polymeter via independent cell length + tiling (the Meshuggah/Born-of-Osiris device)

- A song section has a `total_beats` length. Any instrument can generate a **shorter
  rhythmic cell** (e.g. 7 beats, or 6 beats, or 7.5 beats) via the rhythm layer, then
  tile/loop that cell to fill `total_beats`, truncating the final repeat to fit exactly
  (`loopSequence`). Because the cell length doesn't evenly divide the total, the
  riff's accent pattern drifts against the underlying pulse and drums each repeat —
  mechanically simple, high compositional payoff.
- Confirmed in real presets: `meshuggah` (7-beat guitar cell over 16-beat total),
  `thall` (7.5-beat cell), `polyrhythms` (6-beat guitar cell **and** an independent
  dotted-quarter cymbal cell running at the same time — two different odd cycles
  simultaneously).
- **Port plan**: this becomes our primary mechanism for polymeter (§3), replacing the
  "curated time-signature list" idea with something more powerful — we don't need
  exotic time-signature math, just cell-length-vs-total-length mismatch.

### 8.3 Shared-sequence caching (guitar/kick unison without post-hoc derivation)

- Multiple instruments can reference the same generated-sequence ID; the first
  instrument to resolve it generates and caches the rhythm, later instruments reuse
  the identical rhythm with their own pitch/timbre layer applied on top.
- This is a better solve than metalerator's current approach (`create_kick_pattern`
  scans finished guitar notes after the fact to derive kick hits). Generate the shared
  rhythm once, then let guitar and kick each apply their own pitch/timbre layer to the
  same rhythm skeleton.

### 8.4 Fret/tuning-accurate pitch modeling (worth adopting for realism)

- Their guitar model tunes to Drop G# and defines every playable sound as a literal
  (string, fret) position mapped to real notes, e.g.:
  - `sixth-N-muted` → palm-muted power chord voiced [root, root+7, root+12]
  - `sixth-N-open` → single low note (root only)
  - `sixth-N-chord` → full ringing chord, 5-6 notes across ~3 octaves
  - `third-N-bend` → string-bend articulation
  - `dissonance-10` / `dissonance-16` → deliberately dissonant chromatic-clash dyads,
    used sparingly as a color/tension device (seen in `sworn-in`, `thall-triplets`)
- **Port plan**: consider modeling our fretboard explicitly (string count + tuning +
  fret range) rather than free MIDI-integer scale degrees. This (a) naturally limits
  riffs to physically playable shapes, which sounds more idiomatic, and (b) gives us a
  clean slot for a "dissonance library" of pre-defined clash intervals to sprinkle in
  for Infant-Annihilator-style tension, rather than randomly rolling any chromatic
  interval.

### 8.5 Preset vocabulary observed (useful reference points, not to copy verbatim)

| Preset | BPM | Notable device |
|---|---|---|
| meshuggah | 90 | 7-beat cell / 16-beat total polymeter, dotted-note bias |
| thall | 87 | 7.5-beat cell, bend/scratch/dissonance textures, drone layer |
| thall-triplets | 104 | 12-beat triplet-only cell |
| sworn-in | 90 | cell matches total exactly, hitChance 0.9, dissonance color note |
| polyrhythms | 112 | two independent cell lengths running simultaneously |
| black-dahlia | 212 | fast tremolo-picked runs, `repeatHitTypeForXBeat: 2` |
| contortionist | 90 | 8-bar guitar + independent 6-beat lead polymeter cell + independent hihat/crash cells (true multi-layer independence) |
| doom | — | near-zero rhythmic variety, mostly whole notes, heavy rests |

Confirms our planned "preset = data bundle" approach (§5) — every one of these is the
same generic engine with different config, nothing genre-specific hardcoded.

### 8.6 MIDI export robustness patterns worth keeping

- Simultaneous same-timestamp notes across instruments get merged into a single chord
  event rather than emitted as separate overlapping notes.
- If an articulation's natural duration is shorter than its rhythmic slot, the
  remainder is treated as a rest rather than stretching the note unnaturally (a
  "sharp duration" correction) — worth replicating for palm-mute/staccato hits.

---

## 10. Application / Editor layer (new — from UI references)

The project now has two distinct layers that need separate design:

- **Generation engine** (§1-9): produces musical content given parameters/presets.
- **Editor application**: a UI for composing a song out of sections, tuning each
  section's parameters, regenerating/locking pieces, reordering/resizing with
  automatic blending, and live playback with a visualizer.

Two reference UIs were reviewed (user-provided screenshots):

### 10.1 Reference A — user's new timeline design
Song = ordered list of named section blocks (Intro/Pre-verse/Verse/Bridge/Breakdown/
Outro etc.), each expandable into its own parameter panel: bars count, time signature
(beats + note length), grid resolution, scale, root note, a **riff generation style**
selector, a **riff generation flavor** selector, and per-instrument enable checkboxes
(Drums/Bass/Overdrive guitar/Clean guitar/Synth). Per-block actions: mute, solo,
duplicate, regenerate, edit, delete. Insert-new-section control between any two blocks.
This is the preferred overall layout/IA going forward.

### 10.2 Reference B — user's earlier project ("Forge")
Per-section refinement panel with primitives worth adopting directly:
- **"New notes, same hits" / "Same notes, new hits"** — regenerate only the pitch
  layer or only the rhythm layer, independently. This is exactly the two-layer
  rhythm/pitch model already adopted from djent (§8.1) — strong independent
  validation that this architecture is right.
- **"Too busy" / "Too thin"** — density nudge (maps to `hitChance`/note-length-weight
  adjustment in the rhythm layer).
- **"More djent"** — a style-intensity nudge rather than a binary toggle; implies
  presets need continuous "amount of X" parameters, not just on/off style selection.
- **"Make breakdown"** — one-click section-type conversion.
- **Intensity / Hits / Open / Variation sliders** — continuous knobs exposed directly
  over generation parameters.
- **Keep this pocket / Try again / Undo** — accept-or-reroll workflow per section,
  with history.
- **Guitar tab grid (VexFlow), per-channel (Guitar L / Guitar R)** — editable notation
  view, not just a piano-roll.
- **Save slot / Load slot** — section-level named presets, distinct from song-level
  style presets (§5).
- Global waveform + playhead scrubber for full-song playback.

### 10.3 New engine requirement surfaced by the UI: cross-section blending

Dragging, resizing, or regenerating a section must not produce an abrupt seam. This
means every section needs a defined **entry state** and **exit state** — active
key/tonal-center, active motif, tempo, rhythmic density — that downstream/upstream
neighbors can read. Practically:
- Regenerating or moving a section triggers regeneration of **transition bars** (tail
  of the preceding section and/or head of the following section) so they resolve
  into whatever the neighbor now expects, rather than splicing raw blocks.
- This rides on top of the motif system (§4/§9.3): matching an incoming section's
  opening contour to the outgoing section's closing contour becomes a real
  constraint the engine must satisfy, not just a cosmetic nicety.

### 10.4 Editor feature list (consolidated)

- Section timeline: add/remove/reorder (drag-drop)/resize/duplicate/mute/solo
- Per-section parameter panel (bars, meter, scale, root, style/flavor, instrument
  toggles) per Reference A
- Per-section regeneration primitives (rhythm-only / pitch-only / full reroll /
  density nudge / style-intensity nudge / section-type conversion) per Reference B
- Accept/reroll/undo workflow with section-level history
- Section-level save/load presets (distinct from song-level style presets)
- Cross-section blending on any structural edit (§10.3)
- Live playback with a scrubber, and a visualizer
- Notation/tab grid view, editable per instrument/channel

### 10.5 Architecture fork: where does generation run? — RESOLVED (revised)

Original write-up here weighed a hosted-web-app scenario (network round-trip lag →
favored porting the engine to TypeScript). **User has since clarified this runs
locally only** (their own machine, RTX 5080), in their own repo:
`z2wgv7dc4h-alt/123`. This changes the recommendation:

**Decision: Option A, revised — Python backend, local-only.** Keep the generation
engine (§1-9) in Python, run it as a local service (FastAPI or similar) alongside a
local frontend (React, likely via Electron/Tauri or just a local dev server + browser
tab). Localhost round-trip latency is negligible (sub-millisecond to a few ms), so the
responsiveness concern that motivated a TS port mostly disappears. This avoids
maintaining the hard music-theory/generation logic in two languages — single Python
codebase for everything in §1-9, editor/UI in TS/React on top, talking over localhost.

**New open question this raises:** the user has an RTX 5080 available locally — worth
clarifying whether that GPU is purely to make the app run snappily (in which case it's
irrelevant to our architecture; a modern GPU is massive overkill for this generation
engine's compute needs, which are trivial), or whether there's an intent to use it for
something GPU-bound — e.g. actual audio synthesis/rendering (neural amp modeling,
sample-convolution reverb, a local audio model) rather than just MIDI export. If the
latter, that's a substantial new scope item (an audio-rendering layer, not just MIDI/
notation) and worth flagging explicitly before building.

**Repo target confirmed:** `z2wgv7dc4h-alt/123` (user's own new repo). No GitHub
integration is active in this session yet — when we're ready to start committing
code, we'll need either a GitHub connector/tool enabled here, or to do the actual repo
work from Claude Code/terminal where the user has git configured locally.

## 11. Audio rendering & production pipeline (new — full synthesis via Reaper)

Scope has expanded from "MIDI export" to a full studio-quality render pipeline:
composition engine → MIDI → DAW project assembly → instrument/amp/drum plugin loading
→ mixing → mastering → rendered audio. This is a genuinely new layer, separate from
both the generation engine (§1-9) and the editor UI (§10).

### 11.1 Why Reaper, and what "driving" it means

Reaper is scriptable via **ReaScript** (Lua/Python/EEL), and since our engine is
already Python-first (per §10.5), the natural bridge is **`reapy`** — a Python
package that controls a *running* Reaper instance directly (tracks, items, FX,
routing, rendering) rather than us hand-writing `.rpp` project files as text. This
keeps the whole pipeline in one language and one process model: our backend both
composes the song and drives Reaper to realize it.

Two viable approaches, to decide before building:
- **`reapy` (control a live Reaper instance)** — more flexible, can inspect/adjust
  live, but requires Reaper running with the `reapy` bridge extension installed.
- **Direct `.rpp` file generation** — simpler dependency-wise (no live bridge needed),
  but more brittle (hand-maintaining Reaper's project file format) and no live
  feedback/inspection.

### 11.2 The two-tier playback model this forces

"Live playback" (§10.4) and "studio-quality full synthesis" are **not the same
pipeline** and shouldn't be conflated:
- **Tier 1 — fast interactive preview**: what plays when you drag a section, hit
  "try again," or scrub the timeline. Needs to be near-instant. Likely a lightweight
  in-app synth (soundfont-based or a simple sample player), not a full Reaper bounce.
- **Tier 2 — full studio render**: an explicit "render"/"bounce" action that hands the
  current song off to Reaper: loads the real amp-sim/drum/synth plugin chain, applies
  mixing and mastering, and renders to final audio. This is expected to take real
  time (seconds to minutes) and is not part of the interactive edit loop.

This split needs to be explicit in the editor UI (§10) — e.g. a distinct "Render"
button/panel, separate from instant per-section playback.

### 11.3 Plugin chain — needs the user's actual toolset to proceed concretely

"Studio quality cutting-edge metal" implies a real signal chain per instrument:
- **Guitar/bass tone**: most likely **NAM (Neural Amp Modeler)** + cabinet IR, given
  the GPU is now confirmed to matter — NAM is the standard GPU-accelerated
  neural-amp-sim tool for exactly this use case (real amp/pedal captures, no physical
  hardware). Alternative: a commercial modeler (Neural DSP Archetype series, etc).
- **Drums**: metalerator's existing MIDI note mapping already targets Superior
  Drummer 3 conventions (§1, kept as-is) — worth confirming this is still the target,
  or whether a different drum plugin/library is preferred.
- **Synth/atmosphere** (§6): needs a target VST too, not yet decided.
- **Mix/master chain**: EQ, compression, reverb, sidechain, and a master bus limiter
  need either scripted FX-chain assembly (ReaScript can insert stock/VST FX and set
  parameters) or a set of saved Reaper track templates we drop instruments into.

This is a concrete open item — see questions below.

### 11.4 Open questions — RESOLVED

1. **Reaper automation approach**: `reapy` (control a running Reaper instance).
2. **Guitar/bass tone chain**: user asked for a recommendation. Proposed concrete
   chain, chosen for being free/open-source throughout (consistent with the drum
   decision below) and for actually using the GPU:
   - **NAM (Neural Amp Modeler)** — free, open-source, GPU-accelerated amp/pedal
     modeling plugin. Free high-gain metal captures (5150III, Mesa Rectifier-style,
     ENGL, Diezel-style, etc.) are available from the community capture-sharing site
     ToneHunt.
   - **NadIR** (Ignite Amps, free) or **Convology XT** (Impact Soundworks, free) as
     the cabinet IR loader, paired with a free metal-oriented IR pack.
   - Reaper's own **stock FX** (ReaEQ, ReaComp, ReaGate, ReaXcomp, ReaLimit) for
     tightening/gating the high-gain signal and for the mix/master bus — these are
     bundled with Reaper (no extra cost) and, importantly, the most reliably
     ReaScript/`reapy`-automatable FX available, since third-party VST parameter
     automation is far less standardized (see engineering note below).
   - **Bass**: either a NAM bass-amp capture, or a common modern-metal technique —
     blend a clean DI layer (for low-end weight/clarity) with a NAM-driven distorted
     layer in parallel, then glue with ReaComp/ReaEQ.
3. **Drum plugin/library**: **CONFIRMED (superseding the earlier tentative pick) —
   user has supplied an actual kit.** See §11.7.



### 11.5 Engineering note: FX-chain presets, not live parameter automation

NAM isn't a heavily-parameterized plugin in the traditional automatable sense — its
main "control" is *which captured model file is loaded*, not a set of knobs. The
robust approach is therefore **not** to script NAM's internals live via `reapy`, but
to:
1. Pre-build a small library of **saved Reaper FX-chain presets** (`.RfxChain` files),
   each representing a complete tone (e.g. `rhythm_high_gain.RfxChain`,
   `lead_tone.RfxChain`, `bass_di_blend.RfxChain`) — built once, by hand, in Reaper,
   with NAM already pointed at a specific capture + cab IR + EQ/comp already dialed in.
2. Have our automation layer simply **apply the appropriate saved FX chain to each
   track** via `reapy`, rather than trying to configure NAM's model selection or
   internal state programmatically.

This is both more reliable (avoids fighting inconsistent third-party plugin
parameter APIs) and matches how a human engineer would actually work in Reaper.

### 11.6 New concrete task: drum note-mapping translation layer

The existing MIDI note choices in metalerator's drum code (§1) target Superior
Drummer 3's mapping conventions (e.g. 36=kick, 38=snare, 41/43/45/47/48=toms,
51/53=ride, 52=china, 55=splash, etc). Whatever drum plugin we land on in §11.4 will
likely expect a different note map. We need a small, explicit translation layer:
`internal_drum_note -> target_plugin_note`, configured per drum plugin, so the
generation engine's drum vocabulary (§3) stays plugin-agnostic and we only maintain
one mapping table per supported plugin. **Superseded by §11.7 below now that a real
kit is confirmed** — the translation needs to be role-based, not a flat note-to-note
table, for reasons detailed there.

### 11.7 Drum kit confirmed — user-supplied SFZ multisample library

User provided a real, hand-tuned, 5-velocity-layer multisampled acoustic kit in
**SFZ format** (free, open, text-based instrument format). Contents:
- Two drum brands: **"Black Pearl"** (Pearl-shelled kit) and **"Red Zeppelin"**
  (Ludwig-shelled kit — the name is a pun, not a licensing concern, it's the drum
  brand not the band), each in 4-piece and 5-piece configs (5pc adds a second, larger
  floor tom rather than just re-triggering the 4pc's edge sample).
- Cymbals: Sabian AAX/AA and Zildjian A/K models depending on kit, plus a shared
  Paiste 2002 crash, Zildjian A splash, and rototoms/cowbell/tambourine/maraca for
  texture.
- Round-robin-free but velocity-layered (5 layers per articulation via `lovel`/`hivel`
  ranges), with proper choke groups (`off_by`/`offby` opcodes correctly silence a
  ringing crash/ride when its choke articulation fires) — a well-built, usable kit,
  not a rough freebie.

**Player recommendation**: **sfizz** — a free, actively-maintained, fully open-source
(BSD-licensed) real-time SFZ engine available as a VST3/CLAP plugin, matching the
free/open-source posture of the rest of the chain (§11.4) and loadable/automatable
from Reaper via `reapy` like any other plugin. (Sforzando, from Plogue, is a
free-but-closed-source fallback if sfizz has any loading quirks with this file's
opcodes — worth keeping in mind but not the primary target.)

**This kit's actual note map** (confirmed from reading all four `.sfz` files):

| Note | Role | Note | Role |
|---|---|---|---|
| 36 | Kick | 53 | Ride bell |
| 37 | Side stick | 54 | Tambourine |
| 38 | Snare | 55 | Splash |
| 39 | Hand clap | 56 | Cowbell |
| 40 | Snare (edge/rimshot layer) | 57 | Crash 2 |
| 41 | Floor tom | 58 | Crash 2 choke |
| 42 | Hi-hat closed | 59 | Ride shank |
| 43 | Floor tom (2nd, 5pc only) / edge (4pc) | 60 | Crash 3 (Paiste) |
| 44 | Hi-hat pedal | 61 | Rototom hi |
| 45 | Rack tom | 62 | Rototom mid |
| 46 | Hi-hat semi-open | 63 | Rototom lo |
| 47 | Rack tom 2 | 64 | Maraca |
| 48 | Hi-hat swish/open | | |
| 49 | Crash 1 | 50 | Crash 1 choke |
| 51 | Ride | 52 | Ride choke |

**Conflict this surfaces with the existing (metalerator/SD3-oriented) drum code**:
the old internal vocabulary (§1) assumed note 48 was an extra tom (used in
`allowed_drums_for_fills`), notes 57/60 meant "open hat," note 63 meant "closed hat,"
and notes 27–31/52 meant "china cymbal." **None of that holds for this kit** — 48 is
a hi-hat articulation here, 57/60 are crashes, 63 is a rototom, and there is no china
cymbal sample in this kit at all.

**Resolution — redesign the internal drum vocabulary as semantic roles, not raw MIDI
numbers.** The generation engine (§3/§8) should reference drums by role
(`KICK`, `SNARE`, `SNARE_RIMSHOT`, `HIHAT_CLOSED`, `HIHAT_PEDAL`, `HIHAT_SEMI_OPEN`,
`HIHAT_OPEN`, `TOM_HIGH`, `TOM_MID`, `TOM_LOW`, `CRASH_1`, `CRASH_1_CHOKE`,
`CRASH_2`, `CRASH_2_CHOKE`, `RIDE`, `RIDE_BELL`, `RIDE_CHOKE`, `RIDE_SHANK`,
`SPLASH`, `CHINA`, `COWBELL`, `TAMBOURINE`, `HANDCLAP`, `ROTOTOM_HI/MID/LO`,
`MARACA`), and a **per-kit mapping table** (like the one above) translates each role
to that kit's actual MIDI note. This is what makes the engine kit-agnostic going
forward, and it cleanly handles the gaps:
- **No `CHINA` sample in this kit** → mapping config marks `CHINA` as unavailable for
  this kit and falls back to a configured substitute (recommend `CRASH_2`) rather
  than silently emitting a wrong note.
- **Old note-48 "fill tom" usage** → remapped to `TOM_HIGH`/`TOM_MID`/`TOM_LOW`
  (roles), which resolve correctly to 41/43/45/47 for this kit instead of colliding
  with its hi-hat note.

## 12. Chord/tab tooling review (Anvil, react-chords) — and a required new module

Two more references reviewed (full source). Neither contributes generation logic;
together they clarify a gap that needs an explicit module.

### 12.1 Anvil (client-side Web Audio metal generator)
Architecturally convergent with what we've already scoped (timeline, presets, seeded
PRNG, interval-table scales) but musically simpler than metalerator — confirms
direction, contributes nothing new to generation. **One reusable technique**: its
WAV export — build the signal graph in an `OfflineAudioContext`, `startRendering()`,
hand-encode 16-bit PCM WAV via `DataView` (no library) — is a clean, dependency-free
pattern worth adapting for the **Tier-1 fast preview** path (§10.2), independent of
the Reaper render pipeline (§11).

### 12.2 react-chords (SVG chord-diagram renderer)
Pure presentation layer — draws a diagram from an already-known shape
`{frets, fingers, barres, capo}`; the real-world usage pulls shapes from an external
static database (`chords-db`), not from music theory. Only reusable logic is the
open-string-plus-fret MIDI formula, which just re-confirms our existing fretboard
model (§7.1/§9.1). Useful as a **rendering reference** for a static chord-diagram
component in the editor (complementary to, not a replacement for, sequential tab
notation — see 12.3), but explicitly **not** to be used as a chord-shape source: a
static lookup table is the opposite of "ground up, entrenched in music theory, no
note that doesn't exist."

### 12.3 New required module: chord-shape solver (ground-up, no lookup tables)

Nothing reviewed so far (metalerator, djent, Anvil, react-chords) actually *derives*
a chord voicing from theory — they all either hardcode intervals against a root, or
render a pre-known shape. Given the explicit requirement — every note must be
derivable from music theory and physically valid on the defined fretboard, not pulled
from a static chord database — this needs to be built as its own module:

- **Input**: a chord specification (root + quality/interval set, e.g. power chord =
  root+5th+octave, or any richer chord for clean/lead sections) plus the active
  fretboard model (§7.1: string count, tuning, fret range).
- **Process**: algorithmically enumerate valid fingerings — for each string, find
  fret(s) that produce a required chord tone within the fret range; reject shapes
  that exceed a realistic fret-span (hand-stretch constraint), that require muting
  patterns inconsistent with the voicing, or that duplicate/omit required tones
  incorrectly. No note is placed unless it's both (a) a theoretically correct chord
  tone and (b) reachable at a valid `(string, fret)` position on the defined tuning.
- **Output**: one or more valid `(string, fret)` fingerings per chord, usable both for
  audio generation (§4, feeds the pitch layer) and for rendering (§12.4).
- This directly serves the guitar-idiomatic-riff goal already noted in §8.4/§9.1, and
  is the actual mechanism behind "no note that doesn't exist" — it's an engine
  requirement, not a UI concern.

### 12.4 Notation/tab rendering — target VexFlow, not react-chords

The user's earlier project (Forge, §10.2) already used **VexFlow** for its tab grid,
and VexFlow is the standard open-source library for sequential music/tab notation
rendering (staff notation *and* tab notation, unlike react-chords which only draws
static chord-box diagrams). Recommendation: VexFlow is the tab/notation rendering
target for the editor (§10.4); react-chords-style static chord diagrams can optionally
supplement it (e.g. a "chord reference" panel) but aren't the primary export/view
mechanism.

---

## 9. Updated open questions (supersedes/adds to §7)

7. **Rhythm engine adoption**: port the djent two-layer model (§8.1) as literally as
   reasonable in Python, or treat it only as a design reference and keep more of
   metalerator's existing per-instrument procedural code? (Recommendation: port it —
   it's simpler and strictly more capable than what exists now.)
8. **Fretboard modeling (§8.4)**: **RESOLVED: adopt.** Also updates §7.1 above.

## 14. Gap analysis & research findings (dependency verification + missing scope)

### 14.1 Research corrections to earlier decisions

- **`reapy` is unmaintained** — the original `RomeoDespres/reapy` package has had no
  meaningful updates in years; the maintainer has moved on. There are active
  community forks: **`reapy-boost`** (Levitanus) is the most actively developed,
  adds bug fixes and extra functionality (including a ReaImGui wrapper). **Decision:
  target `reapy-boost`, not plain `reapy`**, for §11.1.
- **NAM capture licensing nuance** — NAM itself (architecture/training/inference) is
  MIT-licensed, fully free for commercial use, confirmed. However, **individual
  community-shared captures are not automatically licensed the same way** — many
  capture authors explicitly restrict redistributing the raw `.nam` capture file
  itself (not the music made with it). Using a capture as an instrument to make and
  release music is the intended, standard use and is not restricted by any capture
  author's terms I found; **redistributing/bundling the raw capture files** with our
  product would need per-capture license checking. Not a blocker, just a due-diligence
  item before shipping anything that bundles specific `.nam` files.
- **Synth/atmosphere plugin (§6/§11.3, previously undecided)**: recommend **Surge XT**
  — fully open-source (GPL), actively maintained, covers subtractive/FM/wavetable
  synthesis in one plugin, matching the free/open-source posture of the rest of the
  chain. **Vital** is a strong alternative if pure open-source isn't a hard
  requirement (more polished for modern pads/leads, but freemium/closed-source).
  Also worth adding **Valhalla Supermassive** (free, closed-source but zero-cost) as
  a send-effect for atmospheric reverb/delay textures on the ambient layer.
- **Notation/tab rendering (§12.4) — license-checked**: VexFlow is MIT-licensed
  (fully free, no commercial restriction) — confirmed, no change to that decision.
  Worth noting **alphaTab** (MPL-2.0, also free for commercial use) as a serious
  alternative — it's more guitar-tab-idiom-specific out of the box (bends, slides,
  palm-mute markings, Guitar Pro import/export) than VexFlow's more general
  notation-first design. Not switching the decision, but worth a side-by-side
  evaluation once we're actually building the notation layer.

### 14.2 Scope gaps — need decisions

1. **Vocals** — **RESOLVED: out of scope.** Instrumental-only tool. No vocal rhythm/
   phrasing track, no lyric generation, in v1 or planned phases. Revisit only if
   priorities change explicitly later.
2. **Bass needs its own fretboard model** — currently bass is treated as "derived
   from guitar" (metalerator's old approach). Now that we've committed to ground-up
   fretboard modeling (§7.1/§12.3), bass needs its own explicit model — string count
   (4 or 5), tuning, range — distinct from the guitar model, not just a transposed
   copy of guitar's fretboard.
3. **Lead/solo generation algorithm** — flagged as a gap back in §4 and never
   actually designed. Still a stub: needs a real phrase-based approach (target
   chord-tones on strong beats, passing/neighbor tones elsewhere, occasional wide
   interval leaps for technicality) rather than "transpose the rhythm riff."
4. **Mid-section tempo/feel changes** — the structure engine (§5) currently only
   varies tempo/feel *between* sections. Infant-Annihilator-style slam relies heavily
   on sudden half-time drops *within* a section (a riff that's blasting, then
   half-times for 2 bars as a "slam" moment). Worth adding as an explicit
   phrase-level device, not just a section-level one.
5. **Key/tonal-center modulation mechanics** — flagged as needed in §2, still not
   concretely designed (when does a modulation happen, by what interval, how does it
   resolve back).
6. **Humanization/performance-realism layer** — currently just narrow velocity
   jitter (inherited from metalerator). Real "studio quality" wants micro-timing
   (not perfectly quantized), and a dynamic arc across a song (verse quieter,
   chorus/breakdown hits harder) — not yet designed.
7. **Mixing intelligence** — **RESOLVED: adaptive mixing wanted from the start**,
   not just static FX-chain presets. This adds real scope on top of §11.5: the mix
   layer needs to make context-aware decisions — e.g. auto-duck bass under kick hits,
   auto-EQ-carve rhythm guitar vs. bass to avoid low-mid buildup, dynamic
   riding of levels across sections (verse/chorus/breakdown), not just "apply this
   saved chain to this track." Concretely this likely means: the pre-built FX-chain
   presets (§11.5) still provide the *tone*, but a new automation layer scripts
   *dynamic* parameter changes (compressor sidechain routing, EQ automation points,
   bus levels) via `reapy`/`reapy-boost` on top of them, driven by the same
   arrangement data the generation engine already has (which section is playing,
   what's rhythmically active in each instrument at each point). This is a
   substantial new module, not a small addition — worth its own design pass when we
   get to the render pipeline.
8. **Theory validator / automated test harness** — given "no note that doesn't
   exist" is a hard requirement, we should have actual automated tests verifying it
   (scale-membership checks, fretboard-reachability checks, rhythm-sums-to-total
   checks) rather than relying on code review alone. Not yet scoped as a concrete
   module.
9. **Evaluation/QA methodology** — no defined way to judge "is this actually god
   tier" beyond ear-checking. Worth a lightweight rubric or reference-comparison
   process once there's output to judge.
10. **Project file format** — the actual save-state schema for a whole song
    (sections, parameters, generated note data, render settings) hasn't been
    specified. Needed before the editor (§10) can persist anything.
11. **Export matrix** — should be enumerated explicitly: MIDI stems, full mix audio,
    individual stems, tab/notation PDF (now confirmed feasible via VexFlow/alphaTab
    running in Node, not just browser), and a Reaper project file for manual
    tweaking. Not yet listed as a concrete deliverable set.
12. **Reference-corpus analysis** — should we structurally analyze (not reproduce)
    real Infant Annihilator / Born of Osiris songs to sanity-check that our engine's
    output is stylistically plausible (tempo ranges, phrase lengths, groove density),
    as a research/calibration step distinct from the generation engine itself?
    Copyright-safe as long as it stays at the pattern-analysis level and never
    reproduces actual riffs/recordings.
13. **ML/GPU stretch track** — **RESOLVED: yes, flagged as a real phase-2+
    direction**, not just NAM. No specific model/technique chosen yet — this is a
    placeholder for later (candidates worth considering when we get there: a learned
    humanization/groove model trained on real drum/guitar performance data, or a
    style-conditioning model for riff generation). Explicitly deferred — not part of
    the v1 build order (§13), revisit once the core engine and editor are working.

---

## 18. Full review of prior attempt (Ww/Forge repo) — the single richest source reviewed

This is not a reference library like the others — it's the user's own earlier,
substantial, Grok-assisted attempt at this exact project (product name "Forge"),
including a working engine, a test suite, and — critically — a written
knowledge-transfer document (`docs/KNOWLEDGE.txt`) documenting real dead ends,
settled decisions, and unresolved gaps. Full source read directly for the core
theory/preset/tab modules (`theory.py`, `style_packs.py`, `tab_score.py`'s
`pitch_to_fret`, `keys_gen.py`); infrastructure modules (server/API/install
scripts) understood via the project's own comprehensive `KNOWLEDGE.txt`
handoff doc, which was explicitly written to be a complete summary of
everything not in the code itself.

### 18.1 The single most important strategic finding — validates the whole approach

They tried using a general text-to-audio generative model (ACE-Step, run via a
tool called "HOT-Step") to directly render finished audio from a prompt, extensively,
across many iterations. Documented outcome, in their own words: *"First gens =
electronic. Then 'grunge'/'chill metal vibe'/'not as much chugging'... still not
SOTS Pray for Death 1:58, not huge BoO breakdowns, not bouncy djent with cool
drums."* Their explicit conclusion: **"ACE-Step cannot be the writer. Grid is the
writer. Cover is optional paint after the score exists."** Suno was tried and
rejected the same way earlier. Even a fine-tuned adapter (a Civitai deathcore
DoRA) was judged **"valid as an ADAPTER later, not a substitute for cells."**

This directly validates the foundational premise of this whole project: a
deterministic, theory-driven symbolic engine (the "score"/"cells") has to be the
authoritative source of truth, with any AI-audio-model or generative-cover layer
treated strictly as optional paint applied *after* the score exists — never as a
replacement for it. Their own retrospective states it as a closed question:
*"Do not reopen 'should we be text-to-audio?' That debate is closed."* Worth
carrying forward as an explicit, stated architectural principle for this project
too, not just an implicit assumption.

### 18.2 Concrete algorithms and techniques to adopt directly

- **`pitch_to_fret` (fretboard note-placement algorithm)** — directly answers
  §17.2 (human playability) with working code, not just a design question:
  enumerate all `(string, fret)` positions that reach a pitch within a max fret
  (12); with no previous position, prefer the **lowest string**; with a previous
  position, minimize a cost `abs(fret_diff) + abs(string_diff) * 2` — i.e.
  changing strings costs twice what sliding along one string does. Small,
  elegant, directly portable into our fretboard model (§7.1/§12.3) as the
  default fret-selection heuristic. Doesn't solve speed/tempo playability by
  itself, but makes note-to-note motion physically economical, which is most of
  the problem.
- **IRVD phrase form** (Introduction / Repetition / Variation / Destruction,
  credited to the `rust-beats` generator) — a bar-by-bar development shape for
  a *single section*, distinct from and complementary to our cross-section motif
  system (§4/§9.3): Introduction is always exactly one bar; Destruction takes
  the last quarter of the section; the remainder splits between Repetition and
  Variation. This is a genuinely useful addition — our motif system handles
  development *across* sections, IRVD handles development *within* one. Worth
  adopting both.
- **`VoiceLeader` class** — a mature, working melodic engine that directly fills
  the "real lead composition" gap (§14.2 item 3). Cleanly separates *which* note
  (pitch class, chosen from a weighted interval vocabulary) from *where* it sits
  (octave/register, chosen by proximity to the previously-played note — real
  voice leading, so a line walks instead of teleporting). Four operations:
  `pick` (weighted interval + nearest-register placement), `walk` (pure
  stepwise diatonic motion, reflecting off the register span's edges rather
  than leaving it), `move` (probabilistic blend of the two, controlled by a
  single `motion` parameter — "active styles walk, anchored styles re-pick"),
  and `stab` (a deliberate large interval leap for accents, explicitly exempted
  from the smoothing logic). Worth adopting close to as-is.
- **`shade()` dissonance reweighting** — takes a style's weighted interval
  vocabulary and a single 0–1 "dissonance" dial, and reweights dissonant
  intervals (m2/M2/tritone/M7) up or consonances up accordingly — without ever
  zeroing anything out, so a style never loses its own character, only its
  balance shifts. Directly usable as the mechanism behind a Guided Mode (§15)
  tension/dissonance slider.
- **Cross-section `ARC` table** — a single table giving each section-letter an
  energy, a register offset, a dissonance level, and a starting scale degree,
  with one deliberate architectural rule: **density is not an independent
  parameter, it's derived as `0.28 + 0.62 * energy`**, specifically so that
  "the breakdown hits hardest" and "the comedown is a comedown" can't be edited
  into disagreement with each other by only touching one of several redundant
  knobs. This is a concrete, numeric implementation of exactly the "entry/exit
  state per section" concept from §10.3 — worth adopting the table directly
  and, more importantly, adopting the *principle* (derive related parameters
  from fewer master dials) throughout our own Guided Mode design (§15).
- **Real per-artist tuning table**, exact MIDI open-string values — directly
  usable in our fretboard/tuning model (§7.1):
  `drop_g_7` (Born of Osiris "Discovery" style, G-D-G-C-F-A-D, opens
  31/38/43/48/53/57/62), `drop_ab_7` (Periphery), `drop_a_7` (Signs of the
  Swarm), `drop_b_7` (Veil of Maya default), `drop_c_6`, `standard_6`.
- **Two new scales worth adding to §2's palette**: `cluster`
  (0,1,3,6,7,8,11) — explicitly built as "not a mode anyone plays melodies
  in," a deliberate dissonance vocabulary for tech-style chugging, not a real
  mode; and `power` (0,5,7) — root/4th/5th only, for pure power-chord contexts
  with zero color.
- **Judge/retry loop** — a lightweight, working answer to the theory-validator
  gap (§14.2 item 8): a cheap heuristic quality gate (minimum hit count, a
  palm-mute ratio band, a kick/palm-mute lock ratio) that a generated section
  must pass, with automatic reroll up to 6 seeds if it doesn't. Not a full
  music-theory correctness prover, but a proven, cheap pattern worth adopting
  as a first pass before building anything heavier.
- **`flatten` + `pickup` blending** — a real, working (if simple) answer to
  §10.3's cross-section blending requirement: before concatenating two
  sections, overwrite the last 2 cells of the outgoing section with the first 2
  cells of the incoming one. Cheap and effective for avoiding an abrupt seam;
  our motif-aware blending (§10.3) can be a richer version of this same idea
  rather than a wholly different mechanism.
- **A real song/project JSON schema** — directly seeds §17's still-open
  "project file format" gap: `{bpm, pack, tuning_key, sections: [{letter,
  style, bars, seed, pack, guitar, drums, tuning_key}]}`. A good starting
  skeleton to extend (add bass/lead/synth tracks, motif IDs, per-section
  entry/exit state) rather than design from nothing.
- **Two-state velocity-threshold articulation** — a simpler alternative to
  metalerator's separate palm-mute trigger-note pairs (§1): velocity ≥ 110
  means open/ringing, < 110 means palm-muted, encoded as a single property of
  the note itself rather than an extra note inserted beforehand. Worth
  evaluating as a simpler encoding, at least for engine-internal representation
  even if the final NAM/plugin chain (§11) needs its own trigger convention.
- **Cheap placeholder atmosphere layer** — `keys_gen.py` uses plain General MIDI
  program numbers (Program 90 "Pad 2 (warm)" for pads, Program 56 "Orchestra
  Hit" for stabs) as a placeholder before any real sample library is wired in,
  with concrete starter voicings: pad chord = root/5th/octave (open, ambient),
  stab = root/5th/octave/minor-10th (a small dramatic cluster, not full
  orchestration). Worth using as a fast, zero-dependency first pass for §16
  before investing in the full Spitfire/sfizz orchestral pipeline.
- **Preset naming lesson, already learned the hard way** — they *started* with
  band-named presets (`boo`, `vom`, `sots`, `periphery`, `atb`, `psycho`) and
  deliberately moved away from them to mood/archetype names (`groovy`, `djent`,
  `chill`, `tech`, `slam`, `melodic`), keeping the old band-linked ids as
  `ALIASES` purely for backward compatibility with saved songs. Their own
  stated reason: *"style-mood construction rules. Not band names — tunings,
  pulse, mute math... the mood/style you pick drives density, dissonance, and
  note-choice character."* This **upgrades §17.4** from "plan a descriptive
  fallback in case this goes public" to "adopt mood/archetype naming as the
  primary scheme now" — it's better UX independent of the trademark question,
  and they already proved it out. Reference-band names can still live as
  documentation/aliases the way theirs do.
- **`keys_gen.py`'s own genre research independently confirms §16.1** almost
  verbatim, with citations: Lorna Shore's orchestral hits as a rhythmic
  "co-lead" voice punctuating breakdown downbeats (not full underscore), and
  Born of Osiris treating synth/keys as a genuine compositional voice under
  riffs and interludes (not intro-only ambience), sourced from a guitarist
  interview and Wikipedia — careful to stay at the convention level, never
  citing or transcribing a specific song's actual notes. Good independent
  validation of §16, and a good model of how to research genre convention
  without touching copyrighted specifics.

### 18.3 Documented mistakes — avoid repeating these

- **Fake triplets**: their first attempt approximated triplet feel by
  cherry-picking specific 16th-note grid positions (`{0,2,3,5,6,8,10,11,13,14}`)
  rather than using a true compound/tuplet subdivision. Their own note: *"Do
  NOT map triplets onto 16ths anymore. That was the fake 3+3+2 grid."* Our
  rhythm-layer design (§8.1, adopted from djent) already uses genuine tuplet
  multipliers rather than this shortcut — worth double-checking this holds once
  we actually implement it.
- **Naive "double-tracking"**: their two guitar tracks were the *same*
  performance, one copy simply time-shifted +8 MIDI ticks — not two
  independent takes. They flagged this themselves as unfinished. Directly
  validates §17.1 (double-tracked guitars need genuinely independent
  humanized performances, not a delayed copy) — good confirmation we identified
  a real, previously-hit problem rather than a hypothetical one.
- **Un-split preview audio bus**: their preview WAV rendered guitar and drums
  onto one mixed signal before any amp simulation, meaning an amp sim applied
  to that file would amp the drums too. **New concrete requirement for §11**:
  guitar, bass, and drums need to stay on separate buses all the way through
  to the amp-sim/mixing stage — never pre-mixed before that point.
- **Runaway automatic model downloads**: an early automation queued ~144 large
  model files without the user's explicit per-file consent. General caution
  worth carrying into any future automation we build that fetches models,
  presets, or captures on the user's behalf (relevant if we ever automate NAM
  capture or synth-preset fetching) — never a blanket "download everything,"
  always an explicit, itemized confirmation.
- **NAM capture redistribution**: reconfirms §11.4's finding independently —
  their own note: *"use captures, do not redistribute .nam files."*

### 18.4 Gaps they identified but never built — useful cross-check against our own list

Their own "left out of first handoff, now canonical" section lists unresolved
gaps almost point-for-point matching ours, which is a good independent sanity
check that we're not missing something obvious, and a couple of new angles:

- **No motif system** ("Letters ≠ motifs") — matches §4/§9.3 exactly; they
  never built it either, reinforcing it as genuinely hard and high-priority
  rather than something we're overcomplicating.
- **No bass track at all**, and an explicit note that real target-genre
  arrangements are "2 guitars + bass + kit + keys" — matches our own
  instrumentation plan (§17.1 double-tracked guitar + §14.2 item 2 bass
  fretboard model + drums + §16 synth/orchestra) closely.
- **No true polymeter** ("guitar 3 vs drum 4 — researched, not built") — we're
  ahead here: djent-master's cell-length-vs-total-length tiling (§8.2) is a
  concrete, implementable design they never arrived at; their `djent` preset's
  "group: 3" accent-grouping is explicitly described by them as *"a
  displacement device... an honest step toward polymeter, but not polymeter
  yet"* since it's still one meter with an accent trick, not two independently
  different meters.
- **Reaper intended to run headless, never shown to the user** ("A visible
  DAW" is listed under explicit non-goals; "Hidden Reaper later for stems;
  never show the DAW.") — **this directly informs the still-open §17.5
  question** (does the Reaper tempo-map need to be human-legible for polymeter
  sections). If Reaper is meant to stay headless/hidden in our design too, that
  further supports Option A (single constant tempo, don't bother making
  Reaper's own grid reflect the polymeter structure) — no human is expected to
  open Reaper directly to read it.
- **KEEP-labels as a feedback-learning loop**: an unbuilt idea to feed the
  user's accept/reject judgments on generated takes back into adjusting
  style-pack parameter weights over time. Worth adding as a refinement to our
  own §17.6 preset-calibration workflow — could be semi-automated rather than
  purely manual.
- **Buying commercially-licensed drum MIDI packs (GGD/Toontrack) as legal
  "teacher data"** to mine for drum-pattern vocabulary — a clean, legally
  unambiguous way to expand our drum-pattern library later (buying MIDI
  explicitly licensed for use, then studying its patterns, is categorically
  different from analyzing copyrighted audio recordings).

### 18.5 Real reference tracks and a real evaluation methodology

Their own listening-log practice is a good lightweight model for §14.2 item 9
(evaluation/QA methodology): every generated "take" got a plain keep/reject
judgment, sometimes with a one-line comment (*"this is good it definitely
sounds like a breakdown"*, *"chill, not as much chugging as I thought"*).
Named reference tracks per target sound, useful as concrete benchmarks for our
own preset-calibration workflow (§17.6): Born of Osiris — "The Discovery,"
"Follow the Signs"; Signs of the Swarm — "Pray for Death" breakdown around
1:58 (described as triplet/"psycho"-feel, fast chug — this is their `tech`
preset's direct target); Periphery ("heavy/epic djent"); Veil of Maya; After
the Burial (wanted, never got a finished preset).

### 18.6 A ready-made, legally clean reference-MIDI corpus — answers §14.2 item 12

They already sourced and partly ingested exactly the kind of reference corpus
§14.2 item 12 asked about, and the actual files are sitting in this same
upload: **Whack Studio Breakdown Essentials** (52 free GM breakdown MIDIs, one
per BPM/feel), and **JJDoge's free metal groove packs** (Lakeside Camping,
Lamb Chops, Dreaming In Theaters — large sets of GM-mapped grooves and fills
across multiple BPM ranges and time signatures, including several already in
odd meters like 5/4, 7/8, 9/8, 11/4). A third free source they noted but that
isn't in this upload: a Creative-Commons (CC BY-SA) community metal-MIDI site.
Their own `midi_ingest.py` already does the useful part — parses standard MIDI
files, quantizes to a fixed grid, and separates channel-9 drums from
channel-0 guitar — which is directly reusable groundwork for mining this
corpus as a drum-pattern-vocabulary source (not for copying riffs, since
these are generic groove-pack MIDI with no specific song attached, but for
learning realistic rhythmic vocabulary/density/fill placement).

### 18.7 One loose thread worth asking about

Their old private repo was `z2wgv7dc4h-alt/Ww` — same GitHub account prefix as
the new repo created for this project, `z2wgv7dc4h-alt/123`. Worth checking
whether that old repo still exists and has anything (commit history, later
work not captured in this zip) worth pulling forward, rather than treating
this zip as the only surviving copy.

## 15. Guided Mode — for a taste-literate, not theory-literate, user

Revised target user (superseding the earlier "5-year-old" framing): someone with a
diverse, opinionated ear for metal — they know Lorna Shore from Shadow of Intent from
Born of Osiris by listening, and know what they want more/less of — but no
expectation they know what a Phrygian mode or a 7/8 cell is. The tool needs a mode
that speaks in **taste**, not **parameters**, while Pro Mode (§10, full manual
control) remains fully available underneath for anyone who wants to go deeper.

### 15.1 What Guided Mode actually needs
- **Taste-based inputs, not raw parameters**: pick from named style presets
  (Born of Osiris, Lorna Shore, Shadow of Intent, Infant Annihilator, etc. — §5's
  preset system), then a small number of plain-language dials layered on top —
  energy/heaviness, technicality, atmosphere amount, blast-beat frequency — described
  by effect, not by the theory term underneath. No requirement to touch scale,
  tuning, or time-signature controls directly unless the user opts into Pro Mode.
- **Blend/reference controls**: since taste is often relational ("more like this,
  less like that"), consider letting the user nudge between two presets (e.g. a
  Born-of-Osiris ↔ Infant-Annihilator slider) rather than only picking one discrete
  preset — this maps naturally onto the preset-as-data architecture already adopted
  (§5, §8.5).
- **Full customization stays one click away**: every dial Guided Mode exposes should
  be a friendly wrapper over real underlying parameters the Pro editor (§10) can
  also touch directly — same data model, two levels of exposure, not two separate
  systems.
- The stricter "must never require a human to correct anything" bar from the earlier
  5-year-old framing is relaxed accordingly — good adaptive mixing (§14.2 item 7)
  is still the goal by default, but the product no longer needs to guarantee a
  flawless unattended result for a user with zero context; a taste-literate user can
  reasonably tweak a result they don't love.

### 15.2 Consequence: same preset-by-name requirement as before
This still means the preset library needs to be built out per named target sound
rather than generic dials (unchanged from the prior draft) — that part of the
reasoning holds regardless of exactly how novice the user is assumed to be.

## 16. Atmospheric/orchestral layer expansion (Lorna Shore, Shadow of Intent, Born of Osiris)

The synth/atmosphere layer as scoped in §6/§11.3 (a single synth pad track) is not
enough to reach these specific reference points. Genuine research findings + design
consequences:

### 16.1 What these bands actually add, concretely
- **Lorna Shore / Shadow of Intent**: real symphonic layering — string ostinatos,
  brass stabs/hits synced to breakdown accents, choir pads, cinematic percussion
  (orchestral hits, taiko-style low hits) under/around the metal instrumentation, not
  just a background pad.
- **Born of Osiris**: synth **leads that double or harmonize with the guitar riff**
  in unison or a fixed interval, not just atmospheric texture — the synth is a
  melodic participant in the riff, not a wash behind it.

### 16.2 New instrument tracks required
- **Orchestral bed** (strings/brass/woodwind/percussion) — recommend **Spitfire
  Symphony Orchestra: Discover** (free, 44 instruments/74 techniques, genuinely
  high quality, runs in the free Kontakt Player) for fidelity; **Sonatina Symphonic
  Orchestra / Virtual Playing Orchestra** (SFZ format via `sfizz`, same engine as the
  drum kit, zero extra host dependency, lower fidelity) as the fully-open alternative
  if avoiding the Kontakt Player + Spitfire account dependency matters more than
  fidelity. Defaulting to Spitfire for quality given the explicit "god tier" bar,
  pending pushback.
- **Choir pad** — **Spitfire LABS Choir** (free, genuinely good sampled ensemble,
  sustained-vowel/pad textures only — no word-building, which is fine since this is
  atmosphere, not a vocal line; consistent with vocals being out of scope, §14.2
  item 1 resolved).
- **Synth lead** (already planned, §6/§14.1 → Surge XT) gets a new *behavior*, not
  just a new patch: a mode where it plays in **unison or harmony with the active
  guitar motif** (§4/§9.3) rather than only generating independent pad material —
  this is what makes it sound like Born of Osiris rather than generic atmosphere,
  and it's a natural extension of the motif system already in scope (the synth just
  re-renders the same motif contour against its own patch/octave/harmony interval).

### 16.3 New generation behavior: accent-synced orchestral hits
A recurring device in this reference set is a single orchestral/choir hit landing
exactly on a structural accent (e.g. the first beat of a breakdown). This should be
a first-class event the structure engine (§5/§13) can place — not just "the
orchestra plays continuously" — tied to the same section/accent data the drums and
guitar already use for their own accents.

## 17. Further gaps (round 2)

### 17.1 Double-tracked rhythm guitars — production realism gap
Every "studio quality" modern metal record double-tracks rhythm guitar: two
independently-performed takes of the same riff, panned hard left/right, for the wide
sound that's basically non-negotiable in the genre. Everything scoped so far
(§1-9) only generates **one** rhythm guitar performance. This needs:
- Two renders of the same riff/motif, each with its own independent humanization pass
  (§14.2 item 6 — micro-timing and velocity variation) so they sound like two takes,
  not a phased duplicate of one.
- Panned hard L/R in the Reaper render (§11), with the lead/synth/orchestral layers
  sitting in the resulting center/stereo space around them.
- This is a real addition to the render pipeline, not just a mix setting — the
  *generation* engine needs to produce two distinct humanized performances, not one
  performance copied twice.

### 17.2 Human playability — do exported tabs need to be humanly playable?
"No note that doesn't exist" (§12.3) guarantees every note is theoretically valid and
physically reachable on the fretboard *in isolation*. It does not guarantee a
*sequence* of notes is playable by a human at tempo — e.g. a picking pattern that's
individually fine at every instant but physically impossible to alternate-pick at
220 BPM, or a chord-to-chord transition requiring an impossible hand jump in one
sixteenth note. Since tab/notation export (§10.4/§12.4) is an explicit goal (implying
a human might actually play this), this needs a decision:
- **Option A**: add a human-playability constraint to the chord-shape solver/riff
  engine (max notes-per-second by technique, economy-of-motion checks on fret-hand
  jumps) — more work, but exported tabs are genuinely playable by a real guitarist.
- **Option B**: accept "inhuman" precision as a legitimate feature of a
  *programmed* instrument (this is common and accepted in djent/tech-deathcore
  production — some parts are deliberately not meant to be played live), and treat
  tab export as a reference/documentation artifact rather than a performance
  guarantee.

Recommendation: default to **Option B** (matches genre norms — plenty of Born of
Osiris/Infant Annihilator-style parts aren't literally played live either), but flag
extremely dense passages in the tab view so the user knows a section is
programmed-only if they do want to hand a tab to a real player.

### 17.3 Reproducibility — formalize the seed requirement
Both djent (§8) and Anvil (§12.1) use a seeded PRNG so a given seed always
reproduces the same output. This should be an explicit, formal requirement for our
engine too — not just an implementation detail — because it enables: A/B comparison
between parameter tweaks, sharing/reproducing "that one great generation," and
deterministic automated testing (ties directly into the theory validator, §14.2
item 8 — a fixed seed makes regression tests reliable).

### 17.4 Trademark/naming consideration for band-named presets
Using "Born of Osiris," "Lorna Shore," "Shadow of Intent," "Infant Annihilator" as
literal preset names (§15/§16) is fine for personal, internal use as a style
reference — that's exactly what they're for here. If this product is ever shown
publicly, distributed, or sold, using real band names directly as feature/preset
names risks implying an affiliation or endorsement that doesn't exist, which is a
trademark concern distinct from the music-copyright question already handled
carefully throughout. Not a blocker for personal use; worth planning descriptive
alternate names (e.g. "Symphonic Slam," "Atmospheric Tech") to swap in if/when this
goes beyond personal use. (Not a lawyer — this is a practical heads-up, not legal
advice.)

### 17.5 Reaper tempo-map handling for polymeter — unresolved technical decision
Polymeter cells (§8.2) produce note positions that don't land on conventional DAW
grid lines. When writing these into a Reaper project via `reapy-boost` (§11.1), two
options: (a) keep a single, unchanging tempo/time-signature and let notes fall at
correct absolute time positions regardless of grid — simplest, most robust, but the
Reaper timeline won't visually reflect the polymeter structure; or (b) actually
insert meter/tempo-map changes matching the internal polymeter cells — lets a human
editor see and understand it correctly in Reaper's own grid, but meaningfully more
complex to generate and to keep correct when a section gets edited/moved (§10.3
blending). Leaning toward (a) for robustness, revisit if manual Reaper-side editing
of generated material turns out to be a real workflow need.

### 17.6 Preset authoring/calibration workflow
Once there are several named presets (§15.2), how do we actually know each one
sounds convincingly like its reference band? This needs a lightweight iterative
process — generate, listen, adjust preset parameters, repeat — rather than
one-shot authoring. Connects directly to the reference-corpus analysis idea already
flagged (§14.2 item 12): structurally analyzing real songs (tempo ranges, phrase
lengths, groove density — never reproducing actual riffs) gives concrete targets to
calibrate each preset against, rather than tuning by feel alone.

### 17.7 Repo/codebase structure and audio versioning
Given a real repo now exists (`z2wgv7dc4h-alt/123`), worth deciding the monorepo
layout before code starts landing in it — e.g. `/engine` (Python generation core),
`/editor` (React/TS UI), `/presets` (JSON style bundles), `/docs` (this scope doc and
future design docs). Also worth deciding now rather than discovering later: rendered
audio/Reaper project files are large binaries that don't belong in plain git history
— needs a `.gitignore` policy (and/or git-lfs if versioning actual audio output
matters) decided before the first large file gets committed by accident.

---

## 13. Suggested build order (updated after §8, §10, §11, §12, §14, §15, §16)

1. **Config/preset system + tonal layer (§2)** — foundational, everything else reads
   from it. Preset-as-data is now validated by djent's own architecture (§8.5).
2. **Rhythm engine v2 (§3 + §8.1 + §8.2 + §8.3)** — adopt the two-layer
   rhythm/timbre model and cell-length-vs-total-length polymeter mechanism wholesale;
   this replaces most of the originally-planned "curated time signature list" with
   something more powerful and less work. Foundational — riffs, drums, and leads all
   consume this.
3. **Motif-based riff engine v2 (§4)**, built on top of the rhythm engine — motif =
   a rhythm-layer cell + a pitch-layer contour, developed/reused across sections.
   Consider adopting fret/tuning-accurate pitch modeling (§8.4) here rather than free
   MIDI-integer scale degrees.
4. **Drum engine v2** (blast family, meter-aware fills), consuming the same rhythm
   engine and shared-sequence caching (§8.3) for guitar/kick unison.
5. **Structure engine (§5)** — reassembles sections using the new building blocks.
6. **Lead + synth/atmosphere layer (§6)** — polish pass once the skeleton is solid.
