import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { SectionSummary, TimelineBlock } from '../types'
import { roleColor } from '../roleColors'

interface SectionBlockProps {
  block: TimelineBlock
  section: SectionSummary
  selected: boolean
  soloActive: boolean
  onSelect: () => void
  onToggleMute: () => void
  onToggleSolo: () => void
  onDuplicate: () => void
  onDelete: () => void
}

export function SectionBlock({
  block,
  section,
  selected,
  soloActive,
  onSelect,
  onToggleMute,
  onToggleSolo,
  onDuplicate,
  onDelete,
}: SectionBlockProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: block.blockId,
  })

  const color = roleColor(section.role)
  const silenced = block.muted || (soloActive && !block.soloed)

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    borderColor: selected ? color : undefined,
    opacity: isDragging ? 0.4 : silenced ? 0.4 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={onSelect}
      className={`group relative flex min-w-[128px] cursor-pointer flex-col gap-2 rounded-lg border-2 bg-surface-raised p-3 transition hover:bg-surface-hover ${
        selected ? '' : 'border-border'
      }`}
    >
      <div
        {...attributes}
        {...listeners}
        className="absolute left-1 top-1 cursor-grab text-text-faint opacity-0 transition group-hover:opacity-100 active:cursor-grabbing"
        title="Drag to reorder"
      >
        ⠿
      </div>

      <div className="flex items-center gap-2 pl-3">
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
        <span className="text-sm font-semibold capitalize text-text">{section.role}</span>
      </div>

      <div className="flex items-center gap-2 pl-3 font-mono text-xs text-text-dim">
        <span>{section.bars} bars</span>
        <span>·</span>
        <span>{Math.round(section.bpm)} bpm</span>
      </div>

      <div className="flex items-center justify-between pl-3">
        <div className="flex gap-1">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleMute()
            }}
            title="Mute"
            className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase transition ${
              block.muted ? 'bg-ember text-ink' : 'bg-ink text-text-faint hover:text-text'
            }`}
          >
            M
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleSolo()
            }}
            title="Solo"
            className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase transition ${
              block.soloed ? 'bg-amber text-ink' : 'bg-ink text-text-faint hover:text-text'
            }`}
          >
            S
          </button>
        </div>
        <div className="flex gap-1 opacity-0 transition group-hover:opacity-100">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDuplicate()
            }}
            title="Duplicate"
            className="rounded px-1.5 py-0.5 text-xs text-text-faint hover:text-text"
          >
            ⧉
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            title="Delete"
            className="rounded px-1.5 py-0.5 text-xs text-text-faint hover:text-ember"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  )
}
