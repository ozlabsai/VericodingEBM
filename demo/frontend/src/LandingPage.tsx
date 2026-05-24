/* LandingPage.tsx — return to the earlier asymmetric editorial composition.
 *
 * Reinstates the first composition that worked:
 *   - Sticky top nav (AppNav)
 *   - Hero: tagline left + live UMAP right (asymmetric split)
 *   - Numbered sections flow below with figures
 * Keeps the recent typography + verdict-badge visibility wins:
 *   - Chillax display + Inter Tight body + JetBrains Mono numbers
 *   - LLM-wins / We-win / Tied / Different-axis as proper badges
 *   - Pure-neutral monochrome chrome (no accent color)
 */
import { useEffect, useRef } from 'react'
import LandingHeroFigure from './LandingHeroFigure'
import HeroPerLineFigure from './HeroPerLineFigure'
import TrainingArcFigure from './TrainingArcFigure'
import LandingRegimeFigure from './LandingRegimeFigure'
import AppNav, { withBase } from './AppNav'

function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(es => {
      es.forEach(e => { if (e.isIntersecting) { el.classList.add('visible'); io.unobserve(el) } })
    }, { threshold: 0.08 })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return ref
}

function Eyebrow({ n, children }: { n: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-2.5 mb-4">
      <span className="font-mono text-[12px] text-text3 tabular">{n}</span>
      <span className="w-6 h-px bg-line2" />
      <span className="text-text2 text-[13px] font-medium">{children}</span>
    </div>
  )
}

