import type { SectionSummary } from '../types'
import { roleColor } from '../roleColors'

interface SectionDetailPanelProps {
  section: SectionSummary | null
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-ink px-3 py-2">
      <span className="text-[10px] uppercase tracking-widest text-text-faint">{label}</span>
      <span className="font-mono text-lg text-text">{value}</span>
    </div>
  )
}

export function SectionDetailPanel({ section }: SectionDetailPanelProps) {
  if (!section) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-border p-6 text-sm text-text-faint">
        Select a section to see its real generated data.
      </div>
    )
  }

  const pmRatio = section.guitar_hits > 0 ? section.muted_hits / section.guitar_hits : 0

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5">
      <div className="flex items-center gap-2">
        <span className="h-3 w-3 rounded-full" style={{ background: roleColor(section.role) }} />
        <h2 className="text-lg font-semibold capitalize text-text">{section.role}</h2>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Stat label="Bars" value={section.bars} />
        <Stat label="Tempo" value={`${Math.round(section.bpm)} bpm`} />
        <Stat label="Guitar hits" value={section.guitar_hits} />
        <Stat label="Kick hits" value={section.kick_hits} />
        <Stat label="Palm-mute %" value={`${Math.round(pmRatio * 100)}%`} />
        <Stat label="Lead notes" value={section.lead_note_count} />
      </div>

      <div className="flex flex-col gap-1 text-sm">
        <span className="text-text-faint">Lead mode</span>
        <span className="font-mono text-text">{section.lead_mode}</span>
      </div>

      {section.chord_progression && (
        <div className="flex flex-col gap-1 text-sm">
          <span className="text-text-faint">Chord progression (scale-degree offsets)</span>
          <span className="font-mono text-text">[{section.chord_progression.join(', ')}]</span>
        </div>
      )}

      {section.chord_quality && (
        <div className="flex flex-col gap-1 text-sm">
          <span className="text-text-faint">Chord quality</span>
          <span className="font-mono text-text">{section.chord_quality}</span>
        </div>
      )}

      <p className="text-xs text-text-faint">
        Editable per-section parameters (style, density, regenerate rhythm/pitch independently) are a
        real, separate follow-up build (P9.2/P9.3) -- this panel is read-only for now.
      </p>
    </div>
  )
}
