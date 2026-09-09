// Mirrors editor/backend/app/serialize.py's real JSON shapes exactly --
// every field here corresponds to a real field that module reads off the
// engine's own compose_song/preset output, never a UI-invented one.

export interface PresetSummary {
  id: string
  description: string
  tuning_key: string
  scale: string
  bpm: number
  bars: number
  feel: string
  kick: string
  group: number | null
  pedal: number | null
  dissonance: number
  octave_stab: boolean
}

export interface SectionSummary {
  role: string
  bars: number
  bpm: number
  lead_mode: string
  lead_note_count: number
  chord_progression: number[] | null
  chord_quality: string | null
  guitar_hits: number
  muted_hits: number
  open_hits: number
  kick_hits: number
}

export interface JudgeResult {
  ok: boolean
  hits: number
  pm_ratio: number
  kick_lock: number
}

export interface SongSummary {
  preset_id: string
  sequence: string[]
  sections: SectionSummary[]
  judge: JudgeResult
}

// A timeline "block" is a client-side arrangement entry: it points back at
// one real section from the last composed SongSummary by index, plus a
// stable id so dnd-kit can track it independently of that index (the same
// real section can appear more than once via duplicate).
export interface TimelineBlock {
  blockId: string
  sourceIndex: number
  muted: boolean
  soloed: boolean
}
