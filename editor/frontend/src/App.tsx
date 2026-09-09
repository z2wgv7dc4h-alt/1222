import { useEffect, useRef, useState } from 'react'
import { composeSong, exportMidi, exportRpp, fetchPresets, type EditPayload } from './api'
import { GuidedControls } from './components/GuidedControls'
import { MidiPlayer } from './components/MidiPlayer'
import { SectionDetailPanel } from './components/SectionDetailPanel'
import { TabView } from './components/TabView'
import { Timeline } from './components/Timeline'
import { TopBar } from './components/TopBar'
import type { PresetSummary, SongSummary, TimelineBlock } from './types'

function newBlock(sourceIndex: number): TimelineBlock {
  return { blockId: crypto.randomUUID(), sourceIndex, muted: false, soloed: false, edit: null }
}

function visibleBlocks(blocks: TimelineBlock[]): TimelineBlock[] {
  const soloActive = blocks.some((b) => b.soloed)
  return blocks.filter((b) => (soloActive ? b.soloed : !b.muted))
}

function toOrderAndEdits(blocks: TimelineBlock[]): { order: number[]; edits: EditPayload[] } {
  const visible = visibleBlocks(blocks)
  const order = visible.map((b) => b.sourceIndex)
  const edits: EditPayload[] = []
  visible.forEach((b, position) => {
    if (b.edit) edits.push({ section_position: position, ...b.edit })
  })
  return { order, edits }
}

const UNDO_DEPTH = 20

