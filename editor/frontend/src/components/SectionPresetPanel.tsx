import { useEffect, useState } from 'react'
import { deleteSectionPreset, fetchSectionPresets, saveSectionPreset } from '../api'
import type { EditFields } from '../types'

interface SectionPresetPanelProps {
  currentEdit: EditFields | null
  onApplyEdit: (edit: EditFields) => void
}

// P9.7 -- real, local-only, named section presets. A preset IS a complete
// real EditFields (see editor/backend/app/section_presets.py) -- saving
// only makes sense when the current section actually has an edit applied
// (the un-edited base generation isn't a reproducible EditFields), so
// Save stays disabled until `currentEdit` is real.
export function SectionPresetPanel({ currentEdit, onApplyEdit }: SectionPresetPanelProps) {
  const [presets, setPresets] = useState<Record<string, EditFields>>({})
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)

  function refresh() {
    fetchSectionPresets()
      .then(setPresets)
      .catch((e) => setError(String(e)))
  }

  useEffect(refresh, [])

  async function handleSave() {
    if (!currentEdit || !name.trim()) return
    try {
      await saveSectionPreset(name.trim(), currentEdit)
      setName('')
      refresh()
    } catch (e) {
      setError(String(e))
    }
  }

  async function handleDelete(presetName: string) {
    try {
      await deleteSectionPreset(presetName)
      refresh()
    } catch (e) {
      setError(String(e))
    }
  }

  const names = Object.keys(presets).sort()

  return (
    <div className="flex flex-col gap-2 border-t border-border pt-4">
      <span className="text-[10px] uppercase tracking-widest text-text-faint">Section presets (saved locally)</span>

      {error && <div className="text-xs text-ember">{error}</div>}

      <div className="flex gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={currentEdit ? 'Name this edit…' : 'Regenerate this section first'}
          disabled={!currentEdit}
          className="min-w-0 flex-1 rounded-md border border-border bg-ink px-2 py-1.5 text-xs text-text outline-none focus:border-violet disabled:opacity-40"
        />
        <button
          onClick={handleSave}
          disabled={!currentEdit || !name.trim()}
          title="Save the current section edit under this name"
          className="rounded-md border border-border bg-ink px-2.5 py-1.5 text-xs font-semibold text-text-dim transition hover:border-violet hover:text-violet disabled:opacity-40"
        >
          Save
        </button>
      </div>

      {names.length > 0 && (
        <div className="flex flex-col gap-1">
          {names.map((n) => (
            <div key={n} className="flex items-center justify-between gap-2 rounded-md border border-border bg-ink px-2 py-1">
              <button
                onClick={() => onApplyEdit(presets[n])}
                title={`Load "${n}" onto this section`}
                className="min-w-0 flex-1 truncate text-left text-xs text-text-dim transition hover:text-violet"
              >
                {n}
              </button>
              <button
                onClick={() => handleDelete(n)}
                title={`Delete "${n}"`}
                className="text-xs text-text-faint transition hover:text-ember"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
