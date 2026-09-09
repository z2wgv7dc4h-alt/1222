import type { PresetSummary, SongSummary } from './types'

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

export interface ComposeParams {
  preset_id: string
  seed: number
  num_sections: number
}

export function composeSong(params: ComposeParams): Promise<SongSummary> {
  return requestJson('/api/compose', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export async function exportMidi(params: ComposeParams & { order: number[] }): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/api/export-midi`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`export-midi failed (${res.status}): ${detail}`)
  }
  return res.blob()
}
