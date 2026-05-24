/* AppNav.tsx — shared header used by every page (landing + demo views).
 *
 * Identical pattern across the site so the nav doesn't visibly "change"
 * between landing and demo. Only difference: the `active` route is
 * highlighted, and demo views can pass an optional secondary `controls`
 * row that sits below the main nav.
 */
import type { ReactNode } from 'react'

type Route = 'home' | 'manifold' | 'landscape' | 'landscape3d'

type Props = {
  active: Route
  /** Optional secondary row rendered as a sub-band under the main nav.
   *  Used by landscape views for their scope/grid/etc. controls. */
  controls?: ReactNode
  /** Optional small inline meta shown to the right of the section label. */
  meta?: ReactNode
}

const ROUTES: { id: Route; href: string; label: string }[] = [
  { id: 'manifold',    href: '/manifold',    label: 'manifold' },
  { id: 'landscape',   href: '/landscape',   label: '2d' },
  { id: 'landscape3d', href: '/landscape3d', label: '3d' },
]

function ExternalArrow() {
  return <svg width="9" height="9" viewBox="0 0 10 10" className="inline-block ml-1 -translate-y-px"><path d="M3 7l4-4M7 3v4M7 3H3" stroke="currentColor" strokeWidth="1.2" fill="none" strokeLinecap="round" /></svg>
}

export default function AppNav({ active, controls, meta }: Props) {
  return (
    <header className="sticky top-0 z-30 backdrop-blur-md bg-bg0/75 hairline-b shrink-0">
      <div className="max-w-[1400px] mx-auto px-6 h-12 flex items-center gap-6">
        {/* Wordmark + section label */}
        <a href="/" className="press flex items-baseline gap-2 group">
          <span className="text-text0 text-sm font-medium tracking-crisp">Where to Look</span>
          <span className="font-mono text-[10px] tabular text-text3 group-hover:text-text2">
            {active === 'home' ? 'EBM · Verus' : active === 'landscape3d' ? 'landscape 3d' : active === 'landscape' ? 'landscape 2d' : active}
          </span>
        </a>

        {/* Primary nav — section links */}
        <nav className="flex items-center gap-0.5 font-mono text-[10px] uppercase tracking-[0.14em]">
          {ROUTES.map(r => (
            <a key={r.id}
               href={r.href}
               className={`press px-2.5 py-1 rounded ${
                 active === r.id ? 'text-text0' : 'text-text3 hover:text-text1'
               }`}>
              {r.label}
            </a>
          ))}
        </nav>

        {/* Optional inline meta (stats, hover label) */}
        {meta && (
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 truncate flex items-baseline gap-2 max-w-[40%]">
            <span className="text-line2">·</span>
            {meta}
          </div>
        )}

        {/* External links — same set on every page */}
        <nav className="ml-auto flex items-center gap-0.5 font-mono text-[10px] uppercase tracking-[0.14em]">
          <a href="/" className={`press px-2.5 py-1 rounded ${active === 'home' ? 'text-text0' : 'text-text3 hover:text-text1'}`}>home</a>
          <span className="px-1 text-line2">·</span>
          <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer"
             className="press px-2.5 py-1 rounded text-text3 hover:text-text1">github<ExternalArrow /></a>
          <a href="https://huggingface.co/OzLabs/VericodingEBM" target="_blank" rel="noreferrer"
             className="press px-2.5 py-1 rounded text-text3 hover:text-text1">model<ExternalArrow /></a>
          <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf" target="_blank" rel="noreferrer"
             className="press px-2.5 py-1 rounded text-text3 hover:text-text1">paper<ExternalArrow /></a>
        </nav>
      </div>

      {/* Optional secondary control band — used by landscape views */}
      {controls && (
        <div className="hairline-t bg-bg1/50">
          <div className="max-w-[1400px] mx-auto px-6 h-10 flex items-center gap-4 font-mono text-[10px] uppercase tracking-[0.14em] text-text3 overflow-x-auto no-scrollbar">
            {controls}
          </div>
        </div>
      )}
    </header>
  )
}
