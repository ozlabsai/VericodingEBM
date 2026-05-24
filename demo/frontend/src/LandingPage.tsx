/* LandingPage.tsx — anti-template pass.
 *
 * Editorial restructure. Each section has a DIFFERENT shape — not the same
 * `[eyebrow][headline left][content right]` template repeated 8x. Sentient
 * serif carries display surfaces; General Sans body; JetBrains Mono numbers.
 * Pastel cyan accent + Black-Box ink (board #4 palette).
 */
import { useEffect, useRef } from 'react'
import LandingHeroFigure from './LandingHeroFigure'
import HeroPerLineFigure from './HeroPerLineFigure'
import TrainingArcFigure from './TrainingArcFigure'
import LandingRegimeFigure from './LandingRegimeFigure'
import AppNav from './AppNav'

function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(es => {
      es.forEach(e => { if (e.isIntersecting) { el.classList.add('visible'); io.unobserve(el) } })
    }, { threshold: 0.12 })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return ref
}

// ─── HERO — wide editorial spread, no eyebrow ──────────────────────────
function Hero() {
  const lref = useReveal<HTMLDivElement>()
  const rref = useReveal<HTMLDivElement>()
  return (
    <section className="border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 pt-24 pb-16 grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-12 lg:gap-20 items-start">
        <div ref={lref} className="reveal">
          <h1 className="text-text0 leading-[1.0] tracking-tight mb-8"
              style={{ fontSize: 'clamp(2.8rem, 6vw, 5.2rem)' }}>
            Where to <span>look</span><br/>
            when verification<br/>
            fails.
          </h1>
          <p className="text-text2 text-[17px] leading-[1.6] max-w-xl">
            A discriminative energy-based model that scores each line of a Verus
            implementation with an energy proxy for{' '}
            <span className="text-text0">this line is the bug.</span>
            {' '}Qwen2.5-Coder-1.5B with LoRA, trained on the Microsoft Verus Training
            Data, evaluated against six static baselines, five frontier LLMs, and
            in closed-loop CEGIS with the Verus toolchain in the loop.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-2 font-mono text-[11px]">
            <a href="/manifold"
               className="press inline-flex items-center gap-2 px-4 py-2.5 rounded bg-text0 text-bg0 uppercase tracking-[0.12em] hover:bg-text1">
              open the demo
              <svg width="11" height="11" viewBox="0 0 12 12"><path d="M3 6h6m-3-3l3 3-3 3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </a>
            <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf"
               target="_blank" rel="noreferrer"
               className="press inline-flex items-center px-3.5 py-2.5 rounded border border-line2 text-text2 hover:text-text0 hover:border-text3 uppercase tracking-[0.12em]">
              read the paper · 23pp
            </a>
            <a href="https://huggingface.co/OzLabs/VericodingEBM"
               target="_blank" rel="noreferrer"
               className="press inline-flex items-center px-3.5 py-2.5 rounded border border-line2 text-text2 hover:text-text0 hover:border-text3 uppercase tracking-[0.12em]">
              hf weights
            </a>
          </div>
        </div>
        <div ref={rref} className="reveal lg:pt-4">
          <LandingHeroFigure />
        </div>
      </div>
    </section>
  )
}

