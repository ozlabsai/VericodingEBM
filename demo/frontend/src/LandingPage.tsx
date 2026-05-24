/* LandingPage.tsx — composition rebuild.
 *
 * Establishes clear hierarchy:
 *   1. Hero (one screen): tagline + the big 0.84 + CTA. Nothing else.
 *   2. Summary table: at-a-glance what's here, what won, what lost.
 *   3. Figures section: UMAP / audit / training arc, each anchored with its
 *      own caption and breathing room.
 *   4. Artifacts + method: secondary content, dense, paper-like.
 *
 * Chillax (display) + Inter Tight (body) + JetBrains Mono (numbers).
 * Slim top nav, no sidebar.
 */
import { useEffect, useRef } from 'react'
import LandingHeroFigure from './LandingHeroFigure'
import HeroPerLineFigure from './HeroPerLineFigure'
import TrainingArcFigure from './TrainingArcFigure'
import LandingRegimeFigure from './LandingRegimeFigure'

function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(es => {
      es.forEach(e => { if (e.isIntersecting) { el.classList.add('visible'); io.unobserve(el) } })
    }, { threshold: 0.05 })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return ref
}

function TopNav() {
  return (
    <header className="sticky top-0 z-30 bg-bg0/85 backdrop-blur hairline-b">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 h-14 flex items-center gap-8">
        <a href="/" className="font-display text-text0 text-[15px] tracking-tight font-medium">
          Where to Look
        </a>
        <nav className="hidden md:flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.14em]">
          <a href="#findings"  className="press px-2 py-1 text-text2 hover:text-text0">findings</a>
          <a href="#audit"     className="press px-2 py-1 text-text2 hover:text-text0">audit</a>
          <a href="#training"  className="press px-2 py-1 text-text2 hover:text-text0">training</a>
          <a href="#artifacts" className="press px-2 py-1 text-text2 hover:text-text0">artifacts</a>
          <a href="#method"    className="press px-2 py-1 text-text2 hover:text-text0">method</a>
        </nav>
        <div className="ml-auto flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em]">
          <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf" target="_blank" rel="noreferrer"
             className="press hidden sm:inline px-2 py-1 text-text2 hover:text-text0">paper</a>
          <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer"
             className="press hidden sm:inline px-2 py-1 text-text2 hover:text-text0">github</a>
          <a href="/manifold"
             className="press inline-flex items-center gap-1.5 ml-2 px-3 py-1.5 rounded bg-text0 text-bg0 hover:bg-text1">
            <span>Open the demo</span>
            <span>→</span>
          </a>
        </div>
      </div>
    </header>
  )
}