// ─── HERO ──────────────────────────────────────────────────────────────
function Hero() {
  const lref = useReveal<HTMLDivElement>()
  const rref = useReveal<HTMLDivElement>()
  return (
    <section className="border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 pt-20 pb-16 grid grid-cols-1 lg:grid-cols-[1.15fr_1fr] gap-12 lg:gap-16 items-start">
        <div ref={lref} className="reveal">
          <div className="flex items-center gap-2 mb-8 text-[12px] text-text3">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-text2" />
            <span>Apart × Atlas SPS Hackathon · Track 3 · Vericoding</span>
          </div>
          <h1 className="font-display text-text0 leading-[1.0] tracking-tight mb-8 text-balance"
              style={{ fontSize: 'clamp(2.4rem, 5.4vw, 4.6rem)', letterSpacing: '-0.035em' }}>
            Where to <em className="italic font-display">look</em> when verification&nbsp;fails.
          </h1>
          <p className="text-text2 text-[17px] leading-[1.55] max-w-xl">
            A 1.5B-parameter discriminative energy-based model that scores each
            line of a Verus implementation with an energy proxy for{' '}
            <span className="text-text0 font-medium">this line is the bug.</span> Trained on
            the Microsoft Verus Training Data; evaluated against six static
            baselines, five frontier LLMs, and in closed-loop CEGIS.
          </p>

          {/* Single primary CTA. Secondaries become text-links — clearly subordinate. */}
          <div className="mt-10 flex flex-wrap items-center gap-x-7 gap-y-3">
            <a href={withBase('/manifold')}
               className="press group inline-flex items-center gap-2 pl-5 pr-4 py-3 rounded-md bg-accent text-white hover:bg-accent-d font-medium text-[15px] shadow-[0_1px_0_0_oklch(40%_0.15_268)]">
              Open the demo
              <svg width="14" height="14" viewBox="0 0 12 12" className="transition-transform duration-200 group-hover:translate-x-0.5"><path d="M3 6h6m-3-3l3 3-3 3" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </a>
            <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf"
               target="_blank" rel="noreferrer"
               className="press text-text1 hover:text-text0 text-[14px] inline-flex items-baseline gap-1.5 border-b border-line2 hover:border-text1 pb-0.5">
              Read the paper
              <span className="text-text3 text-[12px]">19pp</span>
            </a>
            <a href="https://huggingface.co/OzLabs/VericodingEBM"
               target="_blank" rel="noreferrer"
               className="press text-text1 hover:text-text0 text-[14px] border-b border-line2 hover:border-text1 pb-0.5">
              HF weights
            </a>
          </div>

          {/* Inline stat strip — bigger numbers, smaller labels, tightened to feel like one unit */}
          <div className="mt-14 pt-6 border-t border-line1 grid grid-cols-3 gap-8 max-w-lg">
            {[
              { v: '1,492',  u: 'dev-test impls' },
              { v: '17,168', u: 'scorable lines' },
              { v: '4',      u: 'checkpoints' },
            ].map(s => (
              <div key={s.u}>
                <div className="tabular text-text0 text-[28px] leading-none font-display tracking-tight">{s.v}</div>
                <div className="text-text3 text-[12px] mt-2">{s.u}</div>
              </div>
            ))}
          </div>
        </div>

        <div ref={rref} className="reveal lg:pt-4">
          <LandingHeroFigure />
          <div className="mt-4 text-[12px] text-text3 flex items-center gap-3 flex-wrap">
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-text2 animate-pulse" />
              Live · hover the map
            </span>
            <a href={withBase('/manifold')} className="press ml-auto text-text1 hover:text-text0 border-b border-line2 hover:border-text1 pb-0.5">
              Explore the manifold →
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── FINDINGS — summary table with visible verdict badges ──────────────
function FindingsTable() {
  const ref = useReveal<HTMLDivElement>()
  const rows: { metric: string; ours: string; them: string; themL: string; verdict: 'us' | 'them' | 'split' | 'tied' }[] = [
    { metric: 'Per-line top-3',           ours: '0.84',   them: '0.74',  themL: 'Claude Opus 4.7', verdict: 'us'    },
    { metric: 'AUROC vs static baselines',ours: '0.78',   them: '0.67',  themL: 'best non-leak',   verdict: 'us'    },
    { metric: 'Per-line top-1',           ours: '0.56',   them: '0.55',  themL: 'Verus-keyword',   verdict: 'tied'  },
    { metric: 'Whole-impl AUROC',         ours: '0.78',   them: '0.91',  themL: 'GPT-5.5',         verdict: 'them'  },
    { metric: 'CEGIS repair@1 (n=100)',   ours: '25%',    them: '30%',   themL: 'LLM self-judged', verdict: 'them'  },
    { metric: 'Δ markers stripped',       ours: '−52pp',  them: '±5pp',  themL: 'frontier LLMs',   verdict: 'split' },
  ]
  return (
    <section ref={ref} id="findings" className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-10 items-end mb-10">
          <div>
            <Eyebrow n="01">Findings</Eyebrow>
            <h2 className="font-display text-text0 text-3xl md:text-5xl leading-[1.05] tracking-tight">
              Six measurements.<br/>Two we&nbsp;take.
            </h2>
          </div>
          <p className="text-text2 text-[15px] leading-[1.6] max-w-xl">
            Static baselines, frontier LLMs, and closed-loop CEGIS. The 1.5B
            specialist wins per-line localization; LLMs win whole-impl ranking
            and repair. Marker-strip is a different axis entirely.
          </p>
        </div>
        <div className="border-y border-line1">
          {rows.map((r, i) => (
            <div key={i} className={`grid grid-cols-12 gap-4 items-baseline py-5 ${i > 0 ? 'border-t border-line1' : ''}`}>
              <div className="col-span-12 sm:col-span-4 text-text1 text-[15px] font-medium">{r.metric}</div>
              <div className="col-span-4 sm:col-span-2 flex items-baseline gap-2">
                <span className="tabular text-text0 text-[26px] font-display tracking-tight leading-none">{r.ours}</span>
                <span className="text-text3 text-[12px]">ours</span>
              </div>
              <div className="col-span-4 sm:col-span-3 flex items-baseline gap-2">
                <span className="tabular text-text2 text-[20px] leading-none">{r.them}</span>
                <span className="text-text3 text-[12px] truncate">{r.themL}</span>
              </div>
              <div className="col-span-4 sm:col-span-3 text-right">
                {r.verdict === 'us'   && <span className="inline-flex items-center px-2.5 py-1 rounded bg-text0 text-bg0 text-[12px] font-medium">We win</span>}
                {r.verdict === 'them' && <span className="inline-flex items-center px-2.5 py-1 rounded bg-neg text-bg0 text-[12px] font-medium">LLM wins</span>}
                {r.verdict === 'tied' && <span className="inline-flex items-center px-2.5 py-1 rounded border border-line2 text-text2 text-[12px]">Tied</span>}
                {r.verdict === 'split'&& <span className="inline-flex items-center px-2.5 py-1 rounded border border-text2 text-text1 text-[12px] font-medium">Different axis</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── AUDIT ────────────────────────────────────────────────────────────
function AuditSection() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} id="audit" className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-end mb-10">
          <div>
            <Eyebrow n="02">The audit</Eyebrow>
            <h2 className="font-display text-text0 text-3xl md:text-5xl leading-[1.05] tracking-tight">
              Strip the marker.<br/>
              <em className="italic">Watch the energy&nbsp;crash.</em>
            </h2>
          </div>
          <p className="text-text2 text-[15px] leading-[1.6] max-w-xl">
            Every FAIL impl in the dev-test corpus carries a{' '}
            <code className="font-mono text-[0.92em] bg-bg2 text-text1 px-1.5 py-0.5 rounded">// FAILS</code>
            {' '}debug marker that Qwen's pretraining prior couples to verification
            failure. We documented the leak, released the strip-FAILS audit pipeline,
            and ship a fix that overshoots into marker-aversion.
          </p>
        </div>
        <HeroPerLineFigure />
        <div className="mt-14 pt-10 border-t border-line1 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-10 items-start">
          <div>
            <Eyebrow n="Fig 2">Three regimes</Eyebrow>
            <p className="text-text2 text-sm leading-relaxed max-w-xs">
              Same corpus, same audit. The four trained checkpoints and the
              frontier LLM cluster pinned by their measured marker-strip delta.
            </p>
          </div>
          <LandingRegimeFigure />
        </div>
      </div>
    </section>
  )
}

// ─── TRAINING ─────────────────────────────────────────────────────────
function TrainingArcSection() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} id="training" className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-end mb-10">
          <div>
            <Eyebrow n="03">Training arc</Eyebrow>
            <h2 className="font-display text-text0 text-3xl md:text-5xl leading-[1.05] tracking-tight">
              Five runs.<br/>
              <em className="italic">One that survived&nbsp;audit.</em>
            </h2>
          </div>
          <p className="text-text2 text-[15px] leading-[1.6] max-w-xl">
            Run 07 looked great until we audited it. Run 08 over-corrected.
            Run 09 was directionally right. Run 10 is what's served here.
            Hover a point for the verdict and the delivered metrics.
          </p>
        </div>
        <TrainingArcFigure />
      </div>
    </section>
  )
}

// ─── ARTIFACTS ────────────────────────────────────────────────────────
function ArtifactsSection() {
  const ref = useReveal<HTMLDivElement>()
  const items = [
    { tag: '01 · model',   label: 'Discriminative EBM',           body: 'Qwen2.5-Coder-1.5B + LoRA + sentinel-token per-line head + scalar attention-pool head. Trained with within-spec InfoNCE + pairwise hinge + ListNet + semi-hard mining.', href: 'https://huggingface.co/OzLabs/VericodingEBM', text: 'OzLabs/VericodingEBM' },
    { tag: '02 · corpus',  label: 'Line-labelled Verus dev-test', body: '1,492 implementations (609 with FAIL labels and gold buggy-line indices) scraped from verus-lang/verus and hand-checked. Plus 39,440 training pairs.',                  href: 'https://huggingface.co/datasets/OzLabs/VericodingEBM-data', text: 'OzLabs/VericodingEBM-data' },
    { tag: '03 · audit',   label: 'strip-FAILS pipeline',         body: 'A laptop-only audit script that takes two eval-record JSONLs (with markers / stripped) and reports the top-k delta. The pipeline that surfaced the leak.',              href: 'https://github.com/ozlabsai/VericodingEBM/blob/main/scripts/audit_demo.py', text: 'scripts/audit_demo.py' },
    { tag: '04 · cegis',   label: 'closed-loop CEGIS harness',    body: 'Three-arm comparison (specialist-guided / LLM-only / LLM-self-judged) with the real Verus toolchain in the loop, McNemar pairwise tests, on n=100 records.',           href: 'https://github.com/ozlabsai/VericodingEBM/tree/main/artifacts/cegis', text: 'artifacts/cegis/' },
  ]
  return (
    <section ref={ref} id="artifacts" className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-end mb-10">
          <div>
            <Eyebrow n="04">What we release</Eyebrow>
            <h2 className="font-display text-text0 text-3xl md:text-5xl leading-[1.05] tracking-tight">
              Four reusable&nbsp;artifacts.
            </h2>
          </div>
          <p className="text-text2 text-[15px] leading-[1.6] max-w-xl">
            The contribution per §1.4 of the paper. Everything is released —
            model, data, audit, harness, intermediate checkpoints, and every
            LLM-baseline record we generated.
          </p>
        </div>
        <div className="border-y border-line1">
          {items.map((it, i) => (
            <div key={i} className={`grid grid-cols-12 gap-6 items-baseline py-7 ${i > 0 ? 'border-t border-line1' : ''}`}>
              <div className="col-span-12 sm:col-span-2 font-mono text-[12px] text-text3 tabular">
                {it.tag}
              </div>
              <div className="col-span-12 sm:col-span-3">
                <div className="text-text0 text-[17px] font-medium tracking-tight">{it.label}</div>
              </div>
              <div className="col-span-12 sm:col-span-5 text-text2 text-[14px] leading-[1.55]">
                {it.body}
              </div>
              <div className="col-span-12 sm:col-span-2 text-right">
                <a href={it.href} target="_blank" rel="noreferrer"
                   className="press inline-flex items-center font-mono text-[12px] text-text1 hover:text-text0 border-b border-line2 hover:border-text1 pb-0.5">
                  {it.text} →
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── METHOD ───────────────────────────────────────────────────────────
function MethodBlock() {
  const ref = useReveal<HTMLDivElement>()
  const ROWS: { k: string; v: string; mono?: boolean }[] = [
    { k: 'Base',          v: 'Qwen2.5-Coder-1.5B-Instruct' },
    { k: 'Adapter',       v: 'LoRA r=16 α=32, embed-LoRA r=8',  mono: true },
    { k: 'Per-line head', v: 'MLP over sentinel-token hiddens' },
    { k: 'Impl head',     v: 'Scalar attention-pool over impl' },
    { k: 'Loss',          v: 'Within-spec InfoNCE + pairwise hinge + ListNet + semi-hard mining', mono: true },
    { k: 'Training data', v: 'Microsoft Verus Training Data (39k spec/impl pairs)' },
    { k: 'Hardware',      v: '1× A100 SXM 80GB, ~30 min to usable checkpoint' },
    { k: 'Tests',         v: 'McNemar (per-impl), DeLong (AUROC)', mono: true },
  ]
  return (
    <section ref={ref} id="method" className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20 grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-start">
        <div>
          <Eyebrow n="05">Method</Eyebrow>
          <h2 className="font-display text-text0 text-3xl md:text-5xl leading-[1.05] tracking-tight mb-4">
            The stack,<br/>in eight&nbsp;lines.
          </h2>
          <p className="text-text2 text-sm leading-relaxed max-w-sm">
            §2–§3 of the paper. The post-mortem on what didn't work, the
            gradient equations, and the McNemar tables live there.
          </p>
        </div>
        <dl className="border-y border-line1">
          {ROWS.map((r, i) => (
            <div key={i} className={`grid grid-cols-[160px_1fr] gap-6 items-baseline py-4 ${i > 0 ? 'border-t border-line1' : ''}`}>
              <dt className="text-text3 text-[13px]">{r.k}</dt>
              <dd className={`text-text1 text-[15px] ${r.mono ? 'font-mono text-[13px]' : ''}`}>{r.v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}

// ─── CLOSING ──────────────────────────────────────────────────────────
function Closing() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-16 grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-6 items-end">
        <h2 className="font-display text-text0 leading-[1.05] tracking-tight"
            style={{ fontSize: 'clamp(1.8rem, 3.4vw, 2.8rem)' }}>
          The demo runs in your&nbsp;browser.<br/>
          <span className="text-text3 italic">No model load. No&nbsp;backend.</span>
        </h2>
        <a href={withBase('/manifold')}
           className="press group inline-flex items-center gap-2 pl-5 pr-4 py-3 rounded-md bg-accent text-white hover:bg-accent-d font-medium text-[15px] whitespace-nowrap shadow-[0_1px_0_0_oklch(40%_0.15_268)]">
          Open the demo
          <svg width="14" height="14" viewBox="0 0 12 12" className="transition-transform duration-200 group-hover:translate-x-0.5"><path d="M3 6h6m-3-3l3 3-3 3" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </a>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer>
      <div className="max-w-[1400px] mx-auto px-6 py-10 flex flex-wrap items-center gap-x-5 gap-y-3 text-[13px] text-text3">
        <span>MIT</span><span className="text-line2">·</span>
        <span>Guy Nachshon · Oz Labs</span><span className="text-line2">·</span>
        <span>Apart × Atlas SPS Hackathon · Track 3 · May 2026</span>
        <span className="ml-auto flex gap-5">
          <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer" className="press hover:text-text1">GitHub</a>
          <a href="https://huggingface.co/OzLabs/VericodingEBM" target="_blank" rel="noreferrer" className="press hover:text-text1">HF Model</a>
          <a href="https://huggingface.co/datasets/OzLabs/VericodingEBM-data" target="_blank" rel="noreferrer" className="press hover:text-text1">HF Data</a>
        </span>
      </div>
    </footer>
  )
}

export default function LandingPage() {
  return (
    <div className="min-h-[100dvh] bg-bg0">
      <AppNav active="home" />
      <Hero />
      <FindingsTable />
      <AuditSection />
      <TrainingArcSection />
      <ArtifactsSection />
      <MethodBlock />
      <Closing />
      <Footer />
    </div>
  )
}