// ─── BIG NUMBER PLATE — single hero metric, not a card grid ─────────────
function BigNumberPlate() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20 grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-10 items-end">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">on Verus dev-test (n=609 FAILs)</div>
          <div className="text-text0 leading-none mb-4"
               style={{ fontSize: 'clamp(5rem, 13vw, 12rem)', letterSpacing: '-0.05em' }}>
            0.84
          </div>
          <div className="text-text2 text-[17px] leading-[1.55] max-w-md">
            Per-line top-3 recall — the only measurement where the 1.5B specialist
            beats every frontier LLM (vs Claude Opus 4.7 at <span className="tabular text-text1">0.74</span>).
          </div>
        </div>
        <div className="grid grid-cols-3 gap-x-6 gap-y-4 max-w-md lg:max-w-full">
          {[
            { v: '0.78', l: 'whole-impl AUROC', sub: 'vs GPT-5.5 0.91' },
            { v: '25%',  l: 'CEGIS repair@1',   sub: 'vs LLM 30%' },
            { v: '−52pp',l: 'Δ marker-stripped',sub: 'LLMs ~ 0pp' },
          ].map((m,i) => (
            <div key={i} className="flex flex-col">
              <span className="tabular text-text0 text-3xl leading-none">{m.v}</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 mt-1.5">{m.l}</span>
              <span className="font-mono text-[10px] tabular text-text3/80 mt-0.5">{m.sub}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── ABSTRACT — centered editorial paragraph, no eyebrow ────────────────
function Abstract() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-3xl mx-auto px-6 py-24 text-center">
        <p className="text-text1 text-2xl md:text-3xl leading-[1.45] tracking-tight">
          We treat per-line fault localization as a discriminative
          energy-based modeling problem: assign an unnormalized scalar
          energy to each line of an implementation, conditioned on its
          specification, supervised by contrastive losses derived from
          the broken/fixed sibling structure of the Verus training data.
        </p>
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text3 mt-10">
          paper §1 · the model beats every static baseline · loses three of three to LLMs · the contribution is the artifacts
        </p>
      </div>
    </section>
  )
}

// ─── AUDIT — full-bleed accent strip + figure ──────────────────────────
function AuditSection() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[5fr_7fr] gap-12 mb-12 items-end">
          <h2 className="text-text0 leading-[1.05] tracking-tight"
              style={{ fontSize: 'clamp(2.4rem, 4.5vw, 4rem)' }}>
            Strip the marker.<br/>
            <span>Watch the energy crash.</span>
          </h2>
          <p className="text-text2 text-[16px] leading-[1.6] max-w-xl">
            Every FAIL impl in the dev-test corpus carries a{' '}
            <code className="font-mono text-[0.92em] bg-bg2 text-text1 px-1.5 py-0.5 rounded">// FAILS</code>
            {' '}debug marker that Qwen's pretraining prior couples to verification
            failure. We documented the leak, released the strip-FAILS audit pipeline,
            and ship a fix that overshoots into marker-aversion.
          </p>
        </div>
        <HeroPerLineFigure />
        <div className="mt-16 pt-10 border-t border-line1">
          <LandingRegimeFigure />
        </div>
      </div>
    </section>
  )
}

// ─── TRAINING — sparkline first, no eyebrow ────────────────────────────
function TrainingArcSection() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <h2 className="text-text0 leading-[1.05] tracking-tight mb-3"
            style={{ fontSize: 'clamp(2.4rem, 4.5vw, 4rem)' }}>
          Five runs.<br/>
          <span>One that survived audit.</span>
        </h2>
        <p className="text-text2 text-[16px] leading-[1.6] max-w-2xl mb-12">
          Run 07 looked great until we audited it. Run 08 over-corrected. Run 09 was
          directionally right. Run 10 is what's served here.
          Hover a point for the verdict and the delivered metrics.
        </p>
        <TrainingArcFigure />
      </div>
    </section>
  )
}

