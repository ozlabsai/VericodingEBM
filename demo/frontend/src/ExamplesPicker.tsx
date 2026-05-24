import { useEffect, useState } from 'react'

export type Example = {
  impl_id: string
  category: 'model_win' | 'model_miss' | 'pass_low_energy'
  label: string
  blurb: string
  stats: Record<string, number>
}

type Props = {
  onPick: (implId: string) => void
  selectedId?: string | null
}

const CATEGORY_STYLE: Record<Example['category'], { label: string; tone: string }> = {
  model_win:       { label: 'Model wins',  tone: 'text-emerald-400' },
  model_miss:      { label: 'Model misses', tone: 'text-rose-400'    },
  pass_low_energy: { label: 'Clean PASS',  tone: 'text-sky-400'     },
}

export default function ExamplesPicker({ onPick, selectedId }: Props) {
  const [examples, setExamples] = useState<Example[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [filter, setFilter] = useState<Example['category'] | 'all'>('all')

  useEffect(() => {
    const base = `${(import.meta as any).env?.BASE_URL ?? '/'}data`.replace(/\/+$/, '')
    fetch(`${base}/examples.json`)
      .then(r => r.ok ? r.json() : Promise.reject(`${r.status}`))
      .then(setExamples)
      .catch(e => setErr(String(e)))
  }, [])

  const filtered = filter === 'all' ? examples : examples.filter(e => e.category === filter)

  if (err) return <div className="text-xs text-rose-400 p-2">examples load error: {err}</div>
  if (examples.length === 0) return null

  return (
    <div className="bg-panel border border-border rounded p-2 flex flex-col gap-2 max-h-[40vh] overflow-hidden">
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
          Curated examples
        </span>
        <span className="text-xs text-zinc-500">click to drill in</span>
      </div>
      <div className="flex gap-1 text-xs">
        {(['all', 'model_win', 'model_miss', 'pass_low_energy'] as const).map(k => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={`px-2 py-0.5 rounded border ${
              filter === k
                ? 'bg-accent/20 border-accent text-accent'
                : 'border-border text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {k === 'all' ? 'all' : CATEGORY_STYLE[k].label}
          </button>
        ))}
      </div>
      <div className="overflow-y-auto flex flex-col gap-1.5">
        {filtered.map(ex => {
          const isSelected = selectedId === ex.impl_id
          const style = CATEGORY_STYLE[ex.category]
          return (
            <button
              key={ex.impl_id}
              onClick={() => onPick(ex.impl_id)}
              className={`text-left p-2 rounded border ${
                isSelected
                  ? 'bg-accent/10 border-accent'
                  : 'border-border hover:border-zinc-600 bg-ink'
              }`}
            >
              <div className="flex items-baseline gap-2 mb-0.5">
                <span className={`text-xs font-medium ${style.tone}`}>{style.label}</span>
                <span className="text-xs text-zinc-500">
                  {ex.stats.n_lines}L
                  {ex.stats.n_buggy ? ` · ${ex.stats.n_buggy} bug${ex.stats.n_buggy > 1 ? 's' : ''}` : ''}
                </span>
              </div>
              <div className="text-xs text-zinc-300 leading-snug">{ex.blurb}</div>
              <div className="text-[10px] text-zinc-600 font-mono mt-0.5 truncate">
                {ex.impl_id}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
