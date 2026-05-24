/* TrainingArcFigure.tsx
 *
 * Run-by-run sparkline showing what each training iteration delivered.
 * Two stacked metric tracks: top-3 (cool grey) and AUROC (Lichen accent).
 * Each run is a pinned label on the x-axis. Hovering a pin highlights both
 * tracks and surfaces the one-line summary.
 *
 * Numbers come from the paper. Tracks render as polylines in SVG (no canvas;
 * the figure is small and lightly redrawn).
 */
import { useState, useEffect, useRef } from 'react'

type Run = {
  id: string
  codename: string
  top3: number
  auroc: number
  verdict: 'broke' | 'partial' | 'fixed' | 'shipped'
  note: string
}

// Pulled from the paper. top-3 / AUROC on Verus dev-test (stripped where applicable).
const RUNS: Run[] = [
  { id: '07',  codename: 'Sentinel-Reliant',     top3: 0.93, auroc: 0.55, verdict: 'broke',   note: 'Headline numbers came from the // FAILS marker, not the impl. Audit caught it.' },
  { id: '08',  codename: 'Counterfactual-Mixed', top3: 0.34, auroc: 0.49, verdict: 'broke',   note: 'Mixed-marker augmentation collapsed signal across the board.' },
  { id: '09',  codename: 'Counterfactual-Aug',   top3: 0.76, auroc: 0.51, verdict: 'partial', note: 'Adversarial injection reduced leak but AUROC stayed flat.' },
  { id: '10',  codename: 'Hybrid-Averse',        top3: 0.84, auroc: 0.78, verdict: 'fixed',   note: 'Scalar attention-pool head + hybrid loss. Both tracks recover.' },
  { id: '11b', codename: 'EPA-Stack',            top3: 0.81, auroc: 0.77, verdict: 'shipped', note: 'ListMLE + focal weighting. Same regime, marginally lower top-3.' },
]

const W = 1000
const H = 240
const PAD = { top: 24, right: 80, bottom: 56, left: 56 }
const innerW = W - PAD.left - PAD.right
const innerH = H - PAD.top - PAD.bottom

function xAt(i: number) { return PAD.left + (i / (RUNS.length - 1)) * innerW }
function yAt(v: number) {
  // 0.40 → bottom, 1.00 → top
  const t = (v - 0.40) / 0.60
  return PAD.top + (1 - Math.max(0, Math.min(1, t))) * innerH
}

const verdictTone: Record<Run['verdict'], string> = {
  broke:   'text-neg',
  partial: 'text-text2',
  fixed:   'text-pos',
  shipped: 'text-text2',
}