// ─── ARTIFACTS — wide editorial list, no card chassis ──────────────────
function ArtifactsSection() {
  const ref = useReveal<HTMLDivElement>()
  const items = [
    {
      n: '01',
      label: 'Discriminative EBM',
      body: 'Qwen2.5-Coder-1.5B + LoRA + sentinel-token per-line head + scalar attention-pool head. Trained with within-spec InfoNCE + pairwise hinge + ListNet + semi-hard mining.',
      href: 'https://huggingface.co/OzLabs/VericodingEBM', linkLabel: 'OzLabs/VericodingEBM',
    },
    {
      n: '02',
      label: 'Line-labelled Verus dev-test',
      body: '1,492 implementations (609 with FAIL labels and gold buggy-line indices) scraped from verus-lang/verus and hand-checked. Plus 39,440 training pairs.',
      href: 'https://huggingface.co/datasets/OzLabs/VericodingEBM-data', linkLabel: 'OzLabs/VericodingEBM-data',
    },
    {
      n: '03',
      label: 'strip-FAILS audit pipeline',
      body: 'A laptop-only audit script that reports the top-k delta between markered and stripped runs. The pipeline that surfaced the leak.',
      href: 'https://github.com/ozlabsai/VericodingEBM/blob/main/scripts/audit_demo.py', linkLabel: 'scripts/audit_demo.py',
    },
    {
      n: '04',
      label: 'closed-loop CEGIS harness',
      body: 'Three-arm comparison (specialist-guided / LLM-only / LLM-self-judged) with the real Verus toolchain in the loop, McNemar pairwise tests, n=100.',
      href: 'https://github.com/ozlabsai/VericodingEBM/tree/main/artifacts/cegis', linkLabel: 'artifacts/cegis/',
    },
  ]
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <h2 className="text-text0 leading-[1.05] tracking-tight mb-3"
            style={{ fontSize: 'clamp(2.4rem, 4.5vw, 4rem)' }}>
          Four artifacts.
        </h2>
        <p className="text-text2 text-[16px] leading-[1.6] max-w-2xl mb-12">
          The contribution per §1.4 of the paper. The model itself is one of them; the
          dataset, the audit, and the eval harness are the other three. Everything is released.
        </p>
        <ol className="border-y border-line1">
          {items.map((it, i) => (
            <li key={it.n} className={`grid grid-cols-12 gap-6 items-baseline py-7 ${i > 0 ? 'border-t border-line1' : ''}`}>
              <span className="col-span-1 font-mono text-[10px] tabular text-text3">{it.n}</span>
              <h3 className="col-span-12 sm:col-span-3 text-text0 text-2xl leading-tight tracking-tight">{it.label}</h3>
              <p className="col-span-12 sm:col-span-6 text-text2 text-[14px] leading-relaxed">{it.body}</p>
              <a href={it.href} target="_blank" rel="noreferrer"
                 className="press col-span-12 sm:col-span-2 text-right font-mono text-[11px] text-text2 hover:text-text0 tracking-tight">
                {it.linkLabel} →
              </a>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

// ─── METHOD — definition list, no sidebar ──────────────────────────────
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
    <section ref={ref} className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-3xl mx-auto px-6 py-20">
        <h2 className="text-text0 leading-[1.05] tracking-tight mb-8"
            style={{ fontSize: 'clamp(2.4rem, 4.5vw, 4rem)' }}>
          Method.
        </h2>
        <dl className="border-y border-line1">
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

// ─── CLOSING — quiet, no headline, just the CTA ────────────────────────
function Closing() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal">
      <div className="max-w-[1400px] mx-auto px-6 py-24 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-8 items-end">
        <p className="text-text0 text-3xl md:text-5xl leading-[1.1] tracking-tight max-w-2xl">
          The demo runs in your browser.<br/>
          <span className="text-text3 italic">No model load. No backend.</span>
        </p>
        <a href="/manifold"
           className="press inline-flex items-center gap-2 px-5 py-3 rounded bg-text0 text-bg0 font-mono uppercase tracking-[0.12em] text-xs hover:bg-text1 whitespace-nowrap">
          open the demo
          <svg width="11" height="11" viewBox="0 0 12 12"><path d="M3 6h6m-3-3l3 3-3 3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </a>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="border-t border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-8 flex flex-wrap items-center gap-x-6 gap-y-3 font-mono text-[10px] uppercase tracking-[0.14em] text-text3">
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
      <AppNav active="home" />
      <Hero />
      <BigNumberPlate />
      <Abstract />
      <AuditSection />
      <TrainingArcSection />
      <ArtifactsSection />
      <MethodBlock />
      <Closing />
      <Footer />
    </div>
  )
}