// ─── HERO — one screen, single focal point ────────────────────────────
function Hero() {
  return (
    <section className="border-b border-line1">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 min-h-[calc(100vh-3.5rem)] flex flex-col justify-center py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-10 lg:gap-20 items-center">
          {/* LEFT — the headline + CTA */}
          <div>
            <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-text3 mb-6">
              Apart × Atlas · SPS Hackathon · Track 3 · Vericoding
            </div>
            <h1 className="font-display text-text0 leading-[0.95] tracking-tight mb-8"
                style={{ fontSize: 'clamp(2.4rem, 5vw, 4.4rem)', letterSpacing: '-0.03em' }}>
              A 1.5B specialist that points at the broken line of a Verus impl.
            </h1>
            <p className="text-text2 text-[17px] leading-[1.6] max-w-xl mb-10">
              Discriminative energy-based model. Qwen2.5-Coder-1.5B + LoRA.
              Trained on the Microsoft Verus Training Data; evaluated against
              six static baselines, five frontier LLMs, and in closed-loop CEGIS
              with the Verus toolchain in the loop.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <a href="/manifold"
                 className="press inline-flex items-center gap-2 px-5 py-3 rounded bg-text0 text-bg0 hover:bg-text1 font-medium text-[15px]">
                Open the demo
                <svg width="14" height="14" viewBox="0 0 12 12"><path d="M3 6h6m-3-3l3 3-3 3" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </a>
              <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf"
                 target="_blank" rel="noreferrer"
                 className="press inline-flex items-center gap-1.5 px-4 py-3 rounded border border-line2 text-text1 hover:border-text2 hover:bg-bg1 text-[15px]">
                Read the paper
                <span className="font-mono text-[11px] text-text3">23pp</span>
              </a>
            </div>
          </div>

          {/* RIGHT — the headline number, big */}
          <div className="lg:border-l lg:border-line1 lg:pl-12">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
              Headline · per-line top-3 recall
            </div>
            <div className="font-display text-text0 leading-none mb-4"
                 style={{ fontSize: 'clamp(7rem, 18vw, 14rem)', letterSpacing: '-0.06em' }}>
              0.84
            </div>
            <div className="text-text2 text-[15px] leading-[1.55] max-w-sm">
              On <span className="tabular">609</span> failing Verus dev-test impls.
              Beats every frontier LLM (Claude Opus 4.7: <span className="tabular text-text1">0.74</span>).
              The one measurement the 1.5B specialist takes.
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── FINDINGS — at-a-glance summary table ──────────────────────────────
function FindingsTable() {
  const ref = useReveal<HTMLDivElement>()
  const rows: { metric: string; ours: string; them: string; themL: string; verdict: 'us' | 'them' | 'split' | 'tied' }[] = [
    { metric: 'Per-line top-3',         ours: '0.84',   them: '0.74',  themL: 'Claude Opus 4.7',     verdict: 'us'    },
    { metric: 'AUROC vs static baselines', ours: '0.78', them: '0.67',  themL: 'best non-leak',       verdict: 'us'    },
    { metric: 'Per-line top-1',         ours: '0.56',   them: '0.55',  themL: 'Verus-keyword',       verdict: 'tied'  },
    { metric: 'Whole-impl AUROC',       ours: '0.78',   them: '0.91',  themL: 'GPT-5.5',             verdict: 'them'  },
    { metric: 'CEGIS repair@1 (n=100)', ours: '25%',    them: '30%',   themL: 'LLM self-judged',     verdict: 'them'  },
    { metric: 'Δ markers stripped',     ours: '−52pp',  them: '±5pp',  themL: 'frontier LLMs',       verdict: 'split' },
  ]
  return (
    <section ref={ref} id="findings" className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-20">
        <div className="flex items-end justify-between gap-8 flex-wrap mb-10">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
              02 · Findings
            </div>
            <h2 className="font-display text-text0 text-3xl md:text-5xl leading-[1.05] tracking-tight">
              Six measurements. Two we take.
            </h2>
          </div>
          <p className="text-text2 text-[14px] leading-[1.6] max-w-md">
            Static baselines, frontier LLMs, and closed-loop CEGIS. The 1.5B
            specialist wins per-line localization. LLMs win whole-impl ranking
            and repair. Marker-strip is a different axis.
          </p>
        </div>
        <div className="border-y border-line1">
          {rows.map((r, i) => (
            <div key={i} className={`grid grid-cols-12 gap-4 items-baseline py-5 ${i > 0 ? 'border-t border-line1' : ''}`}>
              <div className="col-span-12 sm:col-span-4 text-text1 text-[15px]">{r.metric}</div>
              <div className="col-span-4 sm:col-span-2 flex items-baseline gap-2">
                <span className="tabular text-text0 text-2xl">{r.ours}</span>
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text3">ours</span>
              </div>
              <div className="col-span-4 sm:col-span-3 flex items-baseline gap-2">
                <span className="tabular text-text2 text-xl">{r.them}</span>
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text3 truncate">{r.themL}</span>
              </div>
              <div className="col-span-4 sm:col-span-3 text-right">
                {r.verdict === 'us'   && <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-text0 text-bg0 font-mono text-[10px] uppercase tracking-[0.12em]">We win</span>}
                {r.verdict === 'them' && <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-neg text-bg0 font-mono text-[10px] uppercase tracking-[0.12em]">LLM wins</span>}
                {r.verdict === 'tied' && <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-line2 text-text2 font-mono text-[10px] uppercase tracking-[0.12em]">Tied</span>}
                {r.verdict === 'split'&& <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-text2 text-text1 font-mono text-[10px] uppercase tracking-[0.12em]">Different axis</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── FIGURE — UMAP (full bleed within container) ──────────────────────
function UmapFigure() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-16">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
          Fig 1 · UMAP of impl embeddings · 1,492 impls · colored by energy
        </div>
        <LandingHeroFigure />
        <p className="font-mono text-[10px] text-text3 mt-3">
          <a href="/manifold" className="press hover:text-text1 underline underline-offset-2">explore the full manifold →</a>
        </p>
      </div>
    </section>
  )
}

// ─── AUDIT ────────────────────────────────────────────────────────────
function AuditSection() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} id="audit" className="reveal border-b border-line1">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-20">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
          03 · The audit
        </div>
        <h2 className="font-display text-text0 text-3xl md:text-5xl leading-[1.05] tracking-tight mb-5 max-w-3xl">
          Strip the marker. Watch the energy crash.
        </h2>
        <p className="text-text2 text-[15px] leading-[1.65] max-w-2xl mb-12">
          Every FAIL impl in the dev-test corpus carries a{' '}
          <code className="font-mono text-[0.92em] bg-bg2 text-text1 px-1.5 py-0.5 rounded">// FAILS</code>
          {' '}debug marker that Qwen's pretraining prior couples to verification
          failure. We documented the leak, released the strip-FAILS audit pipeline,
          and ship a fix that overshoots into marker-aversion.
        </p>
        <HeroPerLineFigure />
        <div className="mt-12 pt-10 border-t border-line1">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
            Fig 2 · three regimes · pinned by measured Δ top-1
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
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-20">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
          04 · Training arc
        </div>
        <h2 className="font-display text-text0 text-3xl md:text-5xl leading-[1.05] tracking-tight mb-5 max-w-3xl">
          Five runs. One that survived audit.
        </h2>
        <p className="text-text2 text-[15px] leading-[1.65] max-w-2xl mb-12">
          Run 07 looked great until we audited it. Run 08 over-corrected. Run 09
          was directionally right. Run 10 is what's served here. Hover a point
          for the verdict and the delivered metrics.
        </p>
        <TrainingArcFigure />
      </div>
    </section>
  )
}

// ─── ARTIFACTS ────────────────────────────────────────────────────────
function ArtifactsSection() {
  const ref = useReveal<HTMLDivElement>()
  const items = [
    { n: 'i',   t: 'Discriminative EBM',              d: 'Qwen2.5-Coder-1.5B + LoRA + sentinel-token per-line head + scalar attention-pool head. Trained with within-spec InfoNCE + pairwise hinge + ListNet + semi-hard mining.', href: 'https://huggingface.co/OzLabs/VericodingEBM', linkLabel: 'HF model →' },
    { n: 'ii',  t: 'Line-labelled Verus dev-test',    d: '1,492 implementations (609 with FAIL labels and gold buggy-line indices) scraped from verus-lang/verus. Plus 39,440 training pairs.',                                  href: 'https://huggingface.co/datasets/OzLabs/VericodingEBM-data', linkLabel: 'HF dataset →' },
    { n: 'iii', t: 'strip-FAILS audit pipeline',      d: 'Laptop-only audit script. Reports top-k delta between markered and stripped runs. The pipeline that surfaced the leak.',                                                href: 'https://github.com/ozlabsai/VericodingEBM/blob/main/scripts/audit_demo.py', linkLabel: 'audit_demo.py →' },
    { n: 'iv',  t: 'closed-loop CEGIS harness',       d: 'Three-arm comparison (specialist-guided / LLM-only / LLM-self-judged) with the real Verus toolchain in the loop, McNemar pairwise tests, n=100.',                       href: 'https://github.com/ozlabsai/VericodingEBM/tree/main/artifacts/cegis', linkLabel: 'artifacts/cegis/ →' },
  ]
  return (
    <section ref={ref} id="artifacts" className="reveal border-b border-line1">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-20">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
          05 · What we release
        </div>
        <h2 className="font-display text-text0 text-3xl md:text-5xl leading-[1.05] tracking-tight mb-12">
          Four artifacts.
        </h2>
        <ol className="border-y border-line1 max-w-3xl">
          {items.map((it, i) => (
            <li key={it.n} className={`grid grid-cols-[36px_1fr] gap-4 items-baseline py-6 ${i > 0 ? 'border-t border-line1' : ''}`}>
              <span className="font-mono text-[11px] tabular text-text3 italic">{it.n}.</span>
              <div>
                <div className="text-text0 text-lg tracking-tight mb-1.5">{it.t}</div>
                <p className="text-text2 text-[14px] leading-relaxed mb-2 max-w-2xl">{it.d}</p>
                <a href={it.href} target="_blank" rel="noreferrer"
                   className="press font-mono text-[11px] text-text1 hover:text-text0 underline underline-offset-2">
                  {it.linkLabel}
                </a>
              </div>
            </li>
          ))}
        </ol>
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
    { k: 'Hardware',      v: '1× A100 SXM 80GB, ~30 min wall-clock to usable checkpoint' },
    { k: 'Tests',         v: 'McNemar (per-impl), DeLong (AUROC)', mono: true },
  ]
  return (
    <section ref={ref} id="method" className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-20">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
          06 · Method
        </div>
        <h2 className="font-display text-text0 text-3xl md:text-5xl leading-[1.05] tracking-tight mb-12">
          The stack.
        </h2>
        <dl className="border-y border-line1 max-w-3xl">
          {ROWS.map((r, i) => (
            <div key={i} className={`grid grid-cols-[160px_1fr] gap-6 items-baseline py-3.5 ${i > 0 ? 'border-t border-line1' : ''}`}>
              <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3">{r.k}</dt>
              <dd className={`text-text1 text-[15px] ${r.mono ? 'font-mono' : ''}`}>{r.v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer>
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-10 flex flex-wrap items-center gap-x-6 gap-y-3 font-mono text-[10px] uppercase tracking-[0.14em] text-text3">
        <span>MIT</span><span className="text-line2">·</span>
        <span>Guy Nachshon · Oz Labs</span><span className="text-line2">·</span>
        <span>Apart × Atlas SPS Hackathon · Track 3 · May 2026</span>
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
      <TopNav />
      <Hero />
      <FindingsTable />
      <UmapFigure />
      <AuditSection />
      <TrainingArcSection />
      <ArtifactsSection />
      <MethodBlock />
      <Footer />
    </div>
  )
}