export default function TrainingArcFigure() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)
  const [visible, setVisible] = useState(false)

  // Reveal on scroll-into-view
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { setVisible(true); io.disconnect() } })
    }, { threshold: 0.25 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  const top3Path = RUNS.map((r, i) => `${i === 0 ? 'M' : 'L'}${xAt(i)},${yAt(r.top3)}`).join(' ')
  const aurocPath = RUNS.map((r, i) => `${i === 0 ? 'M' : 'L'}${xAt(i)},${yAt(r.auroc)}`).join(' ')

  const focus = hoverIdx ?? RUNS.length - 1

  return (
    <div ref={wrapRef} className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block" preserveAspectRatio="xMidYMid meet">
        {/* Y gridlines at 0.5, 0.7, 0.9 */}
        {[0.5, 0.7, 0.9].map(v => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={yAt(v)} y2={yAt(v)}
                  stroke="oklch(86% 0.012 245)" strokeDasharray="2 4" />
            <text x={PAD.left - 8} y={yAt(v)} dy="0.32em" textAnchor="end"
                  fontFamily="JetBrains Mono" fontSize="10" fill="oklch(54% 0.030 245)" className="tabular">{v.toFixed(1)}</text>
          </g>
        ))}

        {/* Track labels */}
        <text x={W - PAD.right + 8} y={yAt(RUNS[RUNS.length - 1].top3)} dy="0.32em"
              fontFamily="JetBrains Mono" fontSize="10" fill="oklch(38% 0.045 245)" className="tabular">top-3</text>
        <text x={W - PAD.right + 8} y={yAt(RUNS[RUNS.length - 1].auroc) + 14} dy="0.32em"
              fontFamily="JetBrains Mono" fontSize="10" fill="oklch(62% 0.150 230)" className="tabular">AUROC</text>

        {/* Lines */}
        <path d={top3Path}
              fill="none"
              stroke="oklch(38% 0.045 245)"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                strokeDasharray: 2000,
                strokeDashoffset: visible ? 0 : 2000,
                transition: 'stroke-dashoffset 1400ms cubic-bezier(0.23, 1, 0.32, 1) 100ms',
              }}/>
        <path d={aurocPath}
              fill="none"
              stroke="oklch(62% 0.150 230)"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                strokeDasharray: 2000,
                strokeDashoffset: visible ? 0 : 2000,
                transition: 'stroke-dashoffset 1400ms cubic-bezier(0.23, 1, 0.32, 1) 300ms',
              }}/>

        {/* Run dots + x labels + hover hitboxes */}
        {RUNS.map((r, i) => {
          const active = hoverIdx === i
          return (
            <g key={r.id}
               onMouseEnter={() => setHoverIdx(i)}
               onMouseLeave={() => setHoverIdx(null)}
               style={{ cursor: 'pointer' }}>
              {/* hover hitbox */}
              <rect x={xAt(i) - 30} y={PAD.top} width={60} height={innerH} fill="transparent" />
              {/* vertical guide on hover */}
              {active && (
                <line x1={xAt(i)} x2={xAt(i)} y1={PAD.top} y2={PAD.top + innerH}
                      stroke="oklch(78% 0.015 245)" strokeWidth="1" />
              )}
              {/* top-3 dot */}
              <circle cx={xAt(i)} cy={yAt(r.top3)} r={active ? 4 : 3}
                      fill="oklch(97% 0.004 245)"
                      stroke="oklch(38% 0.045 245)" strokeWidth="1.5"
                      style={{ transition: 'r 200ms cubic-bezier(0.23,1,0.32,1)' }} />
              {/* AUROC dot */}
              <circle cx={xAt(i)} cy={yAt(r.auroc)} r={active ? 4 : 3}
                      fill="oklch(97% 0.004 245)"
                      stroke="oklch(62% 0.150 230)" strokeWidth="1.5"
                      style={{ transition: 'r 200ms cubic-bezier(0.23,1,0.32,1)' }} />
              {/* x label: run id */}
              <text x={xAt(i)} y={H - PAD.bottom + 18} textAnchor="middle"
                    fontFamily="JetBrains Mono" fontSize="10"
                    fill={active ? 'oklch(15% 0.060 245)' : 'oklch(54% 0.030 245)'}
                    className="tabular">#{r.id}</text>
              {/* codename below */}
              <text x={xAt(i)} y={H - PAD.bottom + 32} textAnchor="middle"
                    fontFamily="Clash Grotesk" fontSize="10" fontWeight="500"
                    fill={active ? 'oklch(22% 0.055 245)' : 'oklch(38% 0.045 245)'}>
                {r.codename}
              </text>
              {/* verdict tag (only for active) */}
              {active && (
                <text x={xAt(i)} y={yAt(r.top3) - 14} textAnchor="middle"
                      fontFamily="JetBrains Mono" fontSize="9"
                      fill="oklch(15% 0.060 245)" className="tabular uppercase">
                  {r.verdict}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* Hover detail card below the chart */}
      <div className="mt-4 grid grid-cols-[120px_1fr_auto] gap-4 items-baseline px-1">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3">run</div>
          <div className="tabular text-text0 text-2xl mt-0.5">#{RUNS[focus].id}</div>
        </div>
        <div>
          <div className="text-text1 text-base">{RUNS[focus].codename}</div>
          <div className="text-text2 text-sm mt-0.5 max-w-2xl leading-snug">{RUNS[focus].note}</div>
        </div>
        <div className={`font-mono text-[10px] uppercase tracking-[0.14em] ${verdictTone[RUNS[focus].verdict]}`}>
          {RUNS[focus].verdict}
        </div>
      </div>
    </div>
  )
}
