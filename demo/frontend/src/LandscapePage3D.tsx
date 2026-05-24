import { useEffect, useRef, useState } from 'react'
import EnergyLandscape3D, { type Landscape3DExample } from './EnergyLandscape3D'
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
  const [examples, setExamples] = useState<Landscape3DExample[]>([])
  const [highlightedImplId, setHighlightedImplId] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchEnergyField(scope, grid, smoothness)
      .then(f => { setField(f); setLoading(false) })
      .catch(e => { setLoading(false); console.error(e) })
  }, [scope, grid, smoothness])

  useEffect(() => {
    const base = `${(import.meta as any).env?.BASE_URL ?? '/'}data`.replace(/\/+$/, '')
    fetch(`${base}/examples.json`)
      .then(r => r.ok ? r.json() : Promise.reject(`${r.status}`))
      .then((es: Landscape3DExample[]) => setExamples(es))
      .catch(e => console.warn('examples load failed:', e))
  }, [])

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
      <label className="flex items-center gap-1.5">
        <span>smooth</span>
        <input type="range" min={0.5} max={15} step={0.25}
               value={smoothness} onChange={e => setSmoothness(parseFloat(e.target.value))}
               className="w-20 accent-accent" />
        <span className="tabular text-text2 w-7">{smoothness.toFixed(1)}</span>
      </label>
      <label className="flex items-center gap-1.5">
        <span>height</span>
        <input type="range" min={0.1} max={2.0} step={0.05}
               value={heightScale} onChange={e => setHeightScale(parseFloat(e.target.value))}
               className="w-20 accent-accent" />
        <span className="tabular text-text2 w-9">{heightScale.toFixed(2)}</span>
      </label>
      <label className="press flex items-center gap-1.5 cursor-pointer hover:text-text1">
        <input type="checkbox" checked={showPoints} onChange={e => setShowPoints(e.target.checked)} className="accent-accent" />
        <span>points</span>
      </label>
      <label className="press flex items-center gap-1.5 cursor-pointer hover:text-text1">
        <input type="checkbox" checked={showWireframe} onChange={e => setShowWireframe(e.target.checked)} className="accent-accent" />
        <span>wire</span>
      </label>
      {loading && <span className="text-accent ml-auto">loading…</span>}
    </>
  )

  return (
    <div className="h-[100dvh] flex flex-col bg-bg0">
      <AppNav active="landscape3d" controls={controls} />

      <main className="flex-1 grid grid-cols-[1fr_380px] divide-x divide-line1 overflow-hidden">
        <section className="flex flex-col overflow-hidden">
          <div className="hairline-b px-4 py-3 flex items-baseline gap-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text1">3d energy landscape</span>
            <span className="font-mono text-[10px] text-text3">
              {field ? `${field.grid}×${field.grid} · ${field.points.length} pts · bw ${field.bandwidth.toFixed(2)}` : '—'}
            </span>
            <span className="ml-auto font-mono text-[10px] uppercase tracking-[0.14em] text-text3">drag · scroll · right-drag</span>
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
                examples={scope === 'impl' ? examples : undefined}
                highlightedImplId={highlightedImplId}
                onExampleClick={(ex) => setHighlightedImplId(ex.impl_id)}
              />
            )}
            {field && (
              <div className="absolute bottom-3 left-3 bg-bg0/85 backdrop-blur border border-line1 rounded px-2.5 py-1.5 flex items-center gap-2 font-mono text-[10px] text-text3">
                <span>low</span>
                <div className="h-1.5 w-32 rounded-sm" style={{
                  background: 'linear-gradient(to right, #053061, #2166ac, #4393c3, #92c5de, #f7f7f7, #f4a582, #d6604d, #b2182b, #67001f)',
                }} />
                <span>high</span>
                <span className="text-text2 tabular ml-1">{field.energy_min.toFixed(1)} … {field.energy_max.toFixed(1)}</span>
              </div>
            )}
            {trajectory && (
              <div className="absolute top-3 right-3 bg-bg0/85 backdrop-blur border border-line1 rounded px-2.5 py-1.5 font-mono text-[10px] text-text2 flex items-center gap-2">
                <span className="tabular">step {trajStep}/{trajectory.length}</span>
                <button onClick={() => { setTrajectory(null); setTrajStep(0); setUserBall(null) }}
                        className="press text-text3 hover:text-accent uppercase tracking-[0.12em]">clear</button>
              </div>
            )}
          </div>
        </section>

        <aside className="flex flex-col overflow-hidden bg-bg1">
          <div className="flex-1 overflow-y-auto no-scrollbar">
            <div className="px-4 py-4">
              <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 mb-2">how to read</div>
              <p className="text-text2 text-[13px] leading-relaxed">
                Height = predicted energy. Valleys are confident-safe; peaks are suspicious. The
                height slider exaggerates the z-axis when peaks are subtle. The trajectory ball
                follows −∇E exactly.
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
