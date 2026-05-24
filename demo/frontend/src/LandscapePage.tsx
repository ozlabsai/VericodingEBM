import { useEffect, useRef, useState } from 'react'
import EnergyLandscape, { type LandscapeExample } from './EnergyLandscape'
import LineEditor from './LineEditor'
import CorruptionLab from './CorruptionLab'
import AppNav from './AppNav'
import { fetchEnergyField, descend, IS_STATIC_MODE, type EnergyField, type ScoreLineResponse, type Trajectory } from './api'

const SAMPLE_SPEC = `fn add(a: u32, b: u32) -> (s: u32)
    requires a + b < u32::MAX,
    ensures s == a + b,
{`

const SAMPLE_IMPL = `fn add(a: u32, b: u32) -> (s: u32)
    requires a + b < u32::MAX,
    ensures s == a + b,
{
    a + b
}`

export default function LandscapePage() {
  const [field, setField] = useState<EnergyField | null>(null)
  const [scope, setScope] = useState<'impl' | 'line'>('impl')
  const [grid, setGrid] = useState(96)
  const [userBall, setUserBall] = useState<{ x: number; y: number; energy: number } | null>(null)
  const [trajectory, setTrajectory] = useState<Trajectory | null>(null)
  const [trajStep, setTrajStep] = useState(0)
  const [scoreInfo, setScoreInfo] = useState<string | null>(null)
  const [showArrows, setShowArrows] = useState(true)
  const [showPoints, setShowPoints] = useState(true)
  const [panelSize, setPanelSize] = useState({ w: 900, h: 720 })
  const [loading, setLoading] = useState(false)
  const [examples, setExamples] = useState<LandscapeExample[]>([])
  const [highlightedImplId, setHighlightedImplId] = useState<string | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // Fetch field whenever scope/grid changes.
  useEffect(() => {
    setLoading(true)
    fetchEnergyField(scope, grid)
      .then(f => { setField(f); setLoading(false) })
      .catch(e => { setLoading(false); console.error(e) })
  }, [scope, grid])

  // Curated examples are scope-independent (they're impl-level), so load once.
  // Only show them in impl scope (line scope has its own per-line coordinates).
  useEffect(() => {
    const base = `${(import.meta as any).env?.BASE_URL ?? '/'}data`.replace(/\/+$/, '')
    fetch(`${base}/examples.json`)
      .then(r => r.ok ? r.json() : Promise.reject(`${r.status}`))
      .then((es: LandscapeExample[]) => setExamples(es))
      .catch(e => console.warn('examples load failed:', e))
  }, [])

  // Track panel size.
  useEffect(() => {
    const r = () => {
      if (panelRef.current) {
        const b = panelRef.current.getBoundingClientRect()
        setPanelSize({ w: b.width, h: b.height })
      }
    }
    r()
    window.addEventListener('resize', r)
    return () => window.removeEventListener('resize', r)
  }, [field])

  // Trajectory animation loop.
  useEffect(() => {
    if (!trajectory) return
    setTrajStep(0)
    let frame = 0
    const interval = setInterval(() => {
      frame += 1
      setTrajStep(frame)
      if (frame >= trajectory.length) clearInterval(interval)
    }, 60)
    return () => clearInterval(interval)
  }, [trajectory])

  const handleScored = async (r: ScoreLineResponse) => {
    const [x, y] = r.whole_impl_xy
    setUserBall({ x, y, energy: r.whole_impl_energy })
    setScoreInfo(`scored: E=${r.whole_impl_energy.toFixed(3)}, projected to (${x.toFixed(2)}, ${y.toFixed(2)})`)
    // Auto-trigger descent.
    try {
      const { trajectory: t } = await descend(scope, x, y, 60, 0.5)
      setTrajectory(t)
    } catch (e: any) {
      console.error(e)
    }
  }

  const handleLandscapeClick = async (x: number, y: number) => {
    setUserBall({ x, y, energy: 0 })
    setScoreInfo(`clicked at (${x.toFixed(2)}, ${y.toFixed(2)}) — descending...`)
    try {
      const { trajectory: t } = await descend(scope, x, y, 60, 0.5)
      setTrajectory(t)
    } catch (e: any) {
      console.error(e)
    }
  }

  const selectClass = "press bg-bg1 border border-line2 rounded font-mono text-[11px] text-text1 px-1.5 py-0.5 hover:border-text3"
  const controls = (
    <>
      <label className="flex items-center gap-1.5">
        <span>scope</span>
        <select value={scope} onChange={e => setScope(e.target.value as any)} className={selectClass}>
          <option value="impl">whole-impl</option>
          <option value="line">per-line</option>
        </select>
      </label>
      <label className="flex items-center gap-1.5">
        <span>grid</span>
        <select value={grid} onChange={e => setGrid(parseInt(e.target.value))} className={selectClass}>
          <option value="64">64</option>
          <option value="96">96</option>
          <option value="128">128</option>
          <option value="192">192</option>
        </select>
      </label>
      <label className="press flex items-center gap-1.5 cursor-pointer hover:text-text1">
        <input type="checkbox" checked={showArrows} onChange={e => setShowArrows(e.target.checked)} className="accent-accent" />
        <span>arrows</span>
      </label>
      <label className="press flex items-center gap-1.5 cursor-pointer hover:text-text1">
        <input type="checkbox" checked={showPoints} onChange={e => setShowPoints(e.target.checked)} className="accent-accent" />
        <span>points</span>
      </label>
      {loading && <span className="text-accent ml-auto">loading…</span>}
    </>
  )

  return (
    <div className="h-[100dvh] flex flex-col bg-bg0">
      <AppNav active="landscape" controls={controls} />

      <main className="flex-1 grid grid-cols-[1fr_380px] divide-x divide-line1 overflow-hidden">
        <section className="flex flex-col overflow-hidden">
          <div className="hairline-b px-4 py-3 flex items-baseline gap-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text1">energy landscape</span>
            <span className="font-mono text-[10px] text-text3">
              {field ? `${field.points.length} pts · ${field.arrows.length} arrows · bw ${field.bandwidth.toFixed(2)}` : '—'}
            </span>
            <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.14em] text-text3">click → drop ball</span>
          </div>
          <div ref={panelRef} className="flex-1 relative bg-bg0">
            {field && (
              <EnergyLandscape
                field={field}
                width={panelSize.w}
                height={panelSize.h}
                userBall={userBall}
                trajectory={trajectory ?? undefined}
                trajectoryStep={trajStep}
                showArrows={showArrows}
                showPoints={showPoints}
                onClick={handleLandscapeClick}
                examples={scope === 'impl' ? examples : undefined}
                highlightedImplId={highlightedImplId}
                onExampleClick={(ex) => setHighlightedImplId(ex.impl_id)}
              />
            )}
            {field && (
              <div className="absolute bottom-3 left-3 bg-bg0/85 backdrop-blur border border-line1 rounded px-2.5 py-1.5 flex items-center gap-2 font-mono text-[10px] text-text3">
                <span>low</span>
                <div className="h-1.5 w-32 rounded-sm" style={{
                  background: 'linear-gradient(to right, #000004, #350a4f, #781c6d, #bb3754, #ed6925, #fcb519, #fcfdbf)',
                }} />
                <span>high</span>
                <span className="text-text2 tabular ml-1">{field.energy_min.toFixed(1)} … {field.energy_max.toFixed(1)}</span>
              </div>
            )}
            {trajectory && (
              <div className="absolute top-3 right-3 bg-bg0/85 backdrop-blur border border-line1 rounded px-2.5 py-1.5 font-mono text-[10px] text-text2 flex items-center gap-2">
                <span className="tabular">step {trajStep}/{trajectory.length}</span>
                <button onClick={() => { setTrajectory(null); setTrajStep(0); setUserBall(null) }}
                        className="press text-text3 hover:text-accent uppercase tracking-[0.12em]">
                  clear
                </button>
              </div>
            )}
          </div>
        </section>

        <aside className="flex flex-col overflow-hidden bg-bg1">
          <div className="flex-1 overflow-y-auto no-scrollbar">
            <div className="px-4 py-4">
              <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 mb-2">how to read</div>
              <p className="text-text2 text-[13px] leading-relaxed">
                Terrain shows <span className="text-text0">E(x, y)</span>. Dark valleys are confident-safe regions;
                bright peaks are suspicious. Arrows point downhill (−∇E). Click anywhere to drop a ball; it follows
                the gradient to a basin.
              </p>
            </div>
            <div className="hairline-t">
              <CorruptionLab
                onProject={(xy, energy, label) => {
                  setUserBall({ x: xy[0], y: xy[1], energy })
                  setTrajectory(null); setTrajStep(0)
                  setScoreInfo(`${label} · E=${energy.toFixed(3)}`)
                }}
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
            {scoreInfo && (
              <div className="hairline-t px-4 py-3 font-mono text-[11px] text-text2">{scoreInfo}</div>
            )}
            {trajectory && (
              <div className="hairline-t px-4 py-3">
                <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 mb-1.5">trajectory</div>
                <div className="grid grid-cols-[80px_1fr] gap-2 font-mono text-[11px] text-text2">
                  <span className="text-text3">start E</span><span className="tabular">{trajectory[0].energy.toFixed(3)}</span>
                  <span className="text-text3">end E</span>  <span className="tabular">{trajectory[trajectory.length - 1].energy.toFixed(3)}</span>
                  <span className="text-text3">Δ</span>
                  <span className="tabular text-accent">{(trajectory[0].energy - trajectory[trajectory.length - 1].energy).toFixed(3)}</span>
                </div>
              </div>
            )}
          </div>
        </aside>
      </main>
    </div>
  )
}
