/* LandingCorruptionStrip.tsx
 *
 * A second interactive figure for the landing. Picks one of the corruption
 * examples (default: match_assertOnBool — clearest energy swing) and renders
 * three columns side by side: FAIL with marker / FAIL with marker stripped /
 * PASS sibling. Each column has a tiny per-line energy bar chart. Animates
 * the column emphasis on a loop so the page feels alive.
 *
 * Auto-advances the focused variant every ~3.5s; user click overrides.
 */
import { useEffect, useMemo, useRef, useState } from 'react'

type Variant = {
  label: string
  kind: 'fail_original' | 'fail_marker_stripped' | 'pass_sibling'
  note: string
  impl: string
  per_line_energies: number[]
  whole_impl_energy: number
}

type Example = {
  name: string
  label: string
  spec: string
  variants: Variant[]
}

const DEFAULT_EXAMPLE_NAME = 'match_assertOnBool'

function variantTone(kind: Variant['kind']) {
  if (kind === 'fail_original')        return { dot: 'bg-warm',    text: 'text-warm',     bar: 'bg-warm/70',    barWeak: 'bg-warm/20',    badge: 'FAIL' }
  if (kind === 'fail_marker_stripped') return { dot: 'bg-accent',  text: 'text-accent',   bar: 'bg-accent/65',  barWeak: 'bg-accent/20',  badge: 'STRIPPED' }
  return                                       { dot: 'bg-success', text: 'text-success', bar: 'bg-success/65', barWeak: 'bg-success/20', badge: 'PASS' }
}

function isScorable(s: string) {
  return s.trim().length > 0 && !s.trim().startsWith('//')
}

