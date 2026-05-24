/* LandingRegimeFigure.tsx
 *
 * Marker-leak audit summary as a single horizontal scale. The x-axis is the
 * top-1 delta when // FAILS markers are stripped from the input. Three
 * regimes are labeled along it; the four trained checkpoints + the frontier
 * LLM cluster are pinned at their measured positions.
 *
 * Pure SVG, no data dependency. The numbers below are pulled from the paper
 * (Hybrid-Averse delta -52pp, Sentinel-Reliant +47pp, EPA-Stack -47pp, LLM
 * average ~0pp).
 */
import { useEffect, useRef, useState } from 'react'

type Pin = {
  name: string
  delta: number    // top-1 delta in percentage points
  side: 'top' | 'bottom'
  emphasis?: boolean
  variantClass: string
  /** Tall stem keeps label far from axis; short stem tucks label close. Use
   *  short on a pin that sits near another to avoid horizontal collision. */
  stem?: 'tall' | 'short'
}

const PINS: Pin[] = [
  // Hybrid-Averse and EPA-Stack are only 5pp apart; stagger by stem length
  // so labels don't collide.
  { name: 'Sentinel-Reliant',  delta: +47, side: 'bottom', variantClass: 'text-neg',    emphasis: true,  stem: 'tall'  },
  { name: 'EPA-Stack',         delta: -47, side: 'top',    variantClass: 'text-text1',                   stem: 'short' },
  { name: 'Hybrid-Averse',     delta: -52, side: 'top',    variantClass: 'text-accent', emphasis: true,  stem: 'tall'  },
  { name: 'Frontier LLMs',     delta:   0, side: 'bottom', variantClass: 'text-text2',                   stem: 'tall'  },
]

const SCALE_MIN = -60
const SCALE_MAX =  60

function xForDelta(d: number) {
  return ((d - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)) * 100  // 0..100 in %
}

export default function LandingRegimeFigure() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  // Reveal on scroll-into-view; the pin animation runs once
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { setVisible(true); io.disconnect() } })
    }, { threshold: 0.3 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Three regime labels above the axis */}
      <div className="grid grid-cols-3 gap-2 mb-2 text-center font-mono text-[10px] uppercase tracking-[0.18em]">
        <div className="text-accent">marker-averse<br/><span className="text-text3 normal-case tracking-normal">signal improves when marker stripped</span></div>
        <div className="text-text2">marker-invariant<br/><span className="text-text3 normal-case tracking-normal">±5pp swing</span></div>
        <div className="text-neg">marker-reliant<br/><span className="text-text3 normal-case tracking-normal">signal collapses without marker</span></div>
      </div>

      {/* The axis itself: thick line with regime bands underneath */}
      <div className="relative h-44">
        {/* Regime bands */}
        <div className="absolute inset-x-0 top-[78px] h-2 flex">
          <div className="flex-1 rounded-l bg-accent/15" />
          <div className="w-[40px] bg-text3/10" />
          <div className="flex-1 rounded-r bg-neg/15" />
        </div>
        {/* Center invariant band — narrow strip ±5pp around zero */}
        {(() => {
          const left = xForDelta(-5)
          const right = xForDelta(5)
          return (
            <div className="absolute top-[76px] h-3 bg-text3/15 border-y border-text3/25"
                 style={{ left: `${left}%`, width: `${right - left}%` }} />
          )
        })()}

        {/* Tick marks every 20pp */}
        {[-60, -40, -20, 0, 20, 40, 60].map(t => (
          <div key={t} className="absolute font-mono text-[9px] text-text3 tabular"
               style={{ left: `${xForDelta(t)}%`, top: '92px', transform: 'translateX(-50%)' }}>
            <div className="w-px h-2 bg-line2 mx-auto mb-1" />
            {t === 0 ? '0' : t > 0 ? `+${t}` : t}
          </div>
        ))}
        <div className="absolute font-mono text-[10px] uppercase tracking-[0.18em] text-text3"
             style={{ left: '50%', top: '120px', transform: 'translateX(-50%)' }}>
          Δ top-1 recall when // FAILS markers stripped <span className="normal-case tracking-normal text-text3/70">(percentage points)</span>
        </div>

        {/* Pins */}
        {PINS.map((p) => {
          const left = xForDelta(p.delta)
          const isTop = p.side === 'top'
          const stemHeight = p.stem === 'short' ? 'h-3' : 'h-8'
          const wrapperTop = isTop
            ? (p.stem === 'short' ? '24px' : '0px')   // short → 24px below the top, tall → 0
            : (p.stem === 'short' ? '40px' : '40px')
          return (
            <div key={p.name}
                 className="absolute"
                 style={{
                   left: `${left}%`,
                   top: wrapperTop,
                   transform: 'translateX(-50%)',
                   transition: 'opacity 800ms cubic-bezier(0.16, 1, 0.3, 1), transform 800ms cubic-bezier(0.16, 1, 0.3, 1)',
                   transitionDelay: `${(PINS.indexOf(p)) * 120}ms`,
                   opacity: visible ? 1 : 0,
                 }}>
              {isTop ? (
                <div className="flex flex-col items-center">
                  <div className={`font-mono text-[10px] uppercase tracking-[0.16em] ${p.variantClass} ${p.emphasis ? 'font-medium' : ''} whitespace-nowrap`}>
                    {p.name}
                  </div>
                  <div className={`font-mono text-[10px] tabular ${p.variantClass} mt-0.5`}>
                    {p.delta > 0 ? `+${p.delta}` : p.delta}pp
                  </div>
                  <div className={`w-px ${stemHeight} ${p.variantClass.replace('text-', 'bg-')} mt-1`} />
                  <div className={`w-2 h-2 rounded-full ${p.variantClass.replace('text-', 'bg-')} -mt-1 ring-2 ring-bg0 ${p.emphasis ? 'animate-pulse' : ''}`} />
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <div className={`w-2 h-2 rounded-full ${p.variantClass.replace('text-', 'bg-')} ring-2 ring-bg0 ${p.emphasis ? 'animate-pulse' : ''}`} />
                  <div className={`w-px ${stemHeight} ${p.variantClass.replace('text-', 'bg-')} -mt-1`} />
                  <div className={`font-mono text-[10px] tabular ${p.variantClass} mt-0.5`}>
                    {p.delta > 0 ? `+${p.delta}` : p.delta}pp
                  </div>
                  <div className={`font-mono text-[10px] uppercase tracking-[0.16em] ${p.variantClass} ${p.emphasis ? 'font-medium' : ''} whitespace-nowrap`}>
                    {p.name}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
