import { useEffect, useRef, useState } from 'react'
import EnergyLandscape, { type LandscapeExample } from './EnergyLandscape'
import LineEditor from './LineEditor'
import CorruptionLab from './CorruptionLab'
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

  return (
    <div className="h-screen flex flex-col">
      <header className="bg-panel border-b border-border px-4 py-2 flex items-center gap-4">
        <h1 className="text-sm font-semibold tracking-tight">
          EBM <span className="text-zinc-500">energy landscape (run #10)</span>
        </h1>
        <nav className="flex gap-2 text-xs">
          <a href="/" className="text-zinc-500 hover:text-zinc-300">manifold</a>
          <span className="text-zinc-700">|</span>
          <a href="/landscape" className="text-accent font-medium">landscape 2D</a>
          <span className="text-zinc-700">|</span>
          <a href="/landscape3d" className="text-zinc-500 hover:text-zinc-300">landscape 3D</a>
        </nav>
        <div className="ml-auto flex items-center gap-3 text-xs">
          <label className="flex items-center gap-1">
            scope:
            <select value={scope} onChange={e => setScope(e.target.value as any)}
                    className="bg-ink border border-border rounded px-1 py-0.5">
              <option value="impl">whole-impl</option>
              <option value="line">per-line</option>
            </select>
          </label>
          <label className="flex items-center gap-1">
            grid:
            <select value={grid} onChange={e => setGrid(parseInt(e.target.value))}
                    className="bg-ink border border-border rounded px-1 py-0.5">
              <option value="64">64</option>
              <option value="96">96</option>
              <option value="128">128</option>
              <option value="192">192</option>
            </select>
          </label>
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={showArrows} onChange={e => setShowArrows(e.target.checked)} />
            arrows
          </label>
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={showPoints} onChange={e => setShowPoints(e.target.checked)} />
            points
          </label>
          {loading && <span className="text-zinc-500">loading...</span>}
        </div>
      </header>

      <main className="flex-1 grid grid-cols-[1fr_360px] gap-2 p-2 overflow-hidden">
        <div className="flex flex-col bg-panel border border-border rounded overflow-hidden">
          <div className="px-3 py-2 text-xs border-b border-border flex items-center gap-3">
            <span className="font-semibold">Energy landscape</span>
            <span className="text-zinc-500">
              {field ? `${field.points.length} points · ${field.arrows.length} arrows · bandwidth ${field.bandwidth.toFixed(3)}` : ''}
            </span>
            <span className="ml-auto text-zinc-500">click anywhere to drop a ball · arrows show -∇E</span>
          </div>
          <div ref={panelRef} className="flex-1 relative bg-black">
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
              <div className="absolute bottom-2 left-2 bg-ink/80 border border-border rounded px-2 py-1 text-[10px] flex items-center gap-2">
                <span className="text-zinc-500">low E</span>
                <div className="h-2 w-32 rounded" style={{
                  background: 'linear-gradient(to right, #000004, #350a4f, #781c6d, #bb3754, #ed6925, #fcb519, #fcfdbf)',
                }} />
                <span className="text-zinc-500">high E</span>
                <span className="ml-2 text-zinc-600">{field.energy_min.toFixed(1)} … {field.energy_max.toFixed(1)}</span>
              </div>
            )}
            {trajectory && (
              <div className="absolute top-2 right-2 bg-ink/80 border border-border rounded px-2 py-1 text-[10px]">
                step {trajStep}/{trajectory.length}
                <button
                  onClick={() => { setTrajectory(null); setTrajStep(0); setUserBall(null) }}
                  className="ml-2 text-zinc-400 hover:text-zinc-200"
                >
                  clear
                </button>
              </div>
            )}
          </div>
        </div>

        <aside className="flex flex-col gap-2 overflow-hidden">
          <div className="bg-panel border border-border rounded p-3 text-xs">
            <div className="text-zinc-300 font-semibold mb-1">How to read this</div>
            <div className="text-zinc-500 leading-relaxed">
              The terrain shows <b className="text-zinc-300">E(x, y)</b> — the model's predicted bug-likelihood
              energy across the 2D manifold. <span className="text-zinc-300">Dark valleys</span> = low energy
              (good implementations). <span className="text-zinc-300">Bright peaks</span> = high energy (suspicious).
              Arrows point downhill (−∇E). Click anywhere to drop a ball and watch it descend.
              Red dots are buggy lines (in line scope) or fail impls (in impl scope).
            </div>
          </div>
          <CorruptionLab
            onProject={(xy, energy, label) => {
              setUserBall({ x: xy[0], y: xy[1], energy })
              setTrajectory(null); setTrajStep(0)
              setScoreInfo(`${label} · E=${energy.toFixed(3)}`)
            }}
          />
          {!IS_STATIC_MODE && (
            <LineEditor
              initialSpec={SAMPLE_SPEC}
              initialImpl={SAMPLE_IMPL}
              onScored={handleScored}
            />
          )}
          {scoreInfo && (
            <div className="bg-panel border border-border rounded p-2 text-xs text-zinc-400">
              {scoreInfo}
            </div>
          )}
          {trajectory && (
            <div className="bg-panel border border-border rounded p-2 text-xs">
              <div className="text-zinc-400 mb-1">Trajectory</div>
              <div className="font-mono text-[10px] text-zinc-500">
                start E = {trajectory[0].energy.toFixed(3)}<br />
                end   E = {trajectory[trajectory.length - 1].energy.toFixed(3)}<br />
                Δ = <span className="text-accent">{(trajectory[0].energy - trajectory[trajectory.length - 1].energy).toFixed(3)}</span>
              </div>
            </div>
          )}
        </aside>
      </main>
    </div>
  )
}
