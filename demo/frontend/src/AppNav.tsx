/* AppNav.tsx — shared header used by every page.
 *
 * Layout rules:
 *   - Single 14px baseline grid. Wordmark, section links, and external links
 *     all sit on one row at the same optical size.
 *   - Section nav (manifold / 2d / 3d) is the primary nav. Treated as
 *     real text, not 10px chrome.
 *   - External resources (github / model / paper) are demoted to a smaller
 *     ghost row on the right — clearly secondary by weight + size.
 *   - The "Where to Look" wordmark earns its own visual weight as the only
 *     non-link element on the left.
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

/** Prefix an internal route with the Vite BASE_URL so links work both at
 *  the dev/HF root (/) and under a GitHub Pages subpath (/VericodingEBM/). */
export function withBase(path: string): string {
  const base = ((import.meta as any).env?.BASE_URL ?? '/').replace(/\/+$/, '')
  if (!path.startsWith('/')) path = '/' + path
  return base + path
}

const ROUTES: { id: Route; href: string; label: string }[] = [
  { id: 'manifold',    href: withBase('/manifold'),    label: 'Manifold' },
  { id: 'landscape',   href: withBase('/landscape'),   label: 'Landscape' },
  { id: 'landscape3d', href: withBase('/landscape3d'), label: '3D' },
]

function ExternalArrow() {
  return (
    <svg width="8" height="8" viewBox="0 0 10 10" className="inline-block ml-1 -translate-y-px opacity-60">
      <path d="M3 7l4-4M7 3v4M7 3H3" stroke="currentColor" strokeWidth="1.2" fill="none" strokeLinecap="round" />
    </svg>
  )
}

export default function AppNav({ active, controls, meta }: Props) {
  return (
    <header className="sticky top-0 z-30 backdrop-blur-md bg-bg0/80 border-b border-line1 shrink-0">
      <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center gap-8">
        {/* Wordmark — single optical weight, no mono sublabel attached */}
        <a href={withBase('/')} className="press flex items-center gap-2.5 group shrink-0">
          <span className="inline-block w-1.5 h-1.5 rounded-sm bg-text0" />
          <span className="text-text0 text-[15px] font-medium tracking-crisp">Where to Look</span>
        </a>

        {/* Primary nav — real text size, sits on the same baseline as the wordmark */}
        <nav className="flex items-center gap-1 text-[14px]">
          {ROUTES.map(r => (
            <a key={r.id}
               href={r.href}
               className={`press px-2.5 py-1.5 rounded-md transition-colors ${
                 active === r.id
                   ? 'text-text0 bg-bg2'
                   : 'text-text2 hover:text-text0 hover:bg-bg1'
               }`}>
              {r.label}
            </a>
          ))}
        </nav>

        {/* Optional inline meta — small, right of nav */}
        {meta && (
          <div className="font-mono text-[11px] text-text3 truncate flex items-baseline gap-2 max-w-[40%]">
            {meta}
          </div>
        )}

        {/* External links — demoted: smaller, lighter, separated from primary nav */}
        <nav className="ml-auto flex items-center gap-3 text-[12px] text-text3">
          <a href={withBase('/')}
             className={`press transition-colors ${active === 'home' ? 'text-text0' : 'hover:text-text1'}`}>
            Home
          </a>
          <span className="w-px h-3 bg-line2" />
          <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer"
             className="press hover:text-text1 transition-colors">GitHub<ExternalArrow /></a>
          <a href="https://huggingface.co/OzLabs/VericodingEBM" target="_blank" rel="noreferrer"
             className="press hover:text-text1 transition-colors">Model<ExternalArrow /></a>
          <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf" target="_blank" rel="noreferrer"
             className="press hover:text-text1 transition-colors">Paper<ExternalArrow /></a>
        </nav>
      </div>

      {/* Optional secondary control band — used by landscape views */}
      {controls && (
        <div className="border-t border-line1 bg-bg1/60">
          <div className="max-w-[1400px] mx-auto px-6 h-10 flex items-center gap-4 font-mono text-[11px] text-text2 overflow-x-auto no-scrollbar">
            {controls}
          </div>
        </div>
      )}
    </header>
  )
}
