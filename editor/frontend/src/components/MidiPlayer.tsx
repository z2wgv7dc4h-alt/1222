import { Midi } from '@tonejs/midi'
import { useEffect, useRef, useState } from 'react'
import * as Tone from 'tone'

interface MidiPlayerProps {
  midiBlob: Blob | null
  isLoading: boolean
}

const KICK_PITCHES = new Set([35, 36])
const SNARE_PITCHES = new Set([38, 40])
const HIHAT_PITCHES = new Set([42, 44, 46])

// Real Tone.js instruments, one rig per real MIDI track kind -- proper
// Web Audio synthesis via an actively-maintained library, not a hand-
// rolled numpy renderer. Built once and reused across loads.
function buildRig() {
  const distortion = new Tone.Distortion({ distortion: 0.55, wet: 0.7 }).toDestination()
  const guitar = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: 'sawtooth' },
    envelope: { attack: 0.002, decay: 0.08, sustain: 0.4, release: 0.08 },
  }).connect(distortion)
  const bass = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: 'square' },
    envelope: { attack: 0.002, decay: 0.1, sustain: 0.5, release: 0.06 },
  }).connect(distortion)
  const lead = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: 'sawtooth' },
    envelope: { attack: 0.01, decay: 0.12, sustain: 0.5, release: 0.15 },
  }).toDestination()
  const kick = new Tone.MembraneSynth({ octaves: 4, pitchDecay: 0.05 }).toDestination()
  const snare = new Tone.NoiseSynth({
    noise: { type: 'white' },
    envelope: { attack: 0.001, decay: 0.15, sustain: 0 },
  }).toDestination()
  const hihat = new Tone.MetalSynth({
    envelope: { attack: 0.001, decay: 0.08, release: 0.02 },
    harmonicity: 5.1,
    resonance: 4000,
  }).toDestination()
  // P7.1-P7.3 + the 2026-09-10 export-wiring pass: real "Pad"/"Accents"
  // MIDI tracks now carry real data (see midi_export.py's own module
  // docstring) -- undistorted, slow-attack sine pad and a short
  // triangle-wave stab voice so they read as atmosphere/accent, not more
  // distorted guitar (the routing fallback every other unrecognized
  // track would otherwise hit).
  const pad = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: 'sine' },
    envelope: { attack: 0.5, decay: 0.3, sustain: 0.7, release: 1.0 },
  }).toDestination()
  const accent = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: 'triangle' },
    envelope: { attack: 0.005, decay: 0.3, sustain: 0.1, release: 0.4 },
  }).toDestination()
  // Wired same day as the pad/accent fix above, found via direct user
  // listening feedback ("no melody... no synth... nothing") -- a real
  // "Synth" track now doubles the riff an octave up on every dense-chug
  // section (song.py's synth_double wiring). Undistorted bright
  // sawtooth, its own register/timbre so it reads as a synth doubling
  // the riff, not a second rhythm guitar.
  const synthDouble = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: 'sawtooth' },
    envelope: { attack: 0.02, decay: 0.1, sustain: 0.6, release: 0.2 },
  }).toDestination()
  return { guitar, bass, lead, kick, snare, hihat, distortion, pad, accent, synthDouble }
}

type Rig = ReturnType<typeof buildRig>

export function MidiPlayer({ midiBlob, isLoading }: MidiPlayerProps) {
  const [playing, setPlaying] = useState(false)
  const [duration, setDuration] = useState(0)
  const [ready, setReady] = useState(false)
  const rigRef = useRef<Rig | null>(null)
  const partsRef = useRef<Tone.Part[]>([])

  useEffect(() => {
    rigRef.current = buildRig()
    return () => {
      for (const part of partsRef.current) part.dispose()
      const rig = rigRef.current
      if (rig) Object.values(rig).forEach((node) => node.dispose())
    }
  }, [])

  useEffect(() => {
    if (!midiBlob) {
      setReady(false)
      return
    }
    let cancelled = false
    ;(async () => {
      const buffer = await midiBlob.arrayBuffer()
      const midi = new Midi(buffer)
      if (cancelled) return

      Tone.Transport.stop()
      Tone.Transport.cancel()
      for (const part of partsRef.current) part.dispose()
      partsRef.current = []

      const rig = rigRef.current
      if (!rig) return

      for (const track of midi.tracks) {
        const isDrums = /drum/i.test(track.name)
        const isBass = /bass/i.test(track.name)
        const isLead = /lead|harmony/i.test(track.name)
        const isPad = /pad/i.test(track.name)
        const isAccent = /accent/i.test(track.name)
        const isSynthDouble = /^synth$/i.test(track.name)

        const events = track.notes.map((note) => ({
          time: note.time,
          duration: note.duration,
          pitch: note.midi,
          velocity: note.velocity,
        }))

        const part = new Tone.Part((time, event) => {
          const vel = Math.max(0.05, event.velocity)
          if (isDrums) {
            if (KICK_PITCHES.has(event.pitch)) {
              rig.kick.triggerAttackRelease('C1', 0.2, time, vel)
            } else if (SNARE_PITCHES.has(event.pitch)) {
              rig.snare.triggerAttackRelease(0.15, time, vel)
            } else if (HIHAT_PITCHES.has(event.pitch)) {
              rig.hihat.triggerAttackRelease('16n', time, vel * 0.6)
            } else {
              rig.hihat.triggerAttackRelease('8n', time, vel * 0.8)
            }
            return
          }
          const synth = isPad
            ? rig.pad
            : isAccent
              ? rig.accent
              : isSynthDouble
                ? rig.synthDouble
                : isBass
                  ? rig.bass
                  : isLead
                    ? rig.lead
                    : rig.guitar
          const freq = Tone.Frequency(event.pitch, 'midi').toFrequency()
          synth.triggerAttackRelease(freq, Math.max(event.duration, 0.03), time, vel)
        }, events).start(0)

        partsRef.current.push(part)
      }

      setDuration(midi.duration)
      setReady(true)
    })()
    return () => {
      cancelled = true
    }
  }, [midiBlob])

  async function togglePlay() {
    if (!ready) return
    await Tone.start()
    if (playing) {
      Tone.Transport.pause()
      setPlaying(false)
    } else {
      Tone.Transport.start()
      setPlaying(true)
    }
  }

  function stop() {
    Tone.Transport.stop()
    setPlaying(false)
  }

  return (
    <div className="flex items-center gap-4 rounded-lg border border-border bg-surface px-4 py-3">
      <button
        onClick={togglePlay}
        disabled={!ready || isLoading}
        className="flex h-10 w-10 items-center justify-center rounded-full bg-ember text-ink font-bold transition hover:brightness-110 disabled:opacity-30"
      >
        {playing ? '❚❚' : '▶'}
      </button>
      <button
        onClick={stop}
        disabled={!ready || isLoading}
        className="flex h-10 w-10 items-center justify-center rounded-full border border-border-bright text-text-dim transition hover:border-ember hover:text-ember disabled:opacity-30"
      >
        ■
      </button>
      <div className="flex flex-col">
        <span className="text-xs uppercase tracking-widest text-text-faint">Arrangement preview</span>
        <span className="font-mono text-sm text-text-dim">
          {isLoading ? 'rendering…' : ready ? `${duration.toFixed(1)}s` : 'no arrangement yet'}
        </span>
      </div>
    </div>
  )
}
