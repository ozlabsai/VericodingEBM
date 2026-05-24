import { useEffect, useRef, useState } from 'react'
import EnergyLandscape3D from './EnergyLandscape3D'
import LineEditor from './LineEditor'
import { fetchEnergyField, descend, type EnergyField, type ScoreLineResponse, type Trajectory } from './api'

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

export default function LandscapePage3D() {
  const [field, setField] = useState<EnergyField | null>(null)
  const [scope, setScope] = useState<'impl' | 'line'>('impl')
  const [grid, setGrid] = useState(128)
  const [heightScale, setHeightScale] = useState(0.5)
  const [smoothness, setSmoothness] = useState(5.0)   // bandwidth_mul: 0.1=bumpy, 10=smooth
  const [showPoints, setShowPoints] = useState(false)  // hidden by default to match the teaching aesthetic
  const [showWireframe, setShowWireframe] = useState(false)
  const [userBall, setUserBall] = useState<{ x: number; y: number; energy: number } | null>(null)
  const [trajectory, setTrajectory] = useState<Trajectory | null>(null)
  const [trajStep, setTrajStep] = useState(0)
  const [scoreInfo, setScoreInfo] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetchEnergyField(scope, grid, smoothness)
      .then(f => { setField(f); setLoading(false) })
      .catch(e => { setLoading(false); console.error(e) })
  }, [scope, grid, smoothness])

  useEffect(() => {
    if (!trajectory) return
    setTrajStep(0)
    let f = 0
    const id = setInterval(() => {
      f += 1
      setTrajStep(f)
      if (f >= trajectory.length) clearInterval(id)
    }, 60)
    return () => clearInterval(id)
  }, [trajectory])

  const handleScored = async (r: ScoreLineResponse) => {
    const [x, y] = r.whole_impl_xy
    setUserBall({ x, y, energy: r.whole_impl_energy })
    setScoreInfo(`scored: E=${r.whole_impl_energy.toFixed(3)}, projected to (${x.toFixed(2)}, ${y.toFixed(2)})`)
    try {
      const { trajectory: t } = await descend(scope, x, y, 60, 0.5)
      setTrajectory(t)
    } catch (e) { console.error(e) }
  }

  return (
    <div className="h-screen flex flex-col">
      <header className="bg-panel border-b border-border px-4 py-2 flex items-center gap-4">
        <h1 className="text-sm font-semibold tracking-tight">
          EBM <span className="text-zinc-500">energy landscape — 3D (run #10)</span>
        </h1>
        <nav className="flex gap-2 text-xs">
          <a href="/" className="text-zinc-500 hover:text-zinc-300">manifold</a>
          <span className="text-zinc-700">|</span>
          <a href="/landscape" className="text-zinc-500 hover:text-zinc-300">landscape 2D</a>
          <span className="text-zinc-700">|</span>
          <a href="/landscape3d" className="text-accent font-medium">landscape 3D</a>
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
          <label className="flex items-center gap-1">
            smooth:
            <input type="range" min={0.5} max={15} step={0.25}
                   value={smoothness} onChange={e => setSmoothness(parseFloat(e.target.value))}
                   className="w-24" />
            <span className="text-zinc-500 w-8">{smoothness.toFixed(1)}</span>
          </label>
          <label className="flex items-center gap-1">
            height:
            <input type="range" min={0.1} max={2.0} step={0.05}
                   value={heightScale} onChange={e => setHeightScale(parseFloat(e.target.value))}
                   className="w-24" />
            <span className="text-zinc-500 w-8">{heightScale.toFixed(2)}</span>
          </label>
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={showPoints} onChange={e => setShowPoints(e.target.checked)} />
            points
          </label>
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={showWireframe} onChange={e => setShowWireframe(e.target.checked)} />
            wireframe
          </label>
          {loading && <span className="text-zinc-500">loading…</span>}
        </div>
      </header>

      <main className="flex-1 grid grid-cols-[1fr_360px] gap-2 p-2 overflow-hidden">
        <div className="flex flex-col bg-panel border border-border rounded overflow-hidden">
          <div className="px-3 py-2 text-xs border-b border-border flex items-center gap-3">
            <span className="font-semibold">3D energy landscape</span>
            <span className="text-zinc-500">
              {field && `${field.grid}×${field.grid} field · ${field.points.length} pts · bandwidth ${field.bandwidth.toFixed(3)}`}
            </span>
            <span className="ml-auto text-zinc-500">drag to rotate · scroll to zoom · right-drag to pan</span>
          </div>
          <div className="flex-1 relative">
            {field && (
              <EnergyLandscape3D
                field={field}
                userBall={userBall}
                trajectory={trajectory ?? undefined}
                trajectoryStep={trajStep}
                showPoints={showPoints}
                showWireframe={showWireframe}
                heightScale={heightScale}
              />
            )}
            {field && (
              <div className="absolute bottom-2 left-2 bg-ink/80 border border-border rounded px-2 py-1 text-[10px] flex items-center gap-2">
                <span className="text-zinc-500">low E</span>
                <div className="h-2 w-32 rounded" style={{
                  background: 'linear-gradient(to right, #053061, #2166ac, #4393c3, #92c5de, #f7f7f7, #f4a582, #d6604d, #b2182b, #67001f)',
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
                >clear</button>
              </div>
            )}
          </div>
        </div>

        <aside className="flex flex-col gap-2 overflow-hidden">
          <div className="bg-panel border border-border rounded p-3 text-xs">
            <div className="text-zinc-300 font-semibold mb-1">3D energy terrain</div>
            <div className="text-zinc-500 leading-relaxed">
              Height = predicted energy. <span className="text-zinc-300">Valleys</span> are where the model is
              confident the impl is safe; <span className="text-zinc-300">peaks</span> are suspicious regions.
              Paste your code below to drop a ball; the trajectory follows
              −∇E exactly. Use the slider to exaggerate the Z axis when peaks
              are subtle.
            </div>
          </div>
          <LineEditor
            initialSpec={SAMPLE_SPEC}
            initialImpl={SAMPLE_IMPL}
            onScored={handleScored}
          />
          {scoreInfo && (
            <div className="bg-panel border border-border rounded p-2 text-xs text-zinc-400">{scoreInfo}</div>
          )}
          {trajectory && (
            <div className="bg-panel border border-border rounded p-2 text-xs">
              <div className="text-zinc-400 mb-1">Trajectory</div>
              <div className="font-mono text-[10px] text-zinc-500">
                start E = {trajectory[0].energy.toFixed(3)}<br/>
                end   E = {trajectory[trajectory.length - 1].energy.toFixed(3)}<br/>
                Δ = <span className="text-accent">{(trajectory[0].energy - trajectory[trajectory.length - 1].energy).toFixed(3)}</span>
              </div>
            </div>
          )}
        </aside>
      </main>
    </div>
  )
}
