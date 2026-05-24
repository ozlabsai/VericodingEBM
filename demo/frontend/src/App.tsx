import { useEffect, useMemo, useRef, useState } from 'react'
import ManifoldScatter, { type ScatterPoint } from './ManifoldScatter'
import LineEditor from './LineEditor'
import ExamplesPicker from './ExamplesPicker'
import CorruptionLab from './CorruptionLab'
import EnergyLegend from './EnergyLegend'
import AppNav, { withBase } from './AppNav'
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

  const navMeta = (
    <>
      <span className="tabular">{impls.length.toLocaleString()} impls</span>
      <span className="text-line2">·</span>
      <span className="tabular">{allLines.length.toLocaleString()} lines</span>
      <span className="text-line2">·</span>
      <span className="tabular text-neg normal-case">{impls.filter(i => i.status === 'fail').length} fail</span>
    </>
  )

  return (
    <div className="h-[100dvh] flex flex-col bg-bg0">
      <AppNav active="manifold" meta={navMeta} />

      {/* Main — hairline-divided regions, not boxed cards */}
      <main className="flex-1 grid grid-cols-[1fr_1fr_380px] divide-x divide-line1 overflow-hidden">
        {/* Impl manifold region */}
        <section className="flex flex-col overflow-hidden">
          <div className="hairline-b px-4 py-3 flex items-baseline gap-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text1">impl manifold</span>
            <span className="font-mono text-[10px] text-text3">color · whole-impl energy</span>
            <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.14em] text-text3">click → drill</span>
          </div>
          <div ref={implPanelRef} className="flex-1 relative bg-bg0">
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
            <div className="absolute bottom-3 left-3 z-10">
              <EnergyLegend range={impls.length > 0 ? implEnergyRange : null} />
            </div>
          </div>
        </section>

        {/* Line manifold region */}
        <section className="flex flex-col overflow-hidden">
          <div className="hairline-b px-4 py-3 flex items-baseline gap-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text1">line manifold</span>
            <span className="font-mono text-[10px] text-text3">color · per-line energy</span>
            {selectedImpl && (
              <span className="ml-auto font-mono text-[10px] text-accent truncate max-w-[60%]">
                {selectedImpl.impl.impl_id} · {selectedImpl.lines.length}L
              </span>
            )}
          </div>
          <div ref={linePanelRef} className="flex-1 relative bg-bg0">
            {allLines.length > 0 && (
              <ManifoldScatter
                points={linePoints}
                width={linePanelSize.w}
                height={linePanelSize.h}
                energyRange={lineEnergyRange}
              />
            )}
            <div className="absolute bottom-3 left-3 z-10">
              <EnergyLegend range={allLines.length > 0 ? lineEnergyRange : null} />
            </div>
          </div>
        </section>

        {/* Right rail */}
        <aside className="flex flex-col overflow-hidden bg-bg1">
          <div className="flex-1 overflow-y-auto no-scrollbar">
            <CorruptionLab onProject={handleCorruptionProject} />
            <div className="hairline-t">
              <ExamplesPicker
                onPick={loadImpl}
                selectedId={selectedImpl?.impl.impl_id ?? null}
              />
            </div>
            {!IS_STATIC_MODE && (
              <div className="hairline-t">
                <LineEditor
                  initialSpec={SAMPLE_SPEC}
                  initialImpl={SAMPLE_IMPL}
                  onScored={handleScored}
                />
              </div>
            )}
            {selectedImpl && (
              <div className="hairline-t px-4 py-4">
                <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 mb-1.5 truncate">
                  {selectedImpl.impl.impl_id}
                </div>
                <div className="font-mono text-[10px] text-text3 mb-3 flex items-baseline gap-2 flex-wrap">
                  <span>spec={selectedImpl.impl.spec_id.slice(0, 24)}…</span>
                  <span className="text-line2">·</span>
                  <span className={selectedImpl.impl.status === 'fail' ? 'text-neg' : 'text-pos'}>{selectedImpl.impl.status}</span>
                  <span className="text-line2">·</span>
                  <span className="tabular text-text1">E={selectedImpl.impl.whole_impl_energy.toFixed(3)}</span>
                </div>
                <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 mb-1.5">lines, energy desc</div>
                <div className="flex flex-col gap-1 font-mono text-[11px]">
                  {selectedImpl.lines
                    .slice()
                    .sort((a, b) => b.energy - a.energy)
                    .slice(0, 30)
                    .map(l => (
                      <div key={l.line_idx} className="grid grid-cols-[44px_1fr] gap-2 items-baseline">
                        <span className="tabular text-text3 text-right">{l.energy.toFixed(2)}</span>
                        <span className={`truncate ${l.is_buggy ? 'text-neg' : 'text-text2'}`}>
                          {l.is_buggy ? '◆ ' : '  '}{l.line_text.slice(0, 80)}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        </aside>
      </main>
    </div>
  )
}
