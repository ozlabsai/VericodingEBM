/* LandingRegimeFigure.tsx
 *
 * Marker-leak audit summary as a clean dot plot on a single horizontal axis.
 * The x-axis is the top-1 delta when // FAILS markers are stripped from the
 * input. Tinted background regions encode the three regimes; pins land on
 * the axis with their own labels and values, never overlapping.
 *
 * Pure SVG. The numbers come from the paper:
 *   Hybrid-Averse  -52pp  (our shipped checkpoint, accent color)
 *   EPA-Stack      -47pp  (intermediate)
 *   Frontier LLMs    0pp  (cluster average, neutral)
 *   Sentinel-Reliant +47pp (a failure mode, neg color)
 */
import { useEffect, useRef, useState } from 'react'

type Pin = {
  name: string
  delta: number
  /** Visual treatment:
   *  - 'accent' = shipped checkpoint (periwinkle, prominent)
   *  - 'neg'    = failure regime (red, prominent)
   *  - 'mute'   = neutral comparator (grey, lower emphasis) */
  tone: 'accent' | 'neg' | 'mute'
  /** y-row index (0 = top row of pins, 1 = second row). Used to separate
   *  pins that are within 8pp of each other on the x axis. */
  row: 0 | 1
  /** Optional one-line caption shown directly under the pin name. */
  caption?: string
}

const PINS: Pin[] = [
  { name: 'Hybrid-Averse',     delta: -52, tone: 'accent', row: 0, caption: 'shipped checkpoint' },
  { name: 'EPA-Stack',         delta: -47, tone: 'mute',   row: 1, caption: 'intermediate run' },
  { name: 'Frontier LLMs',     delta:   0, tone: 'mute',   row: 0, caption: 'cluster average' },
  { name: 'Sentinel-Reliant',  delta: +47, tone: 'neg',    row: 0, caption: 'failure regime' },
]

const SCALE_MIN = -60
const SCALE_MAX =  60

function xForDelta(d: number) {
  return ((d - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)) * 100
}

const TICKS = [-60, -40, -20, 0, 20, 40, 60]

// Regime regions: where each region starts/ends on the delta axis.
const REGIONS = [
  { name: 'Marker-Averse',    note: 'signal improves',    from: -60, to:  -6, tint: 'bg-text0/[0.04]' },
  { name: 'Marker-Invariant', note: '±5pp swing',         from:  -6, to:   6, tint: 'bg-text3/[0.06]' },
  { name: 'Marker-Reliant',   note: 'signal collapses',   from:   6, to:  60, tint: 'bg-neg/[0.06]' },
]

const TONE_DOT = {
  accent: 'bg-accent ring-bg0',
  neg:    'bg-neg ring-bg0',
  mute:   'bg-text3 ring-bg0',
} as const

const TONE_TEXT = {
  accent: 'text-accent',
  neg:    'text-neg',
  mute:   'text-text2',
} as const

const TONE_NAME = {
  accent: 'text-text0',
  neg:    'text-text0',
  mute:   'text-text1',
} as const

