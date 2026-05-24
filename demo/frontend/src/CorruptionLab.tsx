/* CorruptionLab.tsx
 *
 * Lets a judge click "what if the bug was fixed?" / "what if I strip the
 * // FAILS marker?" without needing the live backend. All variants are
 * pre-scored at build time (see demo/scripts/build_corruption_examples.py)
 * so this works fully static.
 *
 * Surfaces:
 *   - The spec + impl text for the selected variant
 *   - Per-line energy bars (so judges can see WHICH line the model flags)
 *   - The whole-impl energy, with deltas vs the other variants
 *   - 2D coordinates so the host can highlight the projection on a scatter
 */
import { useEffect, useMemo, useState } from 'react'

export type CorruptionVariant = {
  label: string
  kind: 'fail_original' | 'fail_marker_stripped' | 'pass_sibling'
  note: string
  impl: string
  per_line_energies: number[]
  line_xys: [number, number][]
  whole_impl_energy: number
  whole_impl_xy: [number, number]
}

export type CorruptionExample = {
  name: string
  spec_id: string
  label: string
  blurb: string
  spec: string
  variants: CorruptionVariant[]
}

type Props = {
  onProject?: (xy: [number, number], energy: number, label: string) => void
}

function variantMeta(kind: CorruptionVariant['kind']) {
  switch (kind) {
    case 'fail_original':         return { txt: 'FAIL',          dot: 'bg-neg',  text: 'text-neg'   }
    case 'fail_marker_stripped':  return { txt: 'FAIL stripped', dot: 'bg-text2', text: 'text-text1' }
    case 'pass_sibling':          return { txt: 'PASS',          dot: 'bg-pos',  text: 'text-pos'   }
  }
}

