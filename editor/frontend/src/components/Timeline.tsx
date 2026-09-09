import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { SortableContext, arrayMove, horizontalListSortingStrategy } from '@dnd-kit/sortable'
import type { SectionSummary, TimelineBlock } from '../types'
import { SectionBlock } from './SectionBlock'

interface TimelineProps {
  blocks: TimelineBlock[]
  sections: SectionSummary[]
  selectedBlockId: string | null
  onSelect: (blockId: string) => void
  onReorder: (blocks: TimelineBlock[]) => void
  onToggleMute: (blockId: string) => void
  onToggleSolo: (blockId: string) => void
  onDuplicate: (blockId: string) => void
  onDelete: (blockId: string) => void
  onInsertAt: (index: number) => void
}

export function Timeline({
  blocks,
  sections,
  selectedBlockId,
  onSelect,
  onReorder,
  onToggleMute,
  onToggleSolo,
  onDuplicate,
  onDelete,
  onInsertAt,
}: TimelineProps) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))
  const soloActive = blocks.some((b) => b.soloed)

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = blocks.findIndex((b) => b.blockId === active.id)
    const newIndex = blocks.findIndex((b) => b.blockId === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    onReorder(arrayMove(blocks, oldIndex, newIndex))
  }

  if (blocks.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-border text-text-faint">
        Generate a song to build a timeline.
      </div>
    )
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={blocks.map((b) => b.blockId)} strategy={horizontalListSortingStrategy}>
        <div className="flex items-stretch gap-1 overflow-x-auto pb-2">
          <InsertGap onInsert={() => onInsertAt(0)} />
          {blocks.map((block, i) => (
            <div key={block.blockId} className="flex items-stretch gap-1">
              <SectionBlock
                block={block}
                section={sections[block.sourceIndex]}
                selected={block.blockId === selectedBlockId}
                soloActive={soloActive}
                onSelect={() => onSelect(block.blockId)}
                onToggleMute={() => onToggleMute(block.blockId)}
                onToggleSolo={() => onToggleSolo(block.blockId)}
                onDuplicate={() => onDuplicate(block.blockId)}
                onDelete={() => onDelete(block.blockId)}
              />
              <InsertGap onInsert={() => onInsertAt(i + 1)} />
            </div>
          ))}
        </div>
      </SortableContext>
    </DndContext>
  )
}

function InsertGap({ onInsert }: { onInsert: () => void }) {
  return (
    <button
      onClick={onInsert}
      title="Duplicate the nearest section here"
      className="group flex w-3 shrink-0 items-center justify-center rounded transition hover:w-6 hover:bg-surface-hover"
    >
      <span className="text-sm text-text-faint opacity-0 transition group-hover:opacity-100">+</span>
    </button>
  )
}
