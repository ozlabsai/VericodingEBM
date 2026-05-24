/* LandingPage.tsx — pass 3.
 *
 * Design contract:
 *   - Single family: Geist sans + Geist Mono (no editorial italic crutch).
 *   - Committed monochrome OKLCH ramp; ONE accent (Lichen Green), used only
 *     for state, never decoration.
 *   - No section ordinal labels; sections differ by *content shape*.
 *   - Every section earns a real interactive figure or a real stat — never a
 *     row of identical cards.
 *   - Press feedback on every actionable element (Emil rule).
 *   - prefers-reduced-motion honoured globally (utility .reveal).
 */
import { useEffect, useRef } from 'react'
import HeroPerLineFigure from './HeroPerLineFigure'
import TrainingArcFigure from './TrainingArcFigure'
import LandingRegimeFigure from './LandingRegimeFigure'

// ─── Reveal-on-scroll hook ──────────────────────────────────────────────
function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) { el.classList.add('visible'); io.unobserve(el) }
      })
    }, { threshold: 0.12 })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return ref
}

// ─── Top nav ────────────────────────────────────────────────────────────
function Nav() {
  return (
    <header className="sticky top-0 z-30 backdrop-blur-md bg-bg0/75 hairline-b">
      <div className="max-w-[1400px] mx-auto px-6 h-12 flex items-center gap-6">
        <a href="/" className="flex items-baseline gap-2 group">
          <span className="text-text0 text-sm font-medium tracking-crisp">VericodingEBM</span>
          <span className="font-mono text-[10px] tabular text-text3">v1</span>
        </a>
        <nav className="ml-auto flex items-center gap-0.5 font-mono text-[10px] uppercase tracking-[0.14em]">
          <a href="/manifold"    className="press px-2.5 py-1 rounded text-text3 hover:text-text1">manifold</a>
          <a href="/landscape"   className="press px-2.5 py-1 rounded text-text3 hover:text-text1">2d</a>
          <a href="/landscape3d" className="press px-2.5 py-1 rounded text-text3 hover:text-text1">3d</a>
          <span className="px-2 text-line2">·</span>
          <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer"
             className="press px-2.5 py-1 rounded text-text3 hover:text-text1">github</a>
          <a href="https://huggingface.co/OzLabs/VericodingEBM" target="_blank" rel="noreferrer"
             className="press px-2.5 py-1 rounded text-text3 hover:text-text1">model</a>
          <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf" target="_blank" rel="noreferrer"
             className="press px-2.5 py-1 rounded text-text3 hover:text-text1">paper</a>
        </nav>
      </div>
    </header>
  )
}