function PerLineBars({ energies, impl }: { energies: number[]; impl: string }) {
  // Pair impl text lines with per-line energies.
  // The backend energies are aligned with *scorable* lines (which include
  // sentinel-token lines, typically non-blank, non-pure-comment lines). For
  // visualisation we match positionally: energies[i] is the i-th scorable
  // line. Show all impl lines, but only render bars on lines that have
  // a corresponding energy.
  const lines = impl.replace(/^\n+|\n+$/g, '').split('\n')
  const isScorable = (s: string) => s.trim().length > 0 && !s.trim().startsWith('//')
  const scorableIndices: number[] = []
  lines.forEach((l, i) => { if (isScorable(l)) scorableIndices.push(i) })
  const lineToEnergy = new Map<number, number>()
  scorableIndices.forEach((li, k) => { if (k < energies.length) lineToEnergy.set(li, energies[k]) })

  const eMin = Math.min(...energies)
  const eMax = Math.max(...energies)
  const range = Math.max(1e-6, eMax - eMin)
  const topLineIdx = scorableIndices[energies.indexOf(eMax)]

  return (
    <div className="font-mono text-[11px] leading-[1.55]">
      {lines.map((line, i) => {
        const e = lineToEnergy.get(i)
        const hasBar = e !== undefined
        const t = hasBar ? (e - eMin) / range : 0
        const isTop = i === topLineIdx
        return (
          <div key={i} className="grid grid-cols-[20px_56px_1fr] gap-1.5 items-baseline">
            <span className="text-right text-text3/60 tabular text-[10px]">{i + 1}</span>
            <div className="relative h-3 bg-bg2 rounded-sm overflow-hidden">
              {hasBar && (
                <div
                  className={`absolute inset-y-0 left-0 ${isTop ? 'bg-accent' : 'bg-text3/40'}`}
                  style={{ width: `${Math.max(3, t * 100)}%`, transition: 'width 400ms cubic-bezier(0.23, 1, 0.32, 1)' }}
                />
              )}
              {hasBar && (
                <span className="absolute inset-0 flex items-center justify-end pr-1 text-[9px] text-text1 tabular">
                  {e!.toFixed(2)}
                </span>
              )}
            </div>
            <span className={`whitespace-pre truncate ${isTop ? 'text-text0' : hasBar ? 'text-text2' : 'text-text3/60'}`}>
              {line || ' '}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function CorruptionLab({ onProject }: Props) {
  const [examples, setExamples] = useState<CorruptionExample[]>([])
  const [selIdx, setSelIdx] = useState(0)
  const [variantIdx, setVariantIdx] = useState(0)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    const base = `${(import.meta as any).env?.BASE_URL ?? '/'}data`.replace(/\/+$/, '')
    fetch(`${base}/corruption_examples.json`)
      .then(r => r.ok ? r.json() : Promise.reject(`${r.status}`))
      .then(setExamples)
      .catch(e => setErr(String(e)))
  }, [])

  const ex = examples[selIdx]
  const v = ex?.variants[variantIdx]

  // When the user changes example/variant, notify the parent so it can move
  // a highlight marker on the impl manifold.
  useEffect(() => {
    if (v && onProject) {
      onProject(v.whole_impl_xy, v.whole_impl_energy, `${ex.label} — ${v.label}`)
    }
  }, [v?.whole_impl_xy[0], v?.whole_impl_xy[1]])

  const baseEnergy = useMemo(() => {
    // The "anchor" we compute deltas against = original FAIL variant
    if (!ex) return undefined
    const orig = ex.variants.find(x => x.kind === 'fail_original')
    return orig?.whole_impl_energy
  }, [ex])

  if (err) return <div className="px-4 py-3 font-mono text-[11px] text-neg">corruption load error: {err}</div>
  if (!ex || !v) return null
  const vMeta = variantMeta(v.kind)

  return (
    <div className="px-4 py-4 flex flex-col gap-3">
      {/* Heading row */}
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text1">corruption lab</span>
        <span className="font-mono text-[10px] text-text3">precomputed</span>
      </div>

      {/* Example picker */}
      <select
        value={selIdx}
        onChange={(e) => { setSelIdx(Number(e.target.value)); setVariantIdx(0) }}
        className="press bg-bg0 border border-line2 hover:border-text3 rounded px-2 py-1.5 text-[12px] text-text1"
      >
        {examples.map((e, i) => (
          <option key={e.name} value={i}>{e.label}</option>
        ))}
      </select>

      <p className="text-[12px] text-text2 leading-snug">{ex.blurb}</p>

      {/* Variant chips */}
      <div className="flex flex-wrap gap-1">
        {ex.variants.map((vv, i) => {
          const m = variantMeta(vv.kind)
          const active = variantIdx === i
          return (
            <button
              key={i}
              onClick={() => setVariantIdx(i)}
              className={`press flex items-center gap-1.5 px-2 py-1 rounded border font-mono text-[10px] uppercase tracking-[0.12em] ${
                active
                  ? 'border-text1 text-text0 bg-bg2'
                  : 'border-line2 text-text3 hover:text-text2 hover:border-text3'
              }`}
              title={vv.note}
            >
              <span className={`inline-block w-1.5 h-1.5 rounded-full ${m.dot}`} />
              {m.txt}
              {active && (
                <span className="tabular text-text2 normal-case tracking-normal">
                  E {vv.whole_impl_energy.toFixed(2)}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <p className="text-[12px] text-text3 leading-snug">{v.note}</p>

      {/* Energy summary — flat, hairline-divided, no card */}
      <div className="hairline-t hairline-b py-2 flex items-baseline gap-3 font-mono">
        <span className="text-[10px] uppercase tracking-[0.14em] text-text3">whole-impl E</span>
        <span className="tabular text-text0 text-lg">{v.whole_impl_energy.toFixed(3)}</span>
        {baseEnergy != null && v.kind !== 'fail_original' && (
          <span className={`tabular text-[11px] ${
            v.whole_impl_energy < baseEnergy ? 'text-pos' : 'text-neg'
          }`}>
            {v.whole_impl_energy < baseEnergy ? '↓' : '↑'}
            {Math.abs(v.whole_impl_energy - baseEnergy).toFixed(2)}
          </span>
        )}
        <span className={`ml-auto text-[10px] uppercase tracking-[0.14em] ${vMeta.text}`}>{vMeta.txt}</span>
      </div>

      {/* Spec + per-line bars */}
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 mb-1.5">spec</div>
        <pre className="text-[11px] font-mono text-text2 whitespace-pre-wrap mb-3 bg-bg0 rounded border border-line1 p-2 max-h-32 overflow-y-auto no-scrollbar">{ex.spec.trim()}</pre>
        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 mb-1.5">impl · per-line E</div>
        <div className="bg-bg0 rounded border border-line1 p-2 max-h-[40vh] overflow-y-auto no-scrollbar">
          <PerLineBars energies={v.per_line_energies} impl={v.impl} />
        </div>
      </div>
    </div>
  )
}
