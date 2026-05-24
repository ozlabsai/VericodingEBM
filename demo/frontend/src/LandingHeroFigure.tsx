/* LandingHeroFigure.tsx
 *
 * Interactive hero figure for the landing page. Loads the precomputed impl
 * manifold (1492 points colored by whole-impl energy) and renders it as a
 * canvas scatter with a slow drift + breathing radius pulse. The cursor
 * casts a soft halo that reveals nearby impl labels.
 *
 * Goals:
 *   - First-30-seconds proof that this isn't a marketing landing — it's a
 *     real piece of the model's output
 *   - Loads in <300ms (the impls.json is 200KB-ish)
 *   - Pure 2D canvas — no deck.gl bundle in the landing route
 *   - Degrades to a static svg if the data fetch fails (no broken hero)
 */
import { useEffect, useRef, useState } from 'react'
import { interpolateInferno } from 'd3-scale-chromatic'

type ImplPoint = {
  impl_id: string
  status: string
  whole_impl_energy: number
  x: number
  y: number
}

type CanvasSize = { w: number; h: number }

// Inferno colormap matches the demo's ManifoldScatter (d3 interpolateInferno).
// Low energy → near-black indigo; high energy → bright yellow.
function energyToRgb(t: number): [number, number, number] {
  const s = interpolateInferno(Math.max(0, Math.min(1, t)))
  const m = s.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/)
  if (!m) return [128, 128, 128]
  return [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])]
}

