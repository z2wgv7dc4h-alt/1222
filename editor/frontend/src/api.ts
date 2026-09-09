import type { EditFields, PresetSummary, RegenEdit, SongSummary, TabCell } from './types'

const BASE_URL = 'http://localhost:8000'

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`${path} failed (${res.status}): ${detail}`)
  }
  return res.json() as Promise<T>
}

export function fetchPresets(): Promise<PresetSummary[]> {
  return requestJson('/api/presets')
}

export interface EditPayload extends RegenEdit {
  section_position: number
}

export interface ComposeParams {
  preset_id: string
  seed: number
  num_sections: number
  order?: number[]
  edits?: EditPayload[]
  // P9.2 -- Guided Mode's real knobs (see editor/backend/app/main.py's
  // ComposeRequest for the full real citation).
  blend_with?: string | null
  blend_t?: number
  blast_fill_chance?: number | null
}

export function composeSong(params: ComposeParams): Promise<SongSummary> {
  return requestJson('/api/compose', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

async function exportFile(path: string, params: ComposeParams & { order: number[] }): Promise<Blob> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`${path} failed (${res.status}): ${detail}`)
  }
  return res.blob()
}

export function exportMidi(params: ComposeParams & { order: number[] }): Promise<Blob> {
  return exportFile('/api/export-midi', params)
}

// P9.5 -- real Render (distinct from Preview): a real, DAW-importable
// Reaper project file, same real arrange+edits pipeline as the MIDI
// preview export.
export function exportRpp(params: ComposeParams & { order: number[] }): Promise<Blob> {
  return exportFile('/api/export-rpp', params)
}

// P9.6 -- real tab data for one section, same real arrange+edits
// pipeline as compose/export (so a regenerated/reordered section's tab
// reflects its actual current content, not a stale base one).
export function fetchSectionTab(params: ComposeParams & { section_position: number }): Promise<TabCell[]> {
  return requestJson('/api/section-tab', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

// P9.7 -- real, local-only named section presets: a saved preset IS a
// complete, reproducible EditFields (mode/role/hit_chance_bias/
// regen_seed) under a user-given name (see editor/backend/app/
// section_presets.py).
export function fetchSectionPresets(): Promise<Record<string, EditFields>> {
  return requestJson('/api/section-presets')
}

export function saveSectionPreset(name: string, edit: EditFields): Promise<void> {
  return requestJson('/api/section-presets', {
    method: 'POST',
    body: JSON.stringify({ name, edit }),
  }).then(() => undefined)
}

export function deleteSectionPreset(name: string): Promise<void> {
  return requestJson(`/api/section-presets/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  }).then(() => undefined)
}
