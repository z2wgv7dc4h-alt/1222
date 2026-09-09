import type { PresetSummary } from '../types'

interface TopBarProps {
  presets: PresetSummary[]
  presetId: string
  seed: number
  numSections: number
  loading: boolean
  onPresetChange: (id: string) => void
  onSeedChange: (seed: number) => void
  onNumSectionsChange: (n: number) => void
  onRandomizeSeed: () => void
  onGenerate: () => void
  onUndo: () => void
}

export function TopBar({
  presets,
  presetId,
  seed,
  numSections,
  loading,
  onPresetChange,
  onSeedChange,
  onNumSectionsChange,
  onRandomizeSeed,
  onGenerate,
  onUndo,
}: TopBarProps) {
  return (
    <header className="flex flex-wrap items-center gap-4 border-b border-border bg-surface px-6 py-4">
      <div className="flex items-center gap-2">
        <div className="h-7 w-1.5 rounded-full bg-gradient-to-b from-ember to-violet" />
        <h1 className="text-lg font-bold tracking-tight text-text">God Tier Metal — Editor</h1>
      </div>

      <div className="ml-auto flex flex-wrap items-center gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-widest text-text-faint">Preset</span>
          <select
            value={presetId}
            onChange={(e) => onPresetChange(e.target.value)}
            className="rounded-md border border-border bg-ink px-2 py-1.5 text-sm text-text outline-none focus:border-violet"
          >
            {presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.id}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-widest text-text-faint">Seed</span>
          <div className="flex gap-1">
            <input
              type="number"
              value={seed}
              onChange={(e) => onSeedChange(Number(e.target.value))}
              className="w-24 rounded-md border border-border bg-ink px-2 py-1.5 font-mono text-sm text-text outline-none focus:border-violet"
            />
            <button
              onClick={onRandomizeSeed}
              title="Randomize seed"
              className="rounded-md border border-border px-2 text-text-dim transition hover:border-violet hover:text-violet"
            >
              ⟲
            </button>
          </div>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-widest text-text-faint">Sections</span>
          <input
            type="number"
            min={1}
            max={24}
            value={numSections}
            onChange={(e) => onNumSectionsChange(Number(e.target.value))}
            className="w-20 rounded-md border border-border bg-ink px-2 py-1.5 font-mono text-sm text-text outline-none focus:border-violet"
          />
        </label>

        <button
          onClick={onUndo}
          title="Undo the last timeline/regen edit"
          className="mt-4 rounded-md border border-border px-3 py-2 text-sm text-text-dim transition hover:border-violet hover:text-violet"
        >
          ↶ Undo
        </button>

        <button
          onClick={onGenerate}
          disabled={loading}
          className="mt-4 rounded-md bg-gradient-to-r from-ember to-violet px-5 py-2 text-sm font-bold text-ink transition hover:brightness-110 disabled:opacity-50"
        >
          {loading ? 'Generating…' : 'Generate'}
        </button>
      </div>
    </header>
  )
}