export default function LandingHeroFigure() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [points, setPoints] = useState<ImplPoint[] | null>(null)
  const [size, setSize] = useState<CanvasSize>({ w: 1, h: 1 })
  const mouseRef = useRef<{ x: number; y: number; in: boolean }>({ x: 0, y: 0, in: false })
  const [hoverLabel, setHoverLabel] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const base = `${(import.meta as any).env?.BASE_URL ?? '/'}data`.replace(/\/+$/, '')
    fetch(`${base}/impls.json`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((pts: ImplPoint[]) => { setPoints(pts); setLoaded(true) })
      .catch(() => setPoints([]))   // empty => fallback art will render
  }, [])

  useEffect(() => {
    const onResize = () => {
      if (!wrapRef.current) return
      const r = wrapRef.current.getBoundingClientRect()
      setSize({ w: Math.max(1, r.width), h: Math.max(1, r.height) })
    }
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Animation loop
  useEffect(() => {
    if (!points) return
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    canvas.width  = size.w * dpr
    canvas.height = size.h * dpr
    canvas.style.width  = `${size.w}px`
    canvas.style.height = `${size.h}px`
    const ctx = canvas.getContext('2d')!
    ctx.scale(dpr, dpr)

    // Compute bounds + percentile color scale
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
    for (const p of points) {
      if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x
      if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y
    }
    if (!Number.isFinite(minX)) { minX = 0; maxX = 1; minY = 0; maxY = 1 }
    // Pad 4%
    const padX = (maxX - minX) * 0.04 || 0.5
    const padY = (maxY - minY) * 0.04 || 0.5
    minX -= padX; maxX += padX; minY -= padY; maxY += padY

    const energies = points.map(p => p.whole_impl_energy).sort((a, b) => a - b)
    const e05 = energies[Math.floor(energies.length * 0.05)] ?? 0
    const e95 = energies[Math.floor(energies.length * 0.95)] ?? 1
    const eRange = Math.max(1e-6, e95 - e05)

    const toScreen = (x: number, y: number) => [
      ((x - minX) / (maxX - minX)) * size.w,
      // flip y so smaller-y is at bottom
      size.h - ((y - minY) / (maxY - minY)) * size.h,
    ]

    let raf = 0
    const start = performance.now()
    const draw = () => {
      const t = (performance.now() - start) / 1000
      ctx.clearRect(0, 0, size.w, size.h)

      // Background radial wash so the figure has depth even when small
      const g = ctx.createRadialGradient(
        size.w * 0.5, size.h * 0.5, 0,
        size.w * 0.5, size.h * 0.5, Math.max(size.w, size.h) * 0.7,
      )
      g.addColorStop(0, 'rgba(30, 40, 60, 0.45)')
      g.addColorStop(1, 'rgba(14, 18, 24, 0)')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, size.w, size.h)

      // Mouse halo (subtle, just below points)
      const m = mouseRef.current
      if (m.in) {
        const halo = ctx.createRadialGradient(m.x, m.y, 0, m.x, m.y, 120)
        halo.addColorStop(0, 'rgba(255, 200, 120, 0.18)')
        halo.addColorStop(1, 'rgba(255, 200, 120, 0)')
        ctx.fillStyle = halo
        ctx.beginPath()
        ctx.arc(m.x, m.y, 120, 0, Math.PI * 2)
        ctx.fill()
      }

      // Per-point pulse: radius depends on energy + slow sine
      let nearestDist = Infinity
      let nearestPoint: ImplPoint | null = null
      const cursorR2 = 14 * 14

      for (const p of points) {
        const [sx, sy] = toScreen(p.x, p.y)
        // Subtle drift to add life — global rotation around manifold center
        const phase = t * 0.06 + (p.x * 0.11 + p.y * 0.13)
        const dx = Math.cos(phase) * 0.6
        const dy = Math.sin(phase) * 0.6
        const px = sx + dx, py = sy + dy

        const normE = Math.max(0, Math.min(1, (p.whole_impl_energy - e05) / eRange))
        const baseR = 1.2 + normE * 2.4
        const pulse = 1 + 0.10 * Math.sin(t * 1.4 + p.x * 0.7)
        const r = baseR * pulse

        // Cursor highlight
        if (m.in) {
          const ddx = px - m.x, ddy = py - m.y
          const d2 = ddx * ddx + ddy * ddy
          if (d2 < cursorR2 * 4 && d2 < nearestDist) { nearestDist = d2; nearestPoint = p }
        }

        const [r1, g1, b1] = energyToRgb(normE)
        ctx.fillStyle = `rgba(${r1}, ${g1}, ${b1}, ${0.55 + normE * 0.35})`
        ctx.beginPath()
        ctx.arc(px, py, r, 0, Math.PI * 2)
        ctx.fill()
      }

      // Cursor label
      if (nearestPoint && nearestDist < cursorR2 * 4) {
        const [sx, sy] = toScreen(nearestPoint.x, nearestPoint.y)
        ctx.strokeStyle = 'rgba(255, 200, 120, 0.5)'
        ctx.lineWidth = 1
        ctx.beginPath(); ctx.arc(sx, sy, 7, 0, Math.PI * 2); ctx.stroke()
        const label = `${nearestPoint.status.toUpperCase()} · E=${nearestPoint.whole_impl_energy.toFixed(2)}`
        if (label !== hoverLabel) setHoverLabel(label)
      } else if (hoverLabel) {
        setHoverLabel(null)
      }

      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [points, size.w, size.h])

  const handleMouse = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!wrapRef.current) return
    const r = wrapRef.current.getBoundingClientRect()
    mouseRef.current = { x: e.clientX - r.left, y: e.clientY - r.top, in: true }
  }
  const handleLeave = () => { mouseRef.current.in = false; setHoverLabel(null) }

  return (
    <div
      ref={wrapRef}
      onMouseMove={handleMouse}
      onMouseLeave={handleLeave}
      className="relative w-full overflow-hidden rounded-xl border border-line1 bg-bg1"
      style={{ aspectRatio: '16 / 7', minHeight: 220 }}
    >
      <canvas ref={canvasRef} className="absolute inset-0 block" />
      {/* Top-left caption */}
      <div className="absolute top-3 left-3 z-10 flex flex-col gap-0.5 pointer-events-none">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-text3">live · Hybrid-Averse · 1492 impls</div>
        <div className="text-xs font-mono text-text2">UMAP of whole-impl embeddings, colored by energy</div>
      </div>
      {/* Hover readout */}
      <div className="absolute bottom-3 right-3 z-10 font-mono text-[11px] text-text1 bg-bg0/70 border border-line1 rounded px-2 py-1 backdrop-blur transition-opacity duration-200"
           style={{ opacity: hoverLabel ? 1 : 0 }}>
        {hoverLabel ?? '—'}
      </div>
      {/* Legend — matches d3 interpolateInferno used by /manifold */}
      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 text-[10px] font-mono text-text3">
        <span>low&nbsp;E</span>
        <span className="inline-block h-1 w-24 rounded"
              style={{ background: 'linear-gradient(to right, #000004, #1b0c41, #4a0c6b, #781c6d, #a52c60, #cf4446, #ed6925, #fb9b06, #f7d13d, #fcffa4)' }} />
        <span>high&nbsp;E</span>
      </div>
      {/* Loading shimmer */}
      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center text-[11px] font-mono text-text3">
          loading manifold…
        </div>
      )}
    </div>
  )
}
