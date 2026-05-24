import { useEffect, useMemo, useRef, useState } from 'react'
import ManifoldScatter, { type ScatterPoint } from './ManifoldScatter'
import LineEditor from './LineEditor'
import ExamplesPicker from './ExamplesPicker'
import CorruptionLab from './CorruptionLab'
import { fetchImpls, fetchLines, fetchImplDetail, IS_STATIC_MODE, type ImplPoint, type LinePoint, type ImplDetail, type ScoreLineResponse } from './api'

const SAMPLE_SPEC = `// Returns the sum of two non-negative integers.
fn add(a: u32, b: u32) -> (s: u32)
    requires a + b < u32::MAX,
    ensures s == a + b,
{`

const SAMPLE_IMPL = `fn add(a: u32, b: u32) -> (s: u32)
    requires a + b < u32::MAX,
    ensures s == a + b,
{
    a + b
}`

export default function App() {
  const [impls, setImpls] = useState<ImplPoint[]>([])
  const [allLines, setAllLines] = useState<LinePoint[]>([])
  const [selectedImpl, setSelectedImpl] = useState<ImplDetail | null>(null)
  const [hoverInfo, setHoverInfo] = useState<string | null>(null)
  const [userScore, setUserScore] = useState<ScoreLineResponse | null>(null)
  const [implPanelSize, setImplPanelSize] = useState({ w: 700, h: 600 })
  const [linePanelSize, setLinePanelSize] = useState({ w: 700, h: 600 })
  const implPanelRef = useRef<HTMLDivElement>(null)
  const linePanelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    Promise.all([fetchImpls(), fetchLines()])
      .then(([is, ls]) => { setImpls(is); setAllLines(ls) })
      .catch(e => setHoverInfo(`load error: ${e.message}`))
  }, [])

  // Track panel sizes for responsive deck.gl viewports.
  useEffect(() => {
    const onResize = () => {
      if (implPanelRef.current) {
        const r = implPanelRef.current.getBoundingClientRect()
        setImplPanelSize({ w: r.width, h: r.height })
      }
      if (linePanelRef.current) {
        const r = linePanelRef.current.getBoundingClientRect()
        setLinePanelSize({ w: r.width, h: r.height })
      }
    }
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [impls, selectedImpl])

  // --- Build scatter point arrays from raw data ---
  const implPoints = useMemo<ScatterPoint[]>(() => {
    const pts: ScatterPoint[] = impls.map(p => ({
      x: p.x, y: p.y,
      energy: p.whole_impl_energy,
      isHighlighted: p.status === 'fail',
      label: `${p.impl_id}\nspec=${p.spec_id}\nstatus=${p.status}\nlines=${p.n_lines}`,
      payload: p.impl_id,
    }))
    if (userScore) {
      pts.push({
        x: userScore.whole_impl_xy[0],
        y: userScore.whole_impl_xy[1],
        energy: userScore.whole_impl_energy,
        isUserPoint: true,
        label: `YOUR IMPL\nenergy=${userScore.whole_impl_energy.toFixed(3)}`,
        payload: 'user',
      })
    }
    return pts
  }, [impls, userScore])

  const linePoints = useMemo<ScatterPoint[]>(() => {
    // If an impl is selected, show ONLY that impl's lines big + the rest faded.
    // Otherwise show all lines.
    const baseRows = allLines
    const focused = selectedImpl?.impl.impl_id ?? null
    const pts: ScatterPoint[] = baseRows.map(p => ({
      x: p.x, y: p.y,
      energy: p.energy,
      isHighlighted: p.is_buggy || (focused != null && p.impl_id === focused),
      label: `${p.line_text}\n(${p.impl_id}, line ${p.line_idx})`,
      payload: `${p.impl_id}#${p.line_idx}`,
    }))
    if (userScore && userScore.line_xys.length > 0) {
      // Show the user impl's lines too, marked as user points.
      userScore.line_xys.forEach(([x, y], i) => {
        pts.push({
          x, y,
          energy: userScore.per_line_energies[i] ?? 0,
          isUserPoint: true,
          label: `YOUR LINE ${i}\nenergy=${(userScore.per_line_energies[i] ?? 0).toFixed(3)}`,
          payload: `user#${i}`,
        })
      })
    }
    return pts
  }, [allLines, userScore, selectedImpl])

  // --- Color scale: use percentile-based range so a few outliers don't wash everything out ---
  const implEnergyRange: [number, number] = useMemo(() => {
    if (impls.length === 0) return [0, 1]
    const es = [...impls.map(i => i.whole_impl_energy)].sort((a, b) => a - b)
    return [es[Math.floor(es.length * 0.05)], es[Math.floor(es.length * 0.95)]]
  }, [impls])

  const lineEnergyRange: [number, number] = useMemo(() => {
    if (allLines.length === 0) return [0, 1]
    const es = [...allLines.map(l => l.energy)].sort((a, b) => a - b)
    return [es[Math.floor(es.length * 0.05)], es[Math.floor(es.length * 0.95)]]
  }, [allLines])

  // --- Handlers ---
  const loadImpl = async (id: string) => {
    try {
      const detail = await fetchImplDetail(id)
      setSelectedImpl(detail)
    } catch (e: any) {
      setHoverInfo(`fetch error: ${e.message}`)
    }
  }
  const handleImplClick = (pt: ScatterPoint) => {
    const id = pt.payload
    if (typeof id !== 'string' || id === 'user') return
    loadImpl(id)
  }

  const handleScored = (resp: ScoreLineResponse, _spec: string, _impl: string) => {
    setUserScore(resp)
  }

  // CorruptionLab → also drops a ball on the impl manifold for visual feedback.
  const handleCorruptionProject = (xy: [number, number], energy: number, _label: string) => {
    setUserScore({
      per_line_energies: [],
      line_xys: [],
      whole_impl_energy: energy,
      whole_impl_xy: xy,
    } as ScoreLineResponse)
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="bg-ink/80 backdrop-blur-md border-b border-border px-4 py-2.5 flex items-center gap-5">
        <a href="/" className="flex items-baseline gap-2 group">
          <span className="font-serif italic text-base text-fg leading-none">VericodingEBM</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">manifold</span>
        </a>
        <nav className="flex items-center gap-0.5 font-mono text-[10px] uppercase tracking-[0.16em]">
          <a href="/manifold"    className="px-2 py-1 rounded text-accent">manifold</a>
          <a href="/landscape"   className="px-2 py-1 rounded text-muted hover:text-fg transition-colors">2d</a>
          <a href="/landscape3d" className="px-2 py-1 rounded text-muted hover:text-fg transition-colors">3d</a>
        </nav>
        <div className="font-mono text-[11px] text-body/80 tabular-display">
          {impls.length.toLocaleString()} <span className="text-muted">impls</span>
          <span className="text-border mx-1.5">·</span>
          {allLines.length.toLocaleString()} <span className="text-muted">lines</span>
          <span className="text-border mx-1.5">·</span>
          <span className="text-warm">{impls.filter(i => i.status === 'fail').length}</span> <span className="text-muted">fail</span>
        </div>
        <div className="ml-auto text-xs text-muted">
          {hoverInfo ?? 'click an impl on the left to drill in · use the corruption lab on the right'}
        </div>
      </header>

      {/* Main grid: 2 manifold panels + side editor */}
      <main className="flex-1 grid grid-cols-[1fr_1fr_360px] gap-2 p-2 overflow-hidden">
        {/* Impl manifold */}
        <div className="flex flex-col bg-panel border border-border rounded overflow-hidden">
          <div className="px-3 py-2 text-xs border-b border-border flex items-center gap-2">
            <span className="font-semibold">Impl manifold</span>
            <span className="text-zinc-500">color = whole-impl energy</span>
            <span className="ml-auto text-zinc-500">click → drill</span>
          </div>
          <div ref={implPanelRef} className="flex-1 relative">
            {impls.length > 0 && (
              <ManifoldScatter
                points={implPoints}
                width={implPanelSize.w}
                height={implPanelSize.h}
                energyRange={implEnergyRange}
                onClick={handleImplClick}
                selectedKey={selectedImpl?.impl.impl_id ?? null}
              />
            )}
          </div>
        </div>

        {/* Line manifold */}
        <div className="flex flex-col bg-panel border border-border rounded overflow-hidden">
          <div className="px-3 py-2 text-xs border-b border-border flex items-center gap-2">
            <span className="font-semibold">Line manifold</span>
            <span className="text-zinc-500">color = per-line energy</span>
            {selectedImpl && (
              <span className="ml-auto text-accent">
                showing {selectedImpl.impl.impl_id} ({selectedImpl.lines.length} lines)
              </span>
            )}
          </div>
          <div ref={linePanelRef} className="flex-1 relative">
            {allLines.length > 0 && (
              <ManifoldScatter
                points={linePoints}
                width={linePanelSize.w}
                height={linePanelSize.h}
                energyRange={lineEnergyRange}
              />
            )}
          </div>
        </div>

        {/* Right rail: corruption-lab + examples + (live-only) editor */}
        <aside className="flex flex-col gap-2 overflow-hidden">
          <CorruptionLab onProject={handleCorruptionProject} />
          <ExamplesPicker
            onPick={loadImpl}
            selectedId={selectedImpl?.impl.impl_id ?? null}
          />
          {!IS_STATIC_MODE && (
            <LineEditor
              initialSpec={SAMPLE_SPEC}
              initialImpl={SAMPLE_IMPL}
              onScored={handleScored}
            />
          )}
          {selectedImpl && (
            <div className="bg-panel border border-border rounded p-3 overflow-y-auto flex-1">
              <div className="text-xs text-zinc-400 uppercase tracking-wider mb-1">
                {selectedImpl.impl.impl_id}
              </div>
              <div className="text-xs text-zinc-500 mb-2">
                spec={selectedImpl.impl.spec_id} · status={selectedImpl.impl.status} · whole-impl energy={selectedImpl.impl.whole_impl_energy.toFixed(3)}
              </div>
              <div className="text-xs text-zinc-400 uppercase tracking-wider mb-1">Lines (by energy desc)</div>
              <div className="flex flex-col gap-1 text-xs font-mono">
                {selectedImpl.lines
                  .slice()
                  .sort((a, b) => b.energy - a.energy)
                  .slice(0, 30)
                  .map(l => (
                    <div key={l.line_idx} className="flex gap-2 items-baseline">
                      <span className="text-zinc-500 w-10 shrink-0 text-right">{l.energy.toFixed(2)}</span>
                      <span className={l.is_buggy ? 'text-warm' : 'text-zinc-300'}>
                        {l.is_buggy ? '✱ ' : '  '}{l.line_text.slice(0, 80)}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </aside>
      </main>
    </div>
  )
}
