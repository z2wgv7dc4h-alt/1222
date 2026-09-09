import { useEffect, useState } from 'react'
import { composeSong, exportMidi, fetchPresets } from './api'
import { MidiPlayer } from './components/MidiPlayer'
import { SectionDetailPanel } from './components/SectionDetailPanel'
import { Timeline } from './components/Timeline'
import { TopBar } from './components/TopBar'
import type { PresetSummary, SongSummary, TimelineBlock } from './types'

function newBlock(sourceIndex: number): TimelineBlock {
  return { blockId: crypto.randomUUID(), sourceIndex, muted: false, soloed: false }
}

function effectiveOrder(blocks: TimelineBlock[]): number[] {
  const soloActive = blocks.some((b) => b.soloed)
  return blocks
    .filter((b) => (soloActive ? b.soloed : !b.muted))
    .map((b) => b.sourceIndex)
}

export default function App() {
  const [presets, setPresets] = useState<PresetSummary[]>([])
  const [presetId, setPresetId] = useState('metalcore')
  const [seed, setSeed] = useState(1)
  const [numSections, setNumSections] = useState(8)

  const [song, setSong] = useState<SongSummary | null>(null)
  const [blocks, setBlocks] = useState<TimelineBlock[]>([])
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)

  const [generating, setGenerating] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [midiBlob, setMidiBlob] = useState<Blob | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchPresets()
      .then(setPresets)
      .catch((e) => setError(String(e)))
  }, [])

  async function handleGenerate() {
    setGenerating(true)
    setError(null)
    try {
      const summary = await composeSong({ preset_id: presetId, seed, num_sections: numSections })
      setSong(summary)
      const freshBlocks = summary.sections.map((_, i) => newBlock(i))
      setBlocks(freshBlocks)
      setSelectedBlockId(freshBlocks[0]?.blockId ?? null)
    } catch (e) {
      setError(String(e))
    } finally {
      setGenerating(false)
    }
  }

  // Real, honest scope boundary (see the P9.1 plan): edits below rearrange
  // which already-generated sections play and in what order -- they do
  // NOT regenerate content or blend a new boundary. Every arrangement
  // change re-exports MIDI from the current real order.
  useEffect(() => {
    if (!song || blocks.length === 0) {
      setMidiBlob(null)
      return
    }
    const order = effectiveOrder(blocks)
    if (order.length === 0) {
      setMidiBlob(null)
      return
    }
    let cancelled = false
    setExporting(true)
    exportMidi({ preset_id: presetId, seed, num_sections: numSections, order })
      .then((blob) => {
        if (!cancelled) setMidiBlob(blob)
      })
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setExporting(false))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [song, blocks])

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

  const selectedSection =
    song && selectedBlockId
      ? song.sections[blocks.find((b) => b.blockId === selectedBlockId)?.sourceIndex ?? -1] ?? null
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
      />

      <main className="flex flex-1 flex-col gap-6 p-6">
        {error && (
          <div className="rounded-md border border-ember bg-ember/10 px-4 py-2 text-sm text-ember">
            {error}
          </div>
        )}

        {song && (
          <div className="flex flex-col gap-2 text-sm text-text-dim">
            <span>
              {song.preset_id} · {song.sequence.length} sections · judge:{' '}
              <span className={song.judge.ok ? 'text-role-verse' : 'text-ember'}>
                {song.judge.ok ? 'ok' : 'needs review'}
              </span>{' '}
              <span className="font-mono text-text-faint">
                (hits {song.judge.hits}, pm {song.judge.pm_ratio}, kick-lock {song.judge.kick_lock})
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

        <MidiPlayer midiBlob={midiBlob} isLoading={exporting} />

        <div className="max-w-sm">
          <SectionDetailPanel section={selectedSection} />
        </div>
      </main>
    </div>
  )
}