// ─── HERO ───────────────────────────────────────────────────────────────
function Hero() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section className="border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 pt-20 pb-14 grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-12 lg:gap-16 items-start">
        <div ref={ref} className="reveal">
          <div className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-8">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-pos" />
            Apart × Atlas · SPS hackathon · track 3
          </div>
          <h1 className="text-text0 leading-[0.95] tracking-editorial font-medium mb-6"
              style={{ fontSize: 'clamp(2.6rem, 5.6vw, 4.8rem)' }}>
            A 1.5B model<br/>
            that points at<br/>
            the broken line.
          </h1>
          <p className="text-text2 text-[17px] leading-[1.55] max-w-xl">
            Discriminative energy-based model for Verus vericoding. Scores every
            line of an implementation with an energy proxy for{' '}
            <span className="text-text1">this line is the bug</span>. Trained on 39k spec/impl pairs;
            audited for the obvious shortcut.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-2 font-mono text-[11px]">
            <a href="/manifold"
               className="press inline-flex items-center gap-2 px-4 py-2.5 rounded bg-text0 text-bg0 uppercase tracking-[0.12em] hover:bg-text1">
              open the demo
              <svg width="11" height="11" viewBox="0 0 12 12"><path d="M3 6h6m-3-3l3 3-3 3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </a>
            <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf"
               target="_blank" rel="noreferrer"
               className="press inline-flex items-center px-3.5 py-2.5 rounded border border-line2 text-text2 hover:text-text0 hover:border-text3 uppercase tracking-[0.12em]">
              read the paper
            </a>
            <a href="https://huggingface.co/OzLabs/VericodingEBM"
               target="_blank" rel="noreferrer"
               className="press inline-flex items-center px-3.5 py-2.5 rounded border border-line2 text-text2 hover:text-text0 hover:border-text3 uppercase tracking-[0.12em]">
              hf weights
            </a>
          </div>
        </div>

        <div className="reveal lg:pt-2" ref={useReveal<HTMLDivElement>()}>
          <HeroPerLineFigure />
          <div className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-text3 flex items-center gap-3 flex-wrap">
            <span className="text-pos">● live</span>
            <span className="text-line2">·</span>
            <span>cycles every 4s — hover to pause</span>
            <span className="ml-auto">match_assertOnBool / 6 examples</span>
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── HORIZONTAL STATS STRIP ─────────────────────────────────────────────
function StatsStrip() {
  const stats = [
    { v: '1,492',  l: 'dev-test impls' },
    { v: '17,168', l: 'scorable lines' },
    { v: '39,440', l: 'training pairs' },
    { v: '0.84',   l: 'top-3 recall',   accent: true },
    { v: '0.78',   l: 'whole-impl AUROC' },
    { v: '−52pp',  l: 'Δ stripped top-1', accent: true },
  ]
  return (
    <section className="border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-6 overflow-x-auto no-scrollbar">
        <div className="flex items-baseline gap-12 min-w-max">
          {stats.map((s, i) => (
            <div key={i} className="flex items-baseline gap-2.5">
              <span className={`tabular text-2xl ${s.accent ? 'text-accent' : 'text-text0'}`}>{s.v}</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 whitespace-nowrap">{s.l}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── RESULTS — a horizontal versus-strip, not a sidebar/table ───────────
function ResultsStrip() {
  const ref = useReveal<HTMLDivElement>()
  const rows = [
    { k: 'Per-line top-3 recall',         ours: '0.84',  them: '0.74',  themL: 'Claude Opus 4.7', win: 'us'    },
    { k: 'Whole-impl AUROC',              ours: '0.78',  them: '0.91',  themL: 'GPT-5.5',         win: 'them'  },
    { k: 'CEGIS repair@1 (n=100)',        ours: '25%',   them: '30%',   themL: 'LLM self-judge',  win: 'them'  },
    { k: 'Δ top-1 with markers stripped', ours: '−52pp', them: '±5pp',  themL: 'frontier LLMs',   win: 'split' },
  ]
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="flex items-baseline justify-between mb-10 gap-4 flex-wrap">
          <h2 className="text-text0 font-medium tracking-editorial leading-[1.05]"
              style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.8rem)' }}>
            Four measurements.<br/>
            <span className="text-text3">One we win.</span>
          </h2>
          <p className="text-text3 text-sm max-w-sm">
            Hybrid-Averse (1.5B) versus the strongest LLM on each task.
            The marker-strip column is a different kind of measurement — both regimes are useful.
          </p>
        </div>
        <div className="border-y border-line1">
          {rows.map((r, i) => (
            <div key={i} className={`grid grid-cols-12 gap-4 items-baseline py-5 ${i > 0 ? 'border-t border-line1' : ''}`}>
              <div className="col-span-12 sm:col-span-4 text-text1 text-[15px]">{r.k}</div>
              <div className="col-span-5 sm:col-span-3 flex items-baseline gap-2">
                <span className={`tabular text-4xl ${
                  r.win === 'us' ? 'text-accent' : r.win === 'split' ? 'text-text0' : 'text-text0'
                }`}>{r.ours}</span>
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text3">ours</span>
              </div>
              <div className="col-span-5 sm:col-span-3 flex items-baseline gap-2">
                <span className="tabular text-2xl text-text2">{r.them}</span>
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text3">{r.themL}</span>
              </div>
              <div className="col-span-2 text-right font-mono text-[10px] uppercase tracking-[0.14em]">
                {r.win === 'us'    && <span className="text-accent">specialist</span>}
                {r.win === 'them'  && <span className="text-text3">llm</span>}
                {r.win === 'split' && <span className="text-text1">distinct axis</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── AUDIT — text + regime axis (no Corruption Strip, it lives in hero now)
function AuditRegime() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-end mb-12">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-accent mb-3">
              the audit
            </div>
            <h2 className="text-text0 font-medium tracking-editorial leading-[1.05]"
                style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.8rem)' }}>
              Three regimes,<br/>
              one corpus.
            </h2>
          </div>
          <p className="text-text2 text-[15px] leading-[1.6] max-w-xl">
            Every <span className="text-text0">FAIL</span> impl in the dev-test corpus has a
            <code className="font-mono text-[0.92em] text-accent mx-1">// FAILS</code> debug marker the model can memorise.
            We measured what each checkpoint does when we strip that marker from the input.
            The three regimes plotted below are real model behaviours; pick yours.
          </p>
        </div>
        <LandingRegimeFigure />
      </div>
    </section>
  )
}

// ─── TRAINING ARC — a sparkline, not a table ────────────────────────────
function TrainingArcSection() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-end mb-12">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
              the path here
            </div>
            <h2 className="text-text0 font-medium tracking-editorial leading-[1.05]"
                style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.8rem)' }}>
              Five runs.<br/>
              <span className="text-text3">One that survived audit.</span>
            </h2>
          </div>
          <p className="text-text2 text-[15px] leading-[1.6] max-w-xl">
            Run 07 looked great until we audited it. Run 08 over-corrected. Run 09 was directionally right.
            Run 10 is what's served on every page of this site. Hover a point to see what each run delivered.
          </p>
        </div>
        <TrainingArcFigure />
      </div>
    </section>
  )
}

// ─── METHOD — single concrete diagram-ish block, not a paragraph wall ───
function MethodBlock() {
  const ref = useReveal<HTMLDivElement>()
  const ROWS: { k: string; v: string; mono?: boolean }[] = [
    { k: 'Base',         v: 'Qwen2.5-Coder-1.5B-Instruct' },
    { k: 'Adapter',      v: 'LoRA r=16 α=32, embed-LoRA r=8',  mono: true },
    { k: 'Per-line head', v: 'MLP over sentinel-token hiddens' },
    { k: 'Impl head',     v: 'Scalar attention-pool over impl' },
    { k: 'Loss',         v: 'Logistic pairwise + ListNet + semi-hard mining', mono: true },
    { k: 'Marker fix',   v: 'Counterfactual augmentation (App B)' },
    { k: 'Eval',         v: 'top-k, AUROC, closed-loop CEGIS repair on real Verus' },
    { k: 'Tests',        v: 'McNemar (per-impl), DeLong (AUROC)', mono: true },
  ]
  return (
    <section ref={ref} className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-start">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
              method
            </div>
            <h2 className="text-text0 font-medium tracking-editorial leading-[1.05] mb-4"
                style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.8rem)' }}>
              The stack,<br/>
              in eight lines.
            </h2>
            <p className="text-text2 text-[15px] leading-[1.6] max-w-sm">
              The paper has the gradients, the McNemar tables, and the post-mortems for what
              didn't work. This is the version you can describe to a colleague in 30 seconds.
            </p>
          </div>
          <dl className="border-y border-line1">
            {ROWS.map((r, i) => (
              <div key={i} className={`grid grid-cols-[140px_1fr] gap-6 items-baseline py-3.5 ${i > 0 ? 'border-t border-line1' : ''}`}>
                <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3">{r.k}</dt>
                <dd className={`text-text1 text-[15px] ${r.mono ? 'font-mono' : ''}`}>{r.v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  )
}

// ─── SURFACES — three tall rows, mono right-rail, no card-grid ──────────
function SurfacesSection() {
  const ref = useReveal<HTMLDivElement>()
  const items = [
    { href: '/manifold',    label: 'Manifold',     mono: 'impl × line',  body: 'UMAP of impl and line embeddings, colored by energy. Click a point to drill into source. Six curated corruption examples in the right rail.' },
    { href: '/landscape',   label: 'Landscape 2D', mono: 'E(x,y) heat',  body: 'KNN-interpolated continuous energy field with −∇E arrows. Click anywhere to drop a ball and watch it descend toward a low-energy basin.' },
    { href: '/landscape3d', label: 'Landscape 3D', mono: 'terrain',      body: 'Same field as terrain. Valleys are safe. Peaks are suspicious. The six curated examples pin to the surface as colored spheres.' },
  ]
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <h2 className="text-text0 font-medium tracking-editorial leading-[1.05] mb-10"
            style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.8rem)' }}>
          Three ways into<br/>
          the same energy field.
        </h2>
        <div className="border-y border-line1">
          {items.map((s, i) => (
            <a key={s.href} href={s.href}
               className="press group block py-7 grid grid-cols-12 gap-6 items-baseline border-t border-line1 first:border-t-0 hover:bg-bg1">
              <div className="col-span-12 sm:col-span-3">
                <div className="text-text0 text-2xl tracking-crisp group-hover:text-accent">
                  {s.label}
                </div>
                <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 mt-1">{s.mono}</div>
              </div>
              <div className="col-span-12 sm:col-span-8 text-text2 text-[15px] leading-relaxed max-w-2xl">
                {s.body}
              </div>
              <div className="col-span-12 sm:col-span-1 text-right font-mono text-base text-text3 group-hover:text-accent">→</div>
            </a>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── CLOSING ────────────────────────────────────────────────────────────
function Closing() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20 grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-6 items-end">
        <h2 className="text-text0 font-medium tracking-editorial leading-[1.05]"
            style={{ fontSize: 'clamp(2rem, 4vw, 3.4rem)' }}>
          The demo runs in your browser.<br/>
          <span className="text-text3">No model load. No backend.</span>
        </h2>
        <a href="/manifold"
           className="press inline-flex items-center gap-2 px-5 py-3 rounded bg-text0 text-bg0 font-mono uppercase tracking-[0.12em] text-xs hover:bg-text1 whitespace-nowrap">
          open the demo
          <svg width="11" height="11" viewBox="0 0 12 12"><path d="M3 6h6m-3-3l3 3-3 3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </a>
      </div>
    </section>
  )
}

// ─── FOOTER ─────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer>
      <div className="max-w-[1400px] mx-auto px-6 py-8 flex flex-wrap items-center gap-x-6 gap-y-3 font-mono text-[10px] uppercase tracking-[0.14em] text-text3">
        <span>MIT</span>
        <span className="text-line2">·</span>
        <span>apart × atlas sps hackathon · track 3</span>
        <span className="ml-auto flex gap-4">
          <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer" className="press hover:text-text1">github</a>
          <a href="https://huggingface.co/OzLabs/VericodingEBM" target="_blank" rel="noreferrer" className="press hover:text-text1">hf model</a>
          <a href="https://huggingface.co/datasets/OzLabs/VericodingEBM-data" target="_blank" rel="noreferrer" className="press hover:text-text1">hf data</a>
        </span>
      </div>
    </footer>
  )
}

export default function LandingPage() {
  return (
    <div className="min-h-[100dvh] bg-bg0">
      <Nav />
      <Hero />
      <StatsStrip />
      <ResultsStrip />
      <AuditRegime />
      <TrainingArcSection />
      <MethodBlock />
      <SurfacesSection />
      <Closing />
      <Footer />
    </div>
  )
}
