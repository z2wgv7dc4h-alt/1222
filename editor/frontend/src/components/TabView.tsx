import { useEffect, useRef, useState } from 'react'
import { Formatter, GhostNote, Renderer, TabNote, TabStave } from 'vexflow'
import { fetchSectionTab, type ComposeParams } from '../api'
import type { TabCell } from '../types'

interface TabViewProps {
  params: (ComposeParams & { section_position: number }) | null
}

// P9.6 -- real per-cell (string, fret) data (see serialize.py's
// summarize_tab) rendered as an actual VexFlow tab staff, never a
// fabricated fingering. `duration` is in real beats (song.py's own
// convention -- 1.0 = one quarter-note beat in 4/4, matching
// midi_export.py's `_beats_to_ticks`), snapped to the nearest standard
// notated duration below since this engine's real rhythm devices
// (triplet feel, gallop/stutter-chug asymmetric splits) don't all land
// on a power-of-two beat value VexFlow can notate exactly -- an honest,
// documented approximation, not a silent one.
const _STANDARD_DURATIONS: Array<[number, string]> = [
  [4, 'w'], [3, 'hd'], [2, 'h'], [1.5, 'qd'], [1, 'q'],
  [0.75, '8d'], [0.5, '8'], [0.375, '16d'], [0.25, '16'], [0.125, '32'],
]

function nearestVexDuration(beats: number): string {
  let best = _STANDARD_DURATIONS[_STANDARD_DURATIONS.length - 1]
  let bestDiff = Infinity
  for (const entry of _STANDARD_DURATIONS) {
    const diff = Math.abs(entry[0] - beats)
    if (diff < bestDiff) {
      best = entry
      bestDiff = diff
    }
  }
  return best[1]
}

function buildNotes(cells: TabCell[]) {
  return cells.map((cell) => {
    const duration = nearestVexDuration(cell.duration)
    if (cell.is_rest || cell.string === null || cell.fret === null) {
      return new GhostNote({ duration })
    }
    return new TabNote({ positions: [{ str: cell.string + 1, fret: cell.fret }], duration })
  })
}

export function TabView({ params }: TabViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [tab, setTab] = useState<TabCell[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!params) {
      setTab(null)
      return
    }
    let cancelled = false
    fetchSectionTab(params)
      .then((cells) => !cancelled && setTab(cells))
      .catch((e) => !cancelled && setError(String(e)))
    return () => {
      cancelled = true
    }
  }, [params])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    el.innerHTML = ''
    if (!tab || tab.length === 0) return

    const notes = buildNotes(tab)
    const width = Math.max(400, notes.length * 32 + 40)
    try {
      const renderer = new Renderer(el, Renderer.Backends.SVG)
      renderer.resize(width, 140)
      const context = renderer.getContext()
      // Dark theme: VexFlow's default black stroke/fill is invisible
      // against this app's near-black `bg-ink` container.
      context.setFillStyle('#e8e6ee')
      context.setStrokeStyle('#e8e6ee')
      const stave = new TabStave(10, 20, width - 20)
      stave.addClef('tab')
      stave.setContext(context).draw()
      Formatter.FormatAndDraw(context, stave, notes)
      setError(null)
    } catch (e) {
      setError(`Could not render tab: ${String(e)}`)
    }
  }, [tab])

  if (!params) {
    return <div className="text-xs text-text-faint">Select a section to see its real tab.</div>
  }

  return (
    <div className="flex flex-col gap-2">
      {error && <div className="text-xs text-ember">{error}</div>}
      <div className="overflow-x-auto rounded-md border border-border bg-ink p-2" ref={containerRef} />
    </div>
  )
}
