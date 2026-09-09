import type { PresetSummary } from '../types'

interface GuidedControlsProps {
  guided: boolean
  presets: PresetSummary[]
  blendWith: string | null
  blendT: number
  blastFillChance: number | null
  onToggleGuided: () => void
  onBlendWithChange: (id: string | null) => void
  onBlendTChange: (t: number) => void
  onBlastFillChanceChange: (v: number | null) => void
}

// P9.2 -- Guided Mode speaks in taste, not parameters (scope sec.15.1):
// the SAME real underlying knobs Pro mode touches directly (blend_with/
// blend_t -> presets.blend_presets, blast_fill_chance -> the real
// per-section blast coin-flip), just exposed as a single "lean toward"
// slider and a named "blast-beat frequency" dial instead of raw numbers.
export function GuidedControls({
  guided,
  presets,
  blendWith,
  blendT,
  blastFillChance,
  onToggleGuided,
  onBlendWithChange,
  onBlendTChange,
  onBlastFillChanceChange,
}: GuidedControlsProps) {
  return (
    <div className="flex w-full flex-wrap items-center gap-4 border-b border-border bg-ink px-6 py-3">
      <button
        onClick={onToggleGuided}
        className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-widest transition ${
          guided ? 'bg-violet text-ink' : 'border border-border text-text-faint hover:text-text'
        }`}
      >
        {guided ? 'Guided' : 'Pro'}
      </button>

      {(
        <>
          <label className="flex items-center gap-2 text-xs text-text-dim">
            <span className="uppercase tracking-widest text-text-faint">
              {guided ? 'Lean toward' : 'blend_with / blend_t'}
            </span>
            <select
              value={blendWith ?? ''}
              onChange={(e) => onBlendWithChange(e.target.value || null)}
              className="rounded-md border border-border bg-surface px-2 py-1 text-text"
            >
              <option value="">(no blend)</option>
              {presets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id}
                </option>
              ))}
            </select>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={blendT}
              disabled={!blendWith}
              onChange={(e) => onBlendTChange(Number(e.target.value))}
              className="w-32 accent-violet"
            />
            <span className="w-10 font-mono text-text-faint">{Math.round(blendT * 100)}%</span>
          </label>

          <label className="flex items-center gap-2 text-xs text-text-dim">
            <span className="uppercase tracking-widest text-text-faint">
              {guided ? 'Blast-beat frequency' : 'blast_fill_chance'}
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={blastFillChance ?? 0.35}
              onChange={(e) => onBlastFillChanceChange(Number(e.target.value))}
              className="w-32 accent-ember"
            />
            <span className="w-10 font-mono text-text-faint">
              {Math.round((blastFillChance ?? 0.35) * 100)}%
            </span>
          </label>
        </>
      )}
    </div>
  )
}
