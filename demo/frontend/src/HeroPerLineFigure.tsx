/* HeroPerLineFigure.tsx
 *
 * The single hero figure: one curated impl rendered as per-line bars,
 * cycling through variants (FAIL → FAIL-stripped → PASS) every 4s.
 *
 * Why this and not a manifold scatter:
 *   - A scatter looks like a matplotlib screenshot.
 *   - A per-line view IS what the model produces; it's the demo's atom.
 *   - Watching the bars rearrange between variants makes the marker-leak
 *     audit legible without any prose explanation.
 *
 * Bars are tagged with their line-text right-of-bar for legibility.
 * Animation: bars retarget value via CSS transitions (interruptible).
 * Bg + frame are flat OKLCH; no glow, no gradient text, no italic.
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

const PREFERRED_EXAMPLE = 'match_assertOnBool'  // shortest, clearest delta
const ROTATE_MS = 4200

function isScorable(s: string) {
  return s.trim().length > 0 && !s.trim().startsWith('//')
}

function kindMeta(k: Variant['kind']) {
  switch (k) {
    case 'fail_original':         return { tag: 'FAIL',          tone: 'text-neg' }
    case 'fail_marker_stripped':  return { tag: 'FAIL stripped', tone: 'text-text1' }
    case 'pass_sibling':          return { tag: 'PASS',          tone: 'text-pos' }
  }
}

export default function HeroPerLineFigure() {
  const [examples, setExamples] = useState<Example[]>([])
  const [exIdx, setExIdx] = useState(0)
  const [vIdx, setVIdx] = useState(0)
  const [userPaused, setUserPaused] = useState(false)
  const tickRef = useRef<number | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const base = `${(import.meta as any).env?.BASE_URL ?? '/'}data`.replace(/\/+$/, '')
    fetch(`${base}/corruption_examples.json`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((d: Example[]) => {
        setExamples(d)
        const i = d.findIndex(e => e.name === PREFERRED_EXAMPLE)
        if (i >= 0) setExIdx(i)
      })
      .catch(() => setExamples([]))
  }, [])

  // Auto-advance variant
  useEffect(() => {
    if (userPaused) return
    const ex = examples[exIdx]
    if (!ex) return
    tickRef.current = window.setInterval(() => {
      setVIdx(prev => (prev + 1) % ex.variants.length)
    }, ROTATE_MS)
    return () => { if (tickRef.current) clearInterval(tickRef.current) }
  }, [examples, exIdx, userPaused])

  const ex = examples[exIdx]

  // Build a unified set of "anchor line texts" so bars retarget the same row
  // across variants when the source code overlaps. We use line indices for now
  // (the variants share most lines), keyed by left-trimmed text.
  const rows = useMemo<{ text: string; isScorable: boolean; perVariant: (number | null)[] }[]>(() => {
    if (!ex) return []
    // Pick the variant with the most lines as the row template
    const longest = ex.variants.reduce((a, b) => b.impl.split('\n').length > a.impl.split('\n').length ? b : a)
    const lines = longest.impl.replace(/^\n+|\n+$/g, '').split('\n')
    const variantLineEnergies = ex.variants.map(v => {
      const ls = v.impl.replace(/^\n+|\n+$/g, '').split('\n')
      const scorIdx: number[] = []
      ls.forEach((l, i) => { if (isScorable(l)) scorIdx.push(i) })
      const map = new Map<string, number>()
      scorIdx.forEach((li, k) => {
        if (k < v.per_line_energies.length) map.set(ls[li].trim(), v.per_line_energies[k])
      })
      return map
    })
    return lines.map(line => ({
      text: line,
      isScorable: isScorable(line),
      perVariant: variantLineEnergies.map(m => m.get(line.trim()) ?? null) as (number | null)[],
    })) as { text: string; isScorable: boolean; perVariant: (number | null)[] }[]
  }, [ex])

  // Compute global E range so bars are comparable across variants
  const [eMin, eMax] = useMemo(() => {
    if (!ex) return [0, 1]
    const all = ex.variants.flatMap(v => v.per_line_energies)
    return [Math.min(...all), Math.max(...all)] as [number, number]
  }, [ex])

  if (!ex) {
    return (
      <div className="w-full rounded-lg bg-bg1 border border-line1" style={{ aspectRatio: '5 / 3', minHeight: 300 }}>
        <div className="h-full flex items-center justify-center font-mono text-xs text-text3">loading…</div>
      </div>
    )
  }

  const focusV = ex.variants[vIdx]
  const meta = kindMeta(focusV.kind)
  const baseE = ex.variants.find(v => v.kind === 'fail_original')?.whole_impl_energy ?? focusV.whole_impl_energy
  const delta = focusV.whole_impl_energy - baseE
  const range = Math.max(1e-6, eMax - eMin)

  return (
    <div ref={wrapRef}
         onMouseEnter={() => setUserPaused(true)}
         onMouseLeave={() => setUserPaused(false)}
         className="relative w-full rounded-lg bg-bg1 border border-line1 overflow-hidden">

      {/* TOP — variant chips + impl picker. Press-feedback on each chip. */}
      <div className="px-5 py-3 flex items-center gap-3 hairline-b">
        <div className="flex items-center gap-1.5">
          {ex.variants.map((v, i) => {
            const m = kindMeta(v.kind)
            const active = i === vIdx
            return (
              <button
                key={i}
                onClick={() => { setVIdx(i); setUserPaused(true) }}
                className={`press inline-flex items-center gap-1.5 px-2.5 py-1 rounded font-mono text-[10px] uppercase tracking-[0.12em] border
                  ${active
                    ? 'border-text1 text-text0 bg-bg2'
                    : 'border-line1 text-text3 hover:text-text2 hover:border-line2'}`}
              >
                <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                  v.kind === 'fail_original' ? 'bg-neg' :
                  v.kind === 'fail_marker_stripped' ? 'bg-text2' :
                  'bg-pos'}`} />
                {m.tag}
              </button>
            )
          })}
        </div>
        <select
          value={exIdx}
          onChange={(e) => { setExIdx(Number(e.target.value)); setVIdx(0); setUserPaused(true) }}
          className="ml-auto bg-transparent border border-line1 hover:border-line2 rounded text-[11px] text-text2 px-2 py-1 font-mono"
        >
          {examples.map((e, i) => (
            <option key={e.name} value={i} className="bg-bg0 text-text1">{e.label}</option>
          ))}
        </select>
      </div>

      {/* MAIN — per-line bars + code.
       * Content-sized (no min-height) — the audit examples are 5-12 lines;
       * forcing a min-height creates the awkward empty band shown in the
       * design review. Stagger reveal so 5-line variants still feel alive. */}
      <div className="px-5 py-5 font-mono text-[12px] leading-[1.65]">
        {rows.map((row, i) => {
          const energy = row.perVariant[vIdx]
          const has = energy !== null && row.isScorable
          const t = has ? (energy! - eMin) / range : 0
          const allFocusVariantEnergies = row.perVariant[vIdx] !== null
            ? ex.variants[vIdx].per_line_energies
            : []
          const topE = allFocusVariantEnergies.length ? Math.max(...allFocusVariantEnergies) : -Infinity
          const isTop = has && energy === topE
          return (
            <div key={i} className="grid grid-cols-[24px_minmax(90px,140px)_1fr] gap-3 items-center py-[1px]">
              <span className="text-right text-text3/70 tabular text-[10px]">{i + 1}</span>
              <div className="relative h-3.5 bg-bg2 rounded-sm overflow-hidden border border-line1">
                {has && (
                  <div
                    className={`absolute inset-y-0 left-0 ${isTop ? 'bg-text0' : 'bg-text2/70'}`}
                    style={{
                      width: `${Math.max(4, t * 100)}%`,
                      transition: 'width 600ms cubic-bezier(0.77, 0, 0.175, 1), background-color 200ms cubic-bezier(0.23, 1, 0.32, 1)',
                    }}
                  />
                )}
                {has && (
                  <span className={`absolute inset-0 flex items-center justify-end pr-1.5 text-[9px] tabular font-medium ${isTop ? 'text-bg0' : 'text-text0'}`}>
                    {energy!.toFixed(2)}
                  </span>
                )}
              </div>
              <span className={`truncate whitespace-pre ${isTop ? 'text-text0 font-medium' : has ? 'text-text2' : 'text-text3/60'}`}>
                {row.text || ' '}
              </span>
            </div>
          )
        })}
      </div>

      {/* BOTTOM — summary + delta */}
      <div className="px-5 py-3 hairline-t flex items-baseline gap-4 flex-wrap">
        <div className="flex items-baseline gap-2">
          <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${meta.tone}`}>{meta.tag}</span>
          <span className="font-mono text-[10px] text-text3">whole-impl E</span>
          <span className="tabular text-text0 text-lg">{focusV.whole_impl_energy.toFixed(2)}</span>
        </div>
        {focusV.kind !== 'fail_original' && Math.abs(delta) > 0.01 && (
          <div className="flex items-baseline gap-1">
            <span className="font-mono text-[10px] text-text3">Δ vs FAIL</span>
            <span className={`tabular text-sm ${delta < 0 ? 'text-pos' : 'text-neg'}`}>
              {delta < 0 ? '↓' : '↑'}{Math.abs(delta).toFixed(2)}
            </span>
          </div>
        )}
        <div className="ml-auto font-mono text-[10px] text-text3 max-w-md text-right leading-snug">
          {focusV.note}
        </div>
      </div>
    </div>
  )
}