function PerLineBars({ impl, energies, tone, eGlobalMin, eGlobalMax }: {
  impl: string
  energies: number[]
  tone: ReturnType<typeof variantTone>
  eGlobalMin: number
  eGlobalMax: number
}) {
  const lines = impl.replace(/^\n+|\n+$/g, '').split('\n')
  const scorableIdx: number[] = []
  lines.forEach((l, i) => { if (isScorable(l)) scorableIdx.push(i) })
  const lineToE = new Map<number, number>()
  scorableIdx.forEach((li, k) => { if (k < energies.length) lineToE.set(li, energies[k]) })
  const range = Math.max(1e-6, eGlobalMax - eGlobalMin)
  const topE = Math.max(...energies)

  return (
    <div className="font-mono text-[10px] leading-[1.45]">
      {lines.map((line, i) => {
        const e = lineToE.get(i)
        const has = e !== undefined
        const t = has ? (e! - eGlobalMin) / range : 0
        const isTop = has && e === topE
        return (
          <div key={i} className="flex items-stretch gap-1.5">
            <span className="w-3 text-right text-muted/60 shrink-0">{i + 1}</span>
            <div className={`w-12 shrink-0 relative ${tone.barWeak} rounded-sm overflow-hidden`}>
              {has && (
                <div className={`absolute inset-y-0 left-0 ${isTop ? tone.bar : `${tone.bar} opacity-55`}`}
                     style={{ width: `${Math.max(4, t * 100)}%` }} />
              )}
            </div>
            <span className={`flex-1 truncate whitespace-pre ${isTop ? tone.text : 'text-body/85'}`}>
              {line || ' '}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function LandingCorruptionStrip() {
  const [examples, setExamples] = useState<Example[]>([])
  const [exampleIdx, setExampleIdx] = useState(0)
  const [focusIdx, setFocusIdx] = useState(0)
  const [userInteracted, setUserInteracted] = useState(false)
  const tickRef = useRef<number | null>(null)

  useEffect(() => {
    const base = `${(import.meta as any).env?.BASE_URL ?? '/'}data`.replace(/\/+$/, '')
    fetch(`${base}/corruption_examples.json`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((d: Example[]) => {
        setExamples(d)
        const idx = d.findIndex(e => e.name === DEFAULT_EXAMPLE_NAME)
        if (idx >= 0) setExampleIdx(idx)
      })
      .catch(() => setExamples([]))
  }, [])

  // Auto-advance focus
  useEffect(() => {
    if (userInteracted) return
    if (tickRef.current) clearInterval(tickRef.current)
    const ex = examples[exampleIdx]
    if (!ex) return
    tickRef.current = window.setInterval(() => {
      setFocusIdx(prev => (prev + 1) % ex.variants.length)
    }, 3500)
    return () => { if (tickRef.current) clearInterval(tickRef.current) }
  }, [examples, exampleIdx, userInteracted])

  const ex = examples[exampleIdx]
  const eGlobalRange = useMemo(() => {
    if (!ex) return [0, 1] as [number, number]
    const all = ex.variants.flatMap(v => v.per_line_energies)
    return [Math.min(...all), Math.max(...all)] as [number, number]
  }, [ex])

  if (!ex) {
    return (
      <div className="relative w-full overflow-hidden rounded-xl border border-border bg-ink-2 grain"
           style={{ aspectRatio: '16 / 6', minHeight: 220 }}>
        <div className="absolute inset-0 flex items-center justify-center text-[11px] font-mono text-muted">
          loading variants…
        </div>
      </div>
    )
  }

  const focusedVariant = ex.variants[focusIdx]
  const baseE = ex.variants.find(v => v.kind === 'fail_original')?.whole_impl_energy ?? focusedVariant.whole_impl_energy

  return (
    <div className="relative w-full overflow-hidden rounded-xl border border-border bg-ink-2 grain">
      {/* Top strip: example title + variant chips */}
      <div className="border-b border-border bg-ink/50 backdrop-blur px-4 py-3 flex items-center gap-4 flex-wrap relative z-10">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
          example
        </div>
        <select
          value={exampleIdx}
          onChange={(e) => { setExampleIdx(Number(e.target.value)); setFocusIdx(0); setUserInteracted(true) }}
          className="bg-transparent border border-border rounded text-xs text-fg px-2 py-1 font-mono uppercase tracking-wide hover:border-border-2 transition-colors"
        >
          {examples.map((e, i) => (
            <option key={e.name} value={i} className="bg-ink text-fg normal-case">{e.label}</option>
          ))}
        </select>
        <div className="ml-auto flex items-center gap-1">
          {ex.variants.map((v, i) => {
            const tone = variantTone(v.kind)
            const active = i === focusIdx
            return (
              <button
                key={i}
                onClick={() => { setFocusIdx(i); setUserInteracted(true) }}
                className={`flex items-center gap-1.5 px-2 py-1 rounded font-mono text-[10px] uppercase tracking-[0.14em] border transition-all
                  ${active
                    ? `${tone.text} border-current bg-current/10`
                    : 'text-muted border-border hover:text-body hover:border-border-2'}`}
              >
                <span className={`inline-block w-1.5 h-1.5 rounded-full ${tone.dot}`} />
                {tone.badge}
              </button>
            )
          })}
        </div>
      </div>

      {/* Three columns side by side */}
      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-border relative z-10">
        {ex.variants.map((v, i) => {
          const tone = variantTone(v.kind)
          const active = i === focusIdx
          const delta = v.whole_impl_energy - baseE
          return (
            <button
              key={i}
              onClick={() => { setFocusIdx(i); setUserInteracted(true) }}
              className={`relative text-left p-4 transition-opacity ${active ? 'opacity-100' : 'opacity-50 hover:opacity-80'}`}
            >
              <div className="flex items-baseline gap-2 mb-3">
                <span className={`font-mono text-[10px] uppercase tracking-[0.18em] ${tone.text}`}>{tone.badge}</span>
                <span className="font-mono text-[10px] text-muted">·</span>
                <span className="font-mono text-[10px] text-muted">
                  E = <span className={`tabular-display ${active ? tone.text : 'text-body/80'}`}>{v.whole_impl_energy.toFixed(2)}</span>
                </span>
                {v.kind !== 'fail_original' && Math.abs(delta) > 0.01 && (
                  <span className={`font-mono text-[10px] tabular-display ml-auto ${
                    delta < 0 ? 'text-success' : 'text-warm'
                  }`}>
                    {delta < 0 ? '↓' : '↑'}{Math.abs(delta).toFixed(2)}
                  </span>
                )}
              </div>
              <PerLineBars impl={v.impl} energies={v.per_line_energies} tone={tone}
                           eGlobalMin={eGlobalRange[0]} eGlobalMax={eGlobalRange[1]} />
            </button>
          )
        })}
      </div>

      {/* Bottom row: contextual note for focused variant */}
      <div className="border-t border-border bg-ink/40 px-4 py-3 relative z-10">
        <div className="text-xs text-body/85 max-w-3xl leading-relaxed">
          <span className={`font-mono text-[10px] uppercase tracking-[0.18em] ${variantTone(focusedVariant.kind).text} mr-2`}>
            {variantTone(focusedVariant.kind).badge}
          </span>
          {focusedVariant.note}
        </div>
      </div>
    </div>
  )
}
