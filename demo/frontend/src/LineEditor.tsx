import { useState } from 'react'
import { scoreLine, type ScoreLineResponse } from './api'

type Props = {
  initialSpec: string
  initialImpl: string
  onScored: (resp: ScoreLineResponse, specText: string, implText: string) => void
}

export default function LineEditor({ initialSpec, initialImpl, onScored }: Props) {
  const [spec, setSpec] = useState(initialSpec)
  const [impl, setImpl] = useState(initialImpl)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const handleScore = async () => {
    setLoading(true); setErr(null)
    try {
      const r = await scoreLine(spec, impl)
      onScored(r, spec, impl)
    } catch (e: any) {
      setErr(String(e.message ?? e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-2 p-3 bg-panel border border-border rounded">
      <div className="text-xs text-zinc-400 uppercase tracking-wider">Spec</div>
      <textarea
        value={spec} onChange={e => setSpec(e.target.value)}
        rows={4}
        className="bg-ink border border-border rounded p-2 text-xs font-mono text-zinc-200 resize-y"
      />
      <div className="text-xs text-zinc-400 uppercase tracking-wider">Implementation</div>
      <textarea
        value={impl} onChange={e => setImpl(e.target.value)}
        rows={8}
        className="bg-ink border border-border rounded p-2 text-xs font-mono text-zinc-200 resize-y"
      />
      <div className="flex items-center justify-between gap-2">
        <button
          onClick={handleScore} disabled={loading || !impl.trim()}
          className="px-3 py-1 rounded bg-accent hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium"
        >
          {loading ? 'scoring...' : 'score & project'}
        </button>
        {err && <span className="text-warm text-xs">{err}</span>}
      </div>
    </div>
  )
}
