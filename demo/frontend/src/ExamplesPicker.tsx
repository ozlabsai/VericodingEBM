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

const CATEGORY_STYLE: Record<Example['category'], { label: string; tone: string; dot: string }> = {
  model_win:       { label: 'win',  tone: 'text-pos',  dot: 'bg-pos'   },
  model_miss:      { label: 'miss', tone: 'text-neg',  dot: 'bg-neg'   },
  pass_low_energy: { label: 'pass', tone: 'text-text1', dot: 'bg-text2' },
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

  if (err) return <div className="px-4 py-3 font-mono text-[11px] text-neg">examples load error: {err}</div>
  if (examples.length === 0) return null

  return (
    <div className="px-4 py-4 flex flex-col gap-3 max-h-[50vh] overflow-hidden">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text1">curated examples</span>
        <span className="font-mono text-[10px] text-text3">click to drill in</span>
      </div>
      <div className="flex gap-1 font-mono text-[10px] uppercase tracking-[0.12em]">
        {(['all', 'model_win', 'model_miss', 'pass_low_energy'] as const).map(k => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={`press px-2 py-1 rounded border ${
              filter === k
                ? 'border-text1 text-text0 bg-bg2'
                : 'border-line2 text-text3 hover:text-text2 hover:border-text3'
            }`}
          >
            {k === 'all' ? 'all' : CATEGORY_STYLE[k].label}
          </button>
        ))}
      </div>
      <div className="overflow-y-auto no-scrollbar divide-y divide-line1 border-y border-line1">
        {filtered.map(ex => {
          const isSelected = selectedId === ex.impl_id
          const style = CATEGORY_STYLE[ex.category]
          return (
            <button
              key={ex.impl_id}
              onClick={() => onPick(ex.impl_id)}
              className={`press text-left py-2.5 px-1 w-full block transition-colors ${
                isSelected ? 'bg-bg2' : 'hover:bg-bg2/50'
              }`}
            >
              <div className="flex items-baseline gap-2 mb-1">
                <span className={`inline-block w-1.5 h-1.5 rounded-full ${style.dot} translate-y-[2px]`} />
                <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${style.tone}`}>{style.label}</span>
                <span className="font-mono text-[10px] tabular text-text3">
                  {ex.stats.n_lines}L
                  {ex.stats.n_buggy ? ` · ${ex.stats.n_buggy} bug${ex.stats.n_buggy > 1 ? 's' : ''}` : ''}
                </span>
              </div>
              <div className="text-[12px] text-text2 leading-snug">{ex.blurb}</div>
              <div className="text-[10px] text-text3 font-mono mt-1 truncate">{ex.impl_id}</div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
