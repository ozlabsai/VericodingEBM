/* LandingPage.tsx — pass 4.
 *
 * Framing pulled back to mirror the paper:
 *   Title:        "Where to Look: Energy-Based Fault Localization for Verus Vericoding"
 *   Thesis:       a small discriminative EBM (Qwen2.5-Coder-1.5B + LoRA), trained,
 *                 audited, and benchmarked against 6 static baselines + 5 frontier LLMs
 *                 + closed-loop CEGIS. The model beats every static baseline on AUROC
 *                 and top-3; frontier LLMs match or beat it on all three LLM comparisons.
 *   Contribution: four reusable artifacts (model, dev-test corpus, strip-FAILS audit,
 *                 CEGIS harness), not a claim of specialist superiority.
 *
 * Hero figure is the interactive UMAP of the impl manifold (LandingHeroFigure) —
 * that's the model's actual output and matches the paper's "energy field" framing.
 * The per-line corruption figure lives inside the audit section, where it belongs.
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
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) { el.classList.add('visible'); io.unobserve(el) } })
    }, { threshold: 0.12 })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return ref
}

function Nav() { return <AppNav active="home" /> }

// ─── HERO — UMAP figure right, paper-style title left ───────────────────
function Hero() {
  const lref = useReveal<HTMLDivElement>()
  const rref = useReveal<HTMLDivElement>()
  return (
    <section className="border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 pt-20 pb-14 grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-12 lg:gap-16 items-start">
        <div ref={lref} className="reveal">
          <div className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-8">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-pos" />
            Apart × Atlas Computing · SPS Hackathon · Track 3 · Vericoding
          </div>
          <h1 className="text-text0 leading-[0.95] tracking-editorial font-medium mb-6"
              style={{ fontSize: 'clamp(2.4rem, 5vw, 4.4rem)' }}>
            Where to Look:<br/>
            <span className="text-text2">energy-based fault</span><br/>
            <span className="text-text2">localization for Verus.</span>
          </h1>
          <p className="text-text2 text-[16px] leading-[1.6] max-w-xl">
            A discriminative energy-based model that scores each line of a Verus
            implementation with an energy proxy for{' '}
            <span className="text-text1">this line is the bug</span>.
            Qwen2.5-Coder-1.5B with LoRA, trained on the Microsoft Verus Training
            Data, evaluated against six static baselines, five frontier LLMs, and
            in closed-loop CEGIS with the Verus toolchain in the loop.
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
              read the paper · 23pp
            </a>
            <a href="https://huggingface.co/OzLabs/VericodingEBM"
               target="_blank" rel="noreferrer"
               className="press inline-flex items-center px-3.5 py-2.5 rounded border border-line2 text-text2 hover:text-text0 hover:border-text3 uppercase tracking-[0.12em]">
              hf weights
            </a>
          </div>
        </div>

        <div ref={rref} className="reveal lg:pt-2">
          <LandingHeroFigure />
          <div className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-text3 flex items-center gap-3 flex-wrap">
            <span className="text-pos">● live</span>
            <span className="text-line2">·</span>
            <span>UMAP of impl embeddings · color = whole-impl energy</span>
            <a href="/manifold" className="ml-auto text-text2 hover:text-accent">drill into points →</a>
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── STATS STRIP — paper-grounded ───────────────────────────────────────
function StatsStrip() {
  const stats = [
    { v: '1.5B',   l: 'parameters' },
    { v: '~20M',   l: 'trainable (LoRA)' },
    { v: '39,440', l: 'training pairs' },
    { v: '1,492',  l: 'dev-test impls' },
    { v: '6',      l: 'static baselines' },
    { v: '5',      l: 'frontier LLMs' },
  ]
  return (
    <section className="border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-6 overflow-x-auto no-scrollbar">
        <div className="flex items-baseline gap-12 min-w-max">
          {stats.map((s, i) => (
            <div key={i} className="flex items-baseline gap-2.5">
              <span className="tabular text-2xl text-text0">{s.v}</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 whitespace-nowrap">{s.l}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── ABSTRACT/THESIS — single paragraph, paper-like ─────────────────────
function ThesisBlock() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-16 grid grid-cols-1 lg:grid-cols-[180px_1fr] gap-10">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3">
          abstract
        </div>
        <p className="text-text1 text-[17px] leading-[1.7] max-w-3xl">
          We treat per-line fault localization as a discriminative energy-based
          modeling problem: assign an unnormalized scalar energy to each scorable
          line of an implementation, conditioned on its specification, and
          supervise via contrastive losses derived from the broken/fixed sibling
          structure of the Verus training data. The final model is small
          (1.5B parameters, ~20M trainable via LoRA) and trains on a single A100
          in about 30 minutes. It beats every static baseline on AUROC and top-3
          (DeLong <span className="font-mono tabular text-text2">p &lt; 10⁻⁵</span>);
          frontier LLMs match or beat it on all three LLM comparisons. The
          contribution is a set of reusable artifacts, not a specialist-superiority
          claim.
        </p>
      </div>
    </section>
  )
}

// ─── RESULTS ────────────────────────────────────────────────────────────
function ResultsStrip() {
  const ref = useReveal<HTMLDivElement>()
  const rows: { k: string; ours: string; them: string; themL: string; win: 'us' | 'them' | 'split' | 'tied'; }[] = [
    { k: 'AUROC vs static baselines',     ours: '0.78',  them: '0.67',  themL: 'best non-leak baseline', win: 'us'   },
    { k: 'Per-line top-3 vs LLMs',         ours: '0.84',  them: '0.74',  themL: 'Claude Opus 4.7',        win: 'us'   },
    { k: 'Per-line top-1 vs Verus-keyword', ours: '0.56', them: '0.55',  themL: 'Verus-keyword',         win: 'tied' },
    { k: 'Whole-impl AUROC vs LLMs',       ours: '0.78',  them: '0.91',  themL: 'GPT-5.5',                win: 'them' },
    { k: 'CEGIS repair@1 (n=100)',         ours: '25%',   them: '30%',   themL: 'LLM self-judged',        win: 'them' },
    { k: 'Δ top-1 with markers stripped',  ours: '−52pp', them: '±5pp',  themL: 'frontier LLMs',          win: 'split' },
  ]
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="flex items-baseline justify-between mb-10 gap-4 flex-wrap">
          <h2 className="text-text0 font-medium tracking-editorial leading-[1.05]"
              style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.6rem)' }}>
            Three classes of baseline.
          </h2>
          <p className="text-text3 text-sm max-w-md">
            Static baselines · zero-shot frontier LLMs · closed-loop CEGIS with the Verus
            toolchain. Numbers from §4 of the paper, run on the dev-test corpus (n=1,492).
          </p>
        </div>
        <div className="border-y border-line1">
          {rows.map((r, i) => (
            <div key={i} className={`grid grid-cols-12 gap-4 items-baseline py-5 ${i > 0 ? 'border-t border-line1' : ''}`}>
              <div className="col-span-12 sm:col-span-4 text-text1 text-[15px]">{r.k}</div>
              <div className="col-span-5 sm:col-span-3 flex items-baseline gap-2">
                <span className={`tabular text-3xl ${
                  r.win === 'us' ? 'text-accent' : 'text-text0'
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
                {r.win === 'tied'  && <span className="text-text2">tied</span>}
                {r.win === 'split' && <span className="text-text1">distinct axis</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── AUDIT — corruption per-line figure (was hero) + regime axis ────────
function AuditSection() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-end mb-10">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-accent mb-3">
              the audit
            </div>
            <h2 className="text-text0 font-medium tracking-editorial leading-[1.05]"
                style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.6rem)' }}>
              Strip-FAILS:<br/>
              what the marker hid.
            </h2>
          </div>
          <p className="text-text2 text-[15px] leading-[1.6] max-w-2xl">
            Every <span className="text-text0">FAIL</span> implementation in the dev-test corpus
            carries a <code className="font-mono text-[0.92em] text-accent mx-1">// FAILS</code> debug marker that
            Qwen's pretraining prior couples to verification failure. We document the leak,
            release the strip-FAILS audit pipeline, and ship a fix that overshoots into
            marker-aversion — flagged in the paper as such.
          </p>
        </div>

        <HeroPerLineFigure />

        <div className="mt-14 pt-10 border-t border-line1 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-10 items-start">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-2">
              three regimes
            </div>
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

// ─── TRAINING ARC ───────────────────────────────────────────────────────
function TrainingArcSection() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-end mb-10">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
              training arc
            </div>
            <h2 className="text-text0 font-medium tracking-editorial leading-[1.05]"
                style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.6rem)' }}>
              Five checkpoints.
            </h2>
          </div>
          <p className="text-text2 text-[15px] leading-[1.6] max-w-2xl">
            The model that ships is run #10 (Hybrid-Averse). Runs #07–#09 are
            documented in Appendix E because the path that worked is also part of
            the contribution. Hover a point for the verdict and the delivered metrics.
          </p>
        </div>
        <TrainingArcFigure />
      </div>
    </section>
  )
}

// ─── ARTIFACTS — the four reusable artifacts the paper claims ───────────
function ArtifactsSection() {
  const ref = useReveal<HTMLDivElement>()
  const items = [
    {
      tag: '01 · model',
      label: 'Discriminative EBM',
      body: 'Qwen2.5-Coder-1.5B + LoRA + sentinel-token per-line head + scalar attention-pool head for whole-impl discrimination. Trained with within-spec InfoNCE + pairwise hinge + ListNet + semi-hard mining.',
      link: { href: 'https://huggingface.co/OzLabs/VericodingEBM', text: 'OzLabs/VericodingEBM' },
    },
    {
      tag: '02 · corpus',
      label: 'Line-labelled Verus dev-test',
      body: '1,492 implementations (609 with FAIL labels and gold buggy-line indices) scraped from verus-lang/verus and hand-checked. Plus 39,440 training pairs from the Microsoft Verus Training Data.',
      link: { href: 'https://huggingface.co/datasets/OzLabs/VericodingEBM-data', text: 'OzLabs/VericodingEBM-data' },
    },
    {
      tag: '03 · audit',
      label: 'strip-FAILS pipeline',
      body: 'A laptop-only audit script that takes two eval-record JSONLs (with markers / stripped) for the same checkpoint and reports the top-k delta. The pipeline that surfaced the leak.',
      link: { href: 'https://github.com/ozlabsai/VericodingEBM/blob/main/scripts/audit_demo.py', text: 'scripts/audit_demo.py' },
    },
    {
      tag: '04 · cegis',
      label: 'closed-loop CEGIS harness',
      body: 'Three-arm comparison (specialist-guided / LLM-only / LLM-self-judged) with the real Verus toolchain in the loop, McNemar pairwise tests, on n=100 records.',
      link: { href: 'https://github.com/ozlabsai/VericodingEBM/tree/main/artifacts/cegis', text: 'artifacts/cegis/' },
    },
  ]
  return (
    <section ref={ref} className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-end mb-10">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
              what we release
            </div>
            <h2 className="text-text0 font-medium tracking-editorial leading-[1.05]"
                style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.6rem)' }}>
              Four reusable<br/>artifacts.
            </h2>
          </div>
          <p className="text-text2 text-[15px] leading-[1.6] max-w-2xl">
            The contribution per §1.4 of the paper. Everything is released — model,
            data, audit, harness, intermediate checkpoints, and every LLM-baseline
            record we generated.
          </p>
        </div>
        <div className="border-y border-line1">
          {items.map((it, i) => (
            <div key={i} className={`grid grid-cols-12 gap-6 items-baseline py-6 ${i > 0 ? 'border-t border-line1' : ''}`}>
              <div className="col-span-12 sm:col-span-2 font-mono text-[10px] uppercase tracking-[0.14em] text-text3">
                {it.tag}
              </div>
              <div className="col-span-12 sm:col-span-3">
                <div className="text-text0 text-lg tracking-crisp">{it.label}</div>
              </div>
              <div className="col-span-12 sm:col-span-5 text-text2 text-[14px] leading-relaxed">
                {it.body}
              </div>
              <div className="col-span-12 sm:col-span-2 text-right">
                <a href={it.link.href} target="_blank" rel="noreferrer"
                   className="press inline-flex items-center font-mono text-[11px] text-text2 hover:text-accent tracking-crisp">
                  {it.link.text} →
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── METHOD — 8-row spec ────────────────────────────────────────────────
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
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-20 grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 items-start">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">method</div>
          <h2 className="text-text0 font-medium tracking-editorial leading-[1.05] mb-4"
              style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.6rem)' }}>
            The stack,<br/>in eight lines.
          </h2>
          <p className="text-text2 text-sm leading-relaxed max-w-sm">
            §2–§3 of the paper. The post-mortem on what didn't work, the gradient
            equations, and the McNemar tables live there.
          </p>
        </div>
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

// ─── SURFACES ───────────────────────────────────────────────────────────
function SurfacesSection() {
  const ref = useReveal<HTMLDivElement>()
  const items = [
    { href: '/manifold',    label: 'Manifold',     mono: 'impl × line',  body: 'UMAP of impl and line embeddings, colored by energy. Click a point to drill into source. Six curated corruption examples in the right rail.' },
    { href: '/landscape',   label: 'Landscape 2D', mono: 'E(x,y) heat',  body: 'KNN-interpolated continuous energy field with −∇E arrows. Click anywhere to drop a ball and watch it descend toward a low-energy basin.' },
    { href: '/landscape3d', label: 'Landscape 3D', mono: 'terrain',      body: 'Same field as terrain. Valleys are safe. Peaks are suspicious. The six curated examples pin to the surface as colored spheres.' },
  ]
  return (
    <section ref={ref} className="reveal border-b border-line1 bg-bg1">
      <div className="max-w-[1400px] mx-auto px-6 py-20">
        <h2 className="text-text0 font-medium tracking-editorial leading-[1.05] mb-10"
            style={{ fontSize: 'clamp(1.8rem, 3.2vw, 2.6rem)' }}>
          Three ways into<br/>the same energy field.
        </h2>
        <div className="border-y border-line1">
          {items.map((s) => (
            <a key={s.href} href={s.href}
               className="press group block py-7 grid grid-cols-12 gap-6 items-baseline border-t border-line1 first:border-t-0 hover:bg-bg2/40">
              <div className="col-span-12 sm:col-span-3">
                <div className="text-text0 text-2xl tracking-crisp group-hover:text-accent">{s.label}</div>
                <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text3 mt-1">{s.mono}</div>
              </div>
              <div className="col-span-12 sm:col-span-8 text-text2 text-[15px] leading-relaxed max-w-2xl">{s.body}</div>
              <div className="col-span-12 sm:col-span-1 text-right font-mono text-base text-text3 group-hover:text-accent">→</div>
            </a>
          ))}
        </div>
      </div>
    </section>
  )
}

function Closing() {
  const ref = useReveal<HTMLDivElement>()
  return (
    <section ref={ref} className="reveal border-b border-line1">
      <div className="max-w-[1400px] mx-auto px-6 py-16 grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-6 items-end">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text3 mb-3">
            try it
          </div>
          <h2 className="text-text0 font-medium tracking-editorial leading-[1.05]"
              style={{ fontSize: 'clamp(1.8rem, 3.4vw, 2.8rem)' }}>
            The demo runs in your browser.<br/>
            <span className="text-text3">No model load. No backend.</span>
          </h2>
        </div>
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
    <footer>
      <div className="max-w-[1400px] mx-auto px-6 py-8 flex flex-wrap items-center gap-x-6 gap-y-3 font-mono text-[10px] uppercase tracking-[0.14em] text-text3">
        <span>MIT</span>
        <span className="text-line2">·</span>
        <span>Guy Nachshon · Oz Labs</span>
        <span className="text-line2">·</span>
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
      <Nav />
      <Hero />
      <StatsStrip />
      <ThesisBlock />
      <ResultsStrip />
      <AuditSection />
      <TrainingArcSection />
      <ArtifactsSection />
      <MethodBlock />
      <SurfacesSection />
      <Closing />
      <Footer />
    </div>
  )
}
