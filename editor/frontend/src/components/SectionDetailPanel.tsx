import type { SectionSummary } from '../types'
import { roleColor } from '../roleColors'

interface SectionDetailPanelProps {
  section: SectionSummary | null
  hasEdit: boolean
  onFullReroll: () => void
  onNewNotes: () => void
  onNewHits: () => void
  onMakeRole: (role: string) => void
  onTooBusy: () => void
  onTooThin: () => void
  onClearEdit: () => void
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-ink px-3 py-2">
      <span className="text-[10px] uppercase tracking-widest text-text-faint">{label}</span>
      <span className="font-mono text-lg text-text">{value}</span>
    </div>
  )
}

function ActionButton({ onClick, children, title }: { onClick: () => void; children: React.ReactNode; title?: string }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="rounded-md border border-border bg-ink px-2.5 py-1.5 text-xs font-semibold text-text-dim transition hover:border-violet hover:text-violet"
    >
      {children}
    </button>
  )
}

const CONVERTIBLE_ROLES = ["breakdown", "build", "verse", "chorus", "solo", "chill", "interlude"]

export function SectionDetailPanel({
  section,
  hasEdit,
  onFullReroll,
  onNewNotes,
  onNewHits,
  onMakeRole,
  onTooBusy,
  onTooThin,
  onClearEdit,
}: SectionDetailPanelProps) {
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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full" style={{ background: roleColor(section.role) }} />
          <h2 className="text-lg font-semibold capitalize text-text">{section.role}</h2>
        </div>
        {hasEdit && (
          <button onClick={onClearEdit} className="text-[10px] uppercase tracking-widest text-amber hover:text-text" title="Discard this section's edit, back to the original generation">
            edited · reset
          </button>
        )}
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

      <div className="flex flex-col gap-2 border-t border-border pt-4">
        <span className="text-[10px] uppercase tracking-widest text-text-faint">Regenerate (real, server-side)</span>
        <div className="flex flex-wrap gap-2">
          <ActionButton onClick={onFullReroll} title="Completely fresh rhythm and pitch">Full reroll</ActionButton>
          <ActionButton onClick={onNewNotes} title="Keep the rhythm, redraw only the pitch">New notes, same hits</ActionButton>
          <ActionButton onClick={onNewHits} title="Keep the pitch contour, redraw only the rhythm">Same notes, new hits</ActionButton>
        </div>
        <div className="flex flex-wrap gap-2">
          <ActionButton onClick={onTooBusy}>Too busy</ActionButton>
          <ActionButton onClick={onTooThin}>Too thin</ActionButton>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-[10px] uppercase tracking-widest text-text-faint">Make this section...</span>
        <div className="flex flex-wrap gap-2">
          {CONVERTIBLE_ROLES.filter((r) => r !== section.role).map((r) => (
            <ActionButton key={r} onClick={() => onMakeRole(r)}>
              {r}
            </ActionButton>
          ))}
        </div>
      </div>

      <p className="text-xs text-text-faint">
        Full editable parameters (style intensity, Guided-mode dials) are a real, separate follow-up
        (P9.2) -- these are the real Pro-mode regen primitives, wired directly to the engine.
      </p>
    </div>
  )
}