export default function LandingRegimeFigure() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { setVisible(true); io.disconnect() } })
    }, { threshold: 0.3 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  // Layout constants in px. Two pin rows above the axis line so close-by
  // pins don't collide. Axis sits at AXIS_Y; pins ascend from there.
  const AXIS_Y     = 130
  const ROW_HEIGHT = 38
  const TICK_Y     = AXIS_Y + 6

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="relative" style={{ height: 220 }}>
        {/* Region tints — span the full height behind the chart */}
        <div className="absolute inset-x-0 flex pointer-events-none" style={{ top: 0, bottom: 56 }}>
          {REGIONS.map((r, i) => {
            const left  = xForDelta(r.from)
            const width = xForDelta(r.to) - xForDelta(r.from)
            return (
              <div key={i} className={`absolute h-full ${r.tint}`}
                   style={{ left: `${left}%`, width: `${width}%` }} />
            )
          })}
        </div>

        {/* Region name labels, right-aligned inside each region, top */}
        {REGIONS.map((r, i) => {
          const left  = xForDelta(r.from)
          const width = xForDelta(r.to) - xForDelta(r.from)
          // For the narrow middle region, label sits centered below
          const isNarrow = (r.to - r.from) < 20
          return (
            <div key={i}
                 className={`absolute text-[11px] ${i === 2 ? 'text-neg' : 'text-text3'}`}
                 style={{
                   left:  `${left}%`,
                   width: `${width}%`,
                   top:   isNarrow ? `${AXIS_Y + 30}px` : '6px',
                   textAlign: isNarrow ? 'center' : (i === 0 ? 'left' : 'right'),
                   padding: isNarrow ? '0' : '0 8px',
                 }}>
              <span className="font-medium">{r.name}</span>
              <span className="text-text3 ml-1.5 font-normal">· {r.note}</span>
            </div>
          )
        })}

        {/* The axis line itself */}
        <div className="absolute inset-x-0 h-px bg-line2" style={{ top: `${AXIS_Y}px` }} />

        {/* Tick marks + numeric labels on the axis */}
        {TICKS.map(t => {
          const x = xForDelta(t)
          const isZero = t === 0
          return (
            <div key={t} className="absolute tabular text-[11px] text-text3"
                 style={{ left: `${x}%`, top: `${TICK_Y}px`, transform: 'translateX(-50%)' }}>
              <div className={`w-px mx-auto mb-1 ${isZero ? 'h-2.5 bg-text3' : 'h-1.5 bg-line2'}`} />
              <span className={isZero ? 'text-text2 font-medium' : ''}>
                {t === 0 ? '0' : t > 0 ? `+${t}` : t}
              </span>
            </div>
          )
        })}

        {/* Pins — dot on the axis, stem up, then value + name + caption */}
        {PINS.map((p, idx) => {
          const x = xForDelta(p.delta)
          const pinTop = AXIS_Y - 12 - p.row * ROW_HEIGHT
          return (
            <div key={p.name}
                 className="absolute flex flex-col items-center"
                 style={{
                   left: `${x}%`,
                   top:  `${pinTop - 56}px`,
                   transform: 'translateX(-50%)',
                   transition: 'opacity 700ms cubic-bezier(0.16, 1, 0.3, 1), transform 700ms cubic-bezier(0.16, 1, 0.3, 1)',
                   transitionDelay: `${idx * 120}ms`,
                   opacity: visible ? 1 : 0,
                 }}>
              {/* Name + caption, stacked tightly */}
              <div className={`text-[13px] font-medium whitespace-nowrap ${TONE_NAME[p.tone]}`}>
                {p.name}
              </div>
              {p.caption && (
                <div className="text-[11px] text-text3 whitespace-nowrap mt-0.5">
                  {p.caption}
                </div>
              )}
              {/* Numeric value, weight-emphasized */}
              <div className={`mt-1 tabular text-[14px] font-display tracking-tight font-medium ${TONE_TEXT[p.tone]}`}>
                {p.delta > 0 ? `+${p.delta}` : p.delta}pp
              </div>
              {/* Stem connecting label stack to axis dot */}
              <div className={`w-px mt-1 ${
                p.tone === 'accent' ? 'bg-accent' : p.tone === 'neg' ? 'bg-neg' : 'bg-line2'
              }`} style={{ height: `${20 + p.row * (ROW_HEIGHT - 8)}px` }} />
              {/* Dot on axis */}
              <div className={`w-2.5 h-2.5 rounded-full ring-2 -mt-1 ${TONE_DOT[p.tone]} ${
                p.tone === 'accent' ? 'shadow-[0_0_0_4px_oklch(56%_0.190_268_/_0.15)]' :
                p.tone === 'neg'    ? 'shadow-[0_0_0_4px_oklch(56%_0.190_25_/_0.15)]'  : ''
              }`} />
            </div>
          )
        })}

        {/* Axis caption — left-anchored under the axis, NOT centered under 0 */}
        <div className="absolute inset-x-0 text-[12px] text-text3"
             style={{ top: `${AXIS_Y + 38}px` }}>
          Δ top-1 recall when <code className="text-text2 font-mono text-[11px] bg-bg2 px-1 py-0.5 rounded">// FAILS</code> markers are stripped from FAIL impls
        </div>
      </div>
    </div>
  )
}
