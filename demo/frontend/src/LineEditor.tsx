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

  const taClass = "bg-bg0 border border-line2 rounded p-2 text-[11px] font-mono text-text1 resize-y focus:outline-none focus:border-text3"
  return (
    <div className="flex flex-col gap-2.5 px-4 py-4">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text1">live editor</span>
        <span className="font-mono text-[10px] text-text3">dynamic mode</span>
      </div>
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3">spec</div>
      <textarea value={spec} onChange={e => setSpec(e.target.value)} rows={4} className={taClass} />
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3">impl</div>
      <textarea value={impl} onChange={e => setImpl(e.target.value)} rows={8} className={taClass} />
      <div className="flex items-center justify-between gap-2">
        <button
          onClick={handleScore} disabled={loading || !impl.trim()}
          className="press px-3 py-2 rounded bg-text0 text-bg0 hover:bg-text1 disabled:opacity-40 disabled:cursor-not-allowed font-mono text-[11px] uppercase tracking-[0.12em]"
        >
          {loading ? 'scoring…' : 'score & project'}
        </button>
        {err && <span className="text-neg font-mono text-[11px]">{err}</span>}
      </div>
    </div>
  )
}
