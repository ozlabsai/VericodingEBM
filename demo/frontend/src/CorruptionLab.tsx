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

function VariantBadge({ kind }: { kind: CorruptionVariant['kind'] }) {
  const cfg = {
    fail_original:       { txt: 'FAIL',     cls: 'bg-rose-500/20 text-rose-300 border-rose-500/40' },
    fail_marker_stripped:{ txt: 'FAIL (markers stripped)', cls: 'bg-amber-500/20 text-amber-300 border-amber-500/40' },
    pass_sibling:        { txt: 'PASS',     cls: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' },
  }[kind]
  return (
    <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded border ${cfg.cls}`}>
      {cfg.txt}
    </span>
  )
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
    <div className="text-xs font-mono">
      {lines.map((line, i) => {
        const e = lineToEnergy.get(i)
        const hasBar = e !== undefined
        const t = hasBar ? (e - eMin) / range : 0
        const isTop = i === topLineIdx
        return (
          <div key={i} className="flex gap-1 items-stretch leading-tight">
            <span className="w-7 text-right text-zinc-600 shrink-0">{i + 1}</span>
            <div className="w-14 shrink-0 relative bg-ink/40 rounded overflow-hidden">
              {hasBar && (
                <div
                  className={`absolute inset-y-0 left-0 ${isTop ? 'bg-rose-500/70' : 'bg-sky-500/40'}`}
                  style={{ width: `${Math.max(3, t * 100)}%` }}
                />
              )}
              {hasBar && (
                <span className="absolute inset-0 flex items-center justify-end pr-1 text-[9px] text-zinc-200 tabular-nums">
                  {e!.toFixed(2)}
                </span>
              )}
            </div>
            <span className={`flex-1 whitespace-pre ${isTop ? 'text-rose-200' : 'text-zinc-300'}`}>
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

  if (err) return <div className="text-xs text-rose-400 p-2">corruption examples load error: {err}</div>
  if (!ex || !v) return null

  return (
    <div className="bg-panel border border-border rounded p-2 flex flex-col gap-2 overflow-hidden">
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
          Corruption lab
        </span>
        <span className="text-xs text-zinc-500">precomputed — no backend needed</span>
      </div>

      {/* Example picker */}
      <select
        value={selIdx}
        onChange={(e) => { setSelIdx(Number(e.target.value)); setVariantIdx(0) }}
        className="bg-ink border border-border rounded px-2 py-1 text-xs"
      >
        {examples.map((e, i) => (
          <option key={e.name} value={i}>{e.label}</option>
        ))}
      </select>

      <div className="text-xs text-zinc-400 leading-snug">{ex.blurb}</div>

      {/* Variant chips */}
      <div className="flex flex-wrap gap-1">
        {ex.variants.map((vv, i) => (
          <button
            key={i}
            onClick={() => setVariantIdx(i)}
            className={`flex items-center gap-1 px-2 py-1 rounded border text-xs ${
              variantIdx === i
                ? 'bg-accent/20 border-accent text-accent'
                : 'border-border text-zinc-400 hover:text-zinc-200'
            }`}
            title={vv.note}
          >
            <VariantBadge kind={vv.kind} />
            {variantIdx === i && (
              <span className="tabular-nums text-[10px] text-zinc-300">
                E={vv.whole_impl_energy.toFixed(2)}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="text-xs text-zinc-500 leading-snug italic">{v.note}</div>

      {/* Energy summary */}
      <div className="bg-ink/40 border border-border rounded px-2 py-1 text-xs flex items-baseline gap-3">
        <span className="text-zinc-500">whole-impl E</span>
        <span className="text-zinc-100 font-mono tabular-nums">{v.whole_impl_energy.toFixed(3)}</span>
        {baseEnergy != null && v.kind !== 'fail_original' && (
          <span className={`font-mono tabular-nums text-[10px] ${
            v.whole_impl_energy < baseEnergy ? 'text-emerald-300' : 'text-rose-300'
          }`}>
            {v.whole_impl_energy < baseEnergy ? '↓' : '↑'}
            {Math.abs(v.whole_impl_energy - baseEnergy).toFixed(3)} vs FAIL
          </span>
        )}
      </div>

      {/* Spec + per-line bars (scrollable) */}
      <div className="overflow-y-auto bg-ink/40 rounded border border-border p-2 max-h-[40vh]">
        <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">spec</div>
        <pre className="text-xs font-mono text-zinc-400 whitespace-pre-wrap mb-2">{ex.spec.trim()}</pre>
        <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">impl + per-line energies</div>
        <PerLineBars energies={v.per_line_energies} impl={v.impl} />
      </div>
    </div>
  )
}