export default function App() {
  const [presets, setPresets] = useState<PresetSummary[]>([])
  const [presetId, setPresetId] = useState('metalcore')
  const [seed, setSeed] = useState(1)
  const [numSections, setNumSections] = useState(8)

  // P9.2 -- Pro/Guided are the SAME real params (CLAUDE.md's own law:
  // "Guided = sliders on the same params as Pro"), just shown or hidden.
  // Nothing here is a separate data model from what /api/compose accepts.
  const [guided, setGuided] = useState(false)
  const [blendWith, setBlendWith] = useState<string | null>(null)
  const [blendT, setBlendT] = useState(0.5)
  const [blastFillChance, setBlastFillChance] = useState<number | null>(null)

  const [song, setSong] = useState<SongSummary | null>(null)
  const [arrangedSong, setArrangedSong] = useState<SongSummary | null>(null)
  const [blocks, setBlocksRaw] = useState<TimelineBlock[]>([])
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)

  const [generating, setGenerating] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [midiBlob, setMidiBlob] = useState<Blob | null>(null)
  const [error, setError] = useState<string | null>(null)

  const undoStack = useRef<TimelineBlock[][]>([])

  // Real undo (P9.4): every mutating action pushes the PRE-mutation state
  // onto a real snapshot stack (capped at UNDO_DEPTH) before applying the
  // change -- standard, real snapshot-stack undo, not a fake "last action"
  // flag.
  function setBlocks(updater: TimelineBlock[] | ((prev: TimelineBlock[]) => TimelineBlock[])) {
    setBlocksRaw((prev) => {
      undoStack.current = [...undoStack.current, prev].slice(-UNDO_DEPTH)
      return typeof updater === 'function' ? (updater as (p: TimelineBlock[]) => TimelineBlock[])(prev) : updater
    })
  }

  function handleUndo() {
    const stack = undoStack.current
    if (stack.length === 0) return
    const previous = stack[stack.length - 1]
    undoStack.current = stack.slice(0, -1)
    setBlocksRaw(previous)
  }

  useEffect(() => {
    fetchPresets()
      .then(setPresets)
      .catch((e) => setError(String(e)))
  }, [])

  function guidedParams() {
    return { blend_with: blendWith, blend_t: blendT, blast_fill_chance: blastFillChance }
  }

  async function handleGenerate() {
    setGenerating(true)
    setError(null)
    try {
      const summary = await composeSong({ preset_id: presetId, seed, num_sections: numSections, ...guidedParams() })
      setSong(summary)
      const freshBlocks = summary.sections.map((_, i) => newBlock(i))
      undoStack.current = []
      setBlocksRaw(freshBlocks)
      setSelectedBlockId(freshBlocks[0]?.blockId ?? null)
    } catch (e) {
      setError(String(e))
    } finally {
      setGenerating(false)
    }
  }

  // Real, honest scope boundary (see the P9.1 plan): "order" rearranges
  // which already-generated sections play; a block's own real "edit"
  // (P9.3) regenerates that position's actual content server-side. Every
  // arrangement OR edit change re-fetches both the real arranged summary
  // (for the detail panel) and the real MIDI (for playback).
  useEffect(() => {
    if (!song || blocks.length === 0) {
      setMidiBlob(null)
      setArrangedSong(null)
      return
    }
    const { order, edits } = toOrderAndEdits(blocks)
    if (order.length === 0) {
      setMidiBlob(null)
      setArrangedSong(null)
      return
    }
    let cancelled = false
    setExporting(true)
    const params = { preset_id: presetId, seed, num_sections: numSections, order, edits, ...guidedParams() }
    Promise.all([
      composeSong(params).then((summary) => !cancelled && setArrangedSong(summary)),
      exportMidi(params).then((blob) => !cancelled && setMidiBlob(blob)),
    ])
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setExporting(false))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [song, blocks, blendWith, blendT, blastFillChance])

  function updateBlock(blockId: string, patch: Partial<TimelineBlock>) {
    setBlocks((prev) => prev.map((b) => (b.blockId === blockId ? { ...b, ...patch } : b)))
  }

  function handleDuplicate(blockId: string) {
    setBlocks((prev) => {
      const idx = prev.findIndex((b) => b.blockId === blockId)
      if (idx === -1) return prev
      const copy = newBlock(prev[idx].sourceIndex)
      return [...prev.slice(0, idx + 1), copy, ...prev.slice(idx + 1)]
    })
  }

  function handleDelete(blockId: string) {
    setBlocks((prev) => (prev.length <= 1 ? prev : prev.filter((b) => b.blockId !== blockId)))
  }

  function handleInsertAt(index: number) {
    setBlocks((prev) => {
      if (prev.length === 0) return prev
      const neighborIndex = Math.max(0, Math.min(index, prev.length - 1))
      const copy = newBlock(prev[neighborIndex].sourceIndex)
      return [...prev.slice(0, index), copy, ...prev.slice(index)]
    })
  }

  // P9.3/P9.4: real regen primitives. `regen_seed` is always freshly
  // randomized on the client -- "Try again" is just calling this again
  // for the same block/mode, which produces a genuinely different real
  // result (not a fake reroll).
  function handleRegen(blockId: string, mode: 'full' | 'pitch' | 'rhythm', role: string | null = null) {
    setBlocks((prev) =>
      prev.map((b) =>
        b.blockId === blockId
          ? { ...b, edit: { mode, role, hit_chance_bias: b.edit?.hit_chance_bias ?? 0, regen_seed: Math.floor(Math.random() * 1e9) } }
          : b,
      ),
    )
  }

  function handleDensityNudge(blockId: string, delta: number) {
    setBlocks((prev) =>
      prev.map((b) => {
        if (b.blockId !== blockId) return b
        const current = b.edit ?? { mode: 'rhythm' as const, role: null, hit_chance_bias: 0, regen_seed: Math.floor(Math.random() * 1e9) }
        return { ...b, edit: { ...current, hit_chance_bias: Math.max(-0.6, Math.min(0.6, current.hit_chance_bias + delta)) } }
      }),
    )
  }

  function handleClearEdit(blockId: string) {
    updateBlock(blockId, { edit: null })
  }

  // P9.5 -- real Render (distinct from Preview): downloads the actual
  // .rpp Reaper project for the CURRENT real arrangement (same order +
  // edits the MIDI preview and detail panel already reflect).
  async function handleRenderRpp() {
    if (!song) return
    const { order, edits } = toOrderAndEdits(blocks)
    if (order.length === 0) return
    try {
      const blob = await exportRpp({ preset_id: presetId, seed, num_sections: numSections, order, edits, ...guidedParams() })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'arrangement.rpp'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(String(e))
    }
  }

  const selectedBlock = blocks.find((b) => b.blockId === selectedBlockId) ?? null
  const selectedPosition = selectedBlock ? visibleBlocks(blocks).findIndex((b) => b.blockId === selectedBlockId) : -1
  const selectedSection =
    arrangedSong && selectedPosition >= 0
      ? (arrangedSong.sections[selectedPosition] ?? null)
      : song && selectedBlock
        ? (song.sections[selectedBlock.sourceIndex] ?? null)
        : null

  // P9.6 -- tab data for the CURRENTLY-selected position, same real
  // order+edits the timeline/detail panel already reflect.
  const { order: tabOrder, edits: tabEdits } = toOrderAndEdits(blocks)
  const tabParams =
    song && selectedPosition >= 0 && tabOrder.length > 0
      ? { preset_id: presetId, seed, num_sections: numSections, order: tabOrder, edits: tabEdits, section_position: selectedPosition, ...guidedParams() }
      : null

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar
        presets={presets}
        presetId={presetId}
        seed={seed}
        numSections={numSections}
        loading={generating}
        onPresetChange={setPresetId}
        onSeedChange={setSeed}
        onNumSectionsChange={setNumSections}
        onRandomizeSeed={() => setSeed(Math.floor(Math.random() * 100000))}
        onGenerate={handleGenerate}
        onUndo={handleUndo}
      />

      <GuidedControls
        guided={guided}
        presets={presets.filter((p) => p.id !== presetId)}
        blendWith={blendWith}
        blendT={blendT}
        blastFillChance={blastFillChance}
        onToggleGuided={() => setGuided((g) => !g)}
        onBlendWithChange={setBlendWith}
        onBlendTChange={setBlendT}
        onBlastFillChanceChange={setBlastFillChance}
      />

      <main className="flex flex-1 flex-col gap-6 p-6">
        {error && (
          <div className="rounded-md border border-ember bg-ember/10 px-4 py-2 text-sm text-ember">
            {error}
          </div>
        )}

        {(arrangedSong ?? song) && (
          <div className="flex flex-col gap-2 text-sm text-text-dim">
            <span>
              {(arrangedSong ?? song)!.preset_id} · {(arrangedSong ?? song)!.sequence.length} sections · judge:{' '}
              <span className={(arrangedSong ?? song)!.judge.ok ? 'text-role-verse' : 'text-ember'}>
                {(arrangedSong ?? song)!.judge.ok ? 'ok' : 'needs review'}
              </span>{' '}
              <span className="font-mono text-text-faint">
                (hits {(arrangedSong ?? song)!.judge.hits}, pm {(arrangedSong ?? song)!.judge.pm_ratio}, kick-lock{' '}
                {(arrangedSong ?? song)!.judge.kick_lock})
              </span>
            </span>
          </div>
        )}

        <Timeline
          blocks={blocks}
          sections={song?.sections ?? []}
          selectedBlockId={selectedBlockId}
          onSelect={setSelectedBlockId}
          onReorder={setBlocks}
          onToggleMute={(id) => updateBlock(id, { muted: !blocks.find((b) => b.blockId === id)?.muted })}
          onToggleSolo={(id) => updateBlock(id, { soloed: !blocks.find((b) => b.blockId === id)?.soloed })}
          onDuplicate={handleDuplicate}
          onDelete={handleDelete}
          onInsertAt={handleInsertAt}
        />

        <div className="flex items-center gap-3">
          <MidiPlayer midiBlob={midiBlob} isLoading={exporting} />
          <button
            onClick={handleRenderRpp}
            disabled={!song}
            title="Render a real, DAW-importable Reaper project for the current arrangement"
            className="rounded-md border border-border bg-surface px-4 py-2 text-sm font-semibold text-text-dim transition hover:border-violet hover:text-violet disabled:opacity-40"
          >
            ⬇ Render .rpp
          </button>
        </div>

        <div className="flex flex-wrap items-start gap-6">
          <div className="max-w-sm">
            <SectionDetailPanel
              section={selectedSection}
              hasEdit={!!selectedBlock?.edit}
              onFullReroll={() => selectedBlockId && handleRegen(selectedBlockId, 'full')}
              onNewNotes={() => selectedBlockId && handleRegen(selectedBlockId, 'pitch')}
              onNewHits={() => selectedBlockId && handleRegen(selectedBlockId, 'rhythm')}
              onMakeRole={(role) => selectedBlockId && handleRegen(selectedBlockId, 'full', role)}
              onTooBusy={() => selectedBlockId && handleDensityNudge(selectedBlockId, -0.15)}
              onTooThin={() => selectedBlockId && handleDensityNudge(selectedBlockId, 0.15)}
              onClearEdit={() => selectedBlockId && handleClearEdit(selectedBlockId)}
            />
          </div>
          <div className="min-w-0 flex-1">
            <span className="mb-2 block text-[10px] uppercase tracking-widest text-text-faint">
              Tab (real, per-cell fretboard positions)
            </span>
            <TabView params={tabParams} />
          </div>
        </div>
      </main>
    </div>
  )
}
