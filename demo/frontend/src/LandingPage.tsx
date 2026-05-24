/* LandingPage.tsx — research-page layout.
 *
 * Two-column. Left rail: paper metadata that stays put as you scroll
 * (title, authors, date, version, links). Right column: content as a
 * single long scroll, numbered sections like a paper (1, 2, 3...). No
 * alternating background. No giant headlines per section. Asymmetric
 * white-space and intentionally-uneven block sizes.
 *
 * Reads like the HTML version of a paper, not a marketing landing.
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

function SectionNum({ n }: { n: string }) {
  return <span className="font-mono text-[11px] tabular text-text3">{n}</span>
}

export default function LandingPage() {
  return (
    <div className="min-h-[100dvh] bg-bg0">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-x-12">

        {/* ─── LEFT RAIL — paper metadata, sticky ─────────────────────── */}
        <aside className="lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto py-10 lg:py-14 border-b lg:border-b-0 lg:border-r border-line1">
          <div className="lg:pr-10 flex flex-col gap-10">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
                v1 · may 2026
              </div>
              <h1 className="text-text0 text-2xl leading-[1.15] tracking-tight">
                Where to Look: Energy-Based Fault Localization for Verus Vericoding
              </h1>
              <div className="font-mono text-[11px] text-text3 mt-3 leading-relaxed">
                Guy Nachshon<br/>Oz Labs<br/>
                <span className="text-text3/80">Apart × Atlas · SPS Hackathon · Track 3</span>
              </div>
            </div>

            <nav className="flex flex-col gap-2 font-mono text-[11px]">
              <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf" target="_blank" rel="noreferrer"
                 className="press inline-flex items-center justify-between py-2 px-3 rounded bg-text0 text-bg0 hover:bg-text1">
                <span className="uppercase tracking-[0.12em]">Read paper</span>
                <span className="text-bg0/70">23pp</span>
              </a>
              <a href="/manifold" className="press inline-flex items-center justify-between py-2 px-3 rounded border border-line2 text-text1 hover:border-text2 hover:bg-bg1">
                <span className="uppercase tracking-[0.12em]">Open demo</span>
                <span className="text-text3">→</span>
              </a>
            </nav>

            <div className="flex flex-col gap-1.5 font-mono text-[11px]">
              <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer"
                 className="press text-text2 hover:text-text0 flex items-center justify-between py-1">
                <span>GitHub</span><span className="text-text3 text-[10px]">ozlabsai/VericodingEBM</span>
              </a>
              <a href="https://huggingface.co/OzLabs/VericodingEBM" target="_blank" rel="noreferrer"
                 className="press text-text2 hover:text-text0 flex items-center justify-between py-1">
                <span>Model</span><span className="text-text3 text-[10px]">OzLabs/VericodingEBM</span>
              </a>
              <a href="https://huggingface.co/datasets/OzLabs/VericodingEBM-data" target="_blank" rel="noreferrer"
                 className="press text-text2 hover:text-text0 flex items-center justify-between py-1">
                <span>Dataset</span><span className="text-text3 text-[10px]">VericodingEBM-data</span>
              </a>
            </div>

            <nav className="hidden lg:flex flex-col gap-1 font-mono text-[10px] uppercase tracking-[0.14em] text-text3">
              <div className="text-text2 mb-2">Contents</div>
              <a href="#abstract"  className="press py-0.5 hover:text-text0">01 · Abstract</a>
              <a href="#results"   className="press py-0.5 hover:text-text0">02 · Results</a>
              <a href="#audit"     className="press py-0.5 hover:text-text0">03 · The audit</a>
              <a href="#training"  className="press py-0.5 hover:text-text0">04 · Training arc</a>
              <a href="#artifacts" className="press py-0.5 hover:text-text0">05 · Artifacts</a>
              <a href="#method"    className="press py-0.5 hover:text-text0">06 · Method</a>
            </nav>

            <div className="font-mono text-[10px] text-text3 mt-auto pt-4 border-t border-line1">
              MIT · 2026
            </div>
          </div>
        </aside>

        {/* ─── RIGHT COLUMN — long-scroll content ─────────────────────── */}
        <main className="py-10 lg:py-14 flex flex-col gap-24">

          {/* 01 — Abstract */}
          <section id="abstract" className="reveal" ref={useReveal<HTMLDivElement>()}>
            <div className="flex items-baseline gap-4 mb-6">
              <SectionNum n="01" />
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3">Abstract</span>
            </div>
            <p className="text-text1 text-xl leading-[1.55] tracking-tight max-w-2xl">
              We treat per-line fault localization as a discriminative
              energy-based modeling problem. Assign an unnormalized scalar energy
              to each line of a Verus implementation, conditioned on its
              specification. Supervise via contrastive losses derived from the
              broken/fixed sibling structure of the Microsoft Verus Training Data.
            </p>
            <p className="text-text2 text-[15px] leading-[1.65] mt-5 max-w-2xl">
              Qwen2.5-Coder-1.5B with LoRA adapters; trains on a single A100 in
              about 30 minutes. Evaluated against six static baselines, five
              frontier LLMs, and in closed-loop CEGIS with the Verus toolchain in
              the loop. The model beats every static baseline on AUROC and top-3
              (DeLong <span className="font-mono tabular text-text1">p&lt;10⁻⁵</span>);
              frontier LLMs match or beat it on all three LLM comparisons. The
              contribution is a set of reusable artifacts, not a specialist-
              superiority claim.
            </p>
          </section>

          {/* 02 — Results */}
          <section id="results" className="reveal" ref={useReveal<HTMLDivElement>()}>
            <div className="flex items-baseline gap-4 mb-8">
              <SectionNum n="02" />
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3">Results · Verus dev-test (n=609 FAILs)</span>
            </div>

            {/* Big number — one metric we win */}
            <div className="mb-12">
              <div className="text-text0 leading-none mb-3"
                   style={{ fontSize: 'clamp(5rem, 11vw, 9rem)', letterSpacing: '-0.055em' }}>
                0.84
              </div>
              <div className="text-text2 text-[15px] leading-[1.55] max-w-xl">
                Per-line top-3 recall — the only measurement where the 1.5B
                specialist beats every frontier LLM
                <span className="text-text3"> (vs Claude Opus 4.7 at </span>
                <span className="tabular text-text1">0.74</span>
                <span className="text-text3">).</span>
              </div>
            </div>

            {/* The other three */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-6 max-w-3xl border-t border-line1 pt-6">
              {[
                { v: '0.78',  l: 'whole-impl AUROC',    sub: 'vs GPT-5.5 0.91',     verdict: 'LLM wins' },
                { v: '25%',   l: 'CEGIS repair@1',      sub: 'vs LLM self-judge 30%', verdict: 'LLM wins' },
                { v: '−52pp', l: 'Δ markers stripped',  sub: 'LLMs near 0pp',       verdict: 'distinct' },
              ].map((m, i) => (
                <div key={i} className="flex flex-col">
                  <span className="tabular text-text0 text-4xl leading-none mb-2">{m.v}</span>
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text2">{m.l}</span>
                  <span className="font-mono text-[10px] tabular text-text3 mt-0.5">{m.sub}</span>
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3/80 mt-2">{m.verdict}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Hero figure — anchored between results and audit, full column width */}
          <section className="reveal" ref={useReveal<HTMLDivElement>()}>
            <div className="flex items-baseline gap-4 mb-4">
              <SectionNum n="Fig 1" />
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3">UMAP of impl embeddings · colored by energy · 1,492 impls</span>
            </div>
            <LandingHeroFigure />
            <div className="font-mono text-[10px] text-text3 mt-3">
              <a href="/manifold" className="press hover:text-text1 underline underline-offset-2">explore the full manifold →</a>
            </div>
          </section>

          {/* 03 — Audit */}
          <section id="audit" className="reveal" ref={useReveal<HTMLDivElement>()}>
            <div className="flex items-baseline gap-4 mb-6">
              <SectionNum n="03" />
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3">The audit</span>
            </div>
            <h2 className="text-text0 text-3xl md:text-4xl leading-[1.1] tracking-tight mb-5 max-w-2xl">
              Strip the marker. Watch the energy crash.
            </h2>
            <p className="text-text2 text-[15px] leading-[1.65] max-w-2xl mb-10">
              Every FAIL impl in the dev-test corpus carries a{' '}
              <code className="font-mono text-[0.92em] bg-bg2 text-text1 px-1.5 py-0.5 rounded">// FAILS</code>
              {' '}debug marker that Qwen's pretraining prior couples to verification
              failure. We documented the leak, released the strip-FAILS audit
              pipeline, and ship a fix that overshoots into marker-aversion.
            </p>
            <HeroPerLineFigure />
            <div className="mt-12 pt-10 border-t border-line1">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
                Fig 2 · three regimes · pinned by measured Δ top-1
              </div>
              <LandingRegimeFigure />
            </div>
          </section>

          {/* 04 — Training arc */}
          <section id="training" className="reveal" ref={useReveal<HTMLDivElement>()}>
            <div className="flex items-baseline gap-4 mb-6">
              <SectionNum n="04" />
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3">Training arc</span>
            </div>
            <h2 className="text-text0 text-3xl md:text-4xl leading-[1.1] tracking-tight mb-5 max-w-2xl">
              Five runs. One that survived audit.
            </h2>
            <p className="text-text2 text-[15px] leading-[1.65] max-w-2xl mb-10">
              Run 07 looked great until we audited it. Run 08 over-corrected.
              Run 09 was directionally right. Run 10 is what's served here.
              Hover a point for the verdict and the delivered metrics.
            </p>
            <TrainingArcFigure />
          </section>

          {/* 05 — Artifacts */}
          <section id="artifacts" className="reveal" ref={useReveal<HTMLDivElement>()}>
            <div className="flex items-baseline gap-4 mb-6">
              <SectionNum n="05" />
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3">What we release</span>
            </div>
            <ol className="border-y border-line1 max-w-3xl">
              {[
                { n: 'i',   t: 'Discriminative EBM', d: 'Qwen2.5-Coder-1.5B + LoRA + sentinel-token per-line head + scalar attention-pool head. Trained with within-spec InfoNCE + pairwise hinge + ListNet + semi-hard mining.', href: 'https://huggingface.co/OzLabs/VericodingEBM', label: 'HF model →' },
                { n: 'ii',  t: 'Line-labelled Verus dev-test', d: '1,492 implementations (609 with FAIL labels and gold buggy-line indices) scraped from verus-lang/verus. Plus 39,440 training pairs.', href: 'https://huggingface.co/datasets/OzLabs/VericodingEBM-data', label: 'HF dataset →' },
                { n: 'iii', t: 'strip-FAILS audit pipeline', d: 'Laptop-only audit script. Reports top-k delta between markered and stripped runs. The pipeline that surfaced the leak.', href: 'https://github.com/ozlabsai/VericodingEBM/blob/main/scripts/audit_demo.py', label: 'audit_demo.py →' },
                { n: 'iv',  t: 'closed-loop CEGIS harness', d: 'Three-arm comparison (specialist-guided / LLM-only / LLM-self-judged) with the real Verus toolchain in the loop, McNemar pairwise tests, n=100.', href: 'https://github.com/ozlabsai/VericodingEBM/tree/main/artifacts/cegis', label: 'artifacts/cegis/ →' },
              ].map((it, i) => (
                <li key={it.n} className={`grid grid-cols-[40px_1fr] gap-4 items-baseline py-6 ${i > 0 ? 'border-t border-line1' : ''}`}>
                  <span className="font-mono text-[11px] tabular text-text3 italic">{it.n}.</span>
                  <div>
                    <div className="text-text0 text-lg tracking-tight mb-1.5">{it.t}</div>
                    <p className="text-text2 text-[14px] leading-relaxed mb-2 max-w-2xl">{it.d}</p>
                    <a href={it.href} target="_blank" rel="noreferrer"
                       className="press font-mono text-[11px] text-text1 hover:text-text0 underline underline-offset-2">
                      {it.label}
                    </a>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          {/* 06 — Method */}
          <section id="method" className="reveal" ref={useReveal<HTMLDivElement>()}>
            <div className="flex items-baseline gap-4 mb-6">
              <SectionNum n="06" />
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3">Method</span>
            </div>
            <dl className="border-y border-line1 max-w-3xl">
              {[
                { k: 'Base',          v: 'Qwen2.5-Coder-1.5B-Instruct' },
                { k: 'Adapter',       v: 'LoRA r=16 α=32, embed-LoRA r=8',  mono: true },
                { k: 'Per-line head', v: 'MLP over sentinel-token hiddens' },
                { k: 'Impl head',     v: 'Scalar attention-pool over impl' },
                { k: 'Loss',          v: 'Within-spec InfoNCE + pairwise hinge + ListNet + semi-hard mining', mono: true },
                { k: 'Training data', v: 'Microsoft Verus Training Data (39k spec/impl pairs)' },
                { k: 'Hardware',      v: '1× A100 SXM 80GB, ~30 min wall-clock to usable checkpoint' },
                { k: 'Tests',         v: 'McNemar (per-impl), DeLong (AUROC)', mono: true },
              ].map((r, i) => (
                <div key={i} className={`grid grid-cols-[140px_1fr] gap-6 items-baseline py-3 ${i > 0 ? 'border-t border-line1' : ''}`}>
                  <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3">{r.k}</dt>
                  <dd className={`text-text1 text-[14px] ${r.mono ? 'font-mono' : ''}`}>{r.v}</dd>
                </div>
              ))}
            </dl>
          </section>

          {/* End — quiet sign-off */}
          <section className="pb-20 pt-4 border-t border-line1">
            <div className="font-mono text-[10px] text-text3">
              Released MIT · code + data + intermediate checkpoints + every LLM-baseline record.
            </div>
          </section>

        </main>
      </div>
    </div>
  )
}
