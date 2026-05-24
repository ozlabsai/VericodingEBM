/* LandingPage.tsx — second pass.
 *
 * Removes LLM-tell phrasings (no "honest", no "we report transparently").
 * Adds two more interactive figures (corruption strip, marker-regime axis)
 * and a concrete training-arc section. Typographic scale pushed wider; the
 * grid is genuinely asymmetric (column widths vary section to section);
 * accent placement spread across the page instead of stacked in headlines.
 */
import LandingHeroFigure from './LandingHeroFigure'
import LandingCorruptionStrip from './LandingCorruptionStrip'
import LandingRegimeFigure from './LandingRegimeFigure'

const NUMBERS: { k: string; ours: string; them: string; themLabel: string; win: 'us' | 'them' | 'split' }[] = [
  { k: 'Per-line top-3 recall',           ours: '0.84',  them: '0.74',  themLabel: 'Claude Opus 4.7', win: 'us' },
  { k: 'Whole-impl AUROC',                ours: '0.78',  them: '0.91',  themLabel: 'GPT-5.5',         win: 'them' },
  { k: 'CEGIS repair@1 (n = 100)',        ours: '25%',   them: '30%',   themLabel: 'LLM self-judge', win: 'them' },
  { k: 'Δ top-1 with markers stripped',   ours: '−52pp', them: '±5pp',  themLabel: 'frontier LLMs',  win: 'split' },
]

const CHECKPOINTS = [
  { name: 'Hybrid-Averse',
    sigil: 'H',
    tag: 'canonical',
    role: 'Marker-AVERSE.',
    detail: 'Per-line top-1 IMPROVES when // FAILS markers are stripped. The post-fix model that all paper headlines are taken from.' },
  { name: 'Sentinel-Reliant',
    sigil: 'S',
    tag: 'pre-audit',
    role: 'Marker-RELIANT.',
    detail: 'Top-1 collapses from 73% to 27% when the marker is removed. The leak whose audit motivated everything below.' },
  { name: 'EPA-Stack',
    sigil: 'E',
    tag: 'addendum',
    role: 'Marker-AVERSE, milder.',
    detail: 'A post-deadline retry with ListMLE + focal weighting. Same regime as Hybrid-Averse, smaller swing. Lives in App E footnote.' },
]

const SURFACES = [
  { href: '/manifold',    label: 'Manifold',     mono: 'impl × line',   body: 'UMAP of impl and line embeddings, colored by energy. Click a point to drill into source. Curated examples in the right rail.' },
  { href: '/landscape',   label: 'Landscape 2D', mono: 'E(x,y) heat',   body: 'KNN-interpolated continuous energy field. Arrows are −∇E. Click anywhere to drop a ball and watch it descend.' },
  { href: '/landscape3d', label: 'Landscape 3D', mono: 'terrain',       body: 'Same field as terrain. Valleys are safe regions, peaks are suspicious. Curated examples appear as colored spheres pinned to the surface.' },
]

const TRAINING_ARC: { n: string; codename: string; result: string; verdict: 'broke' | 'partial' | 'fixed' | 'shipped' }[] = [
  { n: '07', codename: 'Sentinel-Reliant',     result: 'Looks great (top-3 = 0.93). Strip the // FAILS marker → collapses to 0.27. Leak.',                          verdict: 'broke' },
  { n: '08', codename: 'Counterfactual-Mixed', result: 'Mixed-marker augmentation as a soft regularizer. AUROC tanks, leak persists.',                                verdict: 'broke' },
  { n: '09', codename: 'Counterfactual-Aug',   result: 'Adversarial-only marker injection. Leak reduced, AUROC still flat — alignment without uniformity.',          verdict: 'partial' },
  { n: '10', codename: 'Hybrid-Averse',        result: 'Scalar attention-pool head + hybrid loss. AUROC → 0.78, top-3 → 0.84, marker-aversion locked in.',           verdict: 'fixed' },
  { n: '11b',codename: 'EPA-Stack',            result: 'ListMLE + focal weighting on top. Same aversion pattern, slightly milder. Footnoted, not headlined.',         verdict: 'shipped' },
]

const VERDICT_TONE: Record<typeof TRAINING_ARC[number]['verdict'], string> = {
  broke:   'text-warm',
  partial: 'text-accent',
  fixed:   'text-success',
  shipped: 'text-body/80',
}

function ExternalArrow() {
  return <svg width="10" height="10" viewBox="0 0 10 10" className="inline-block ml-1 -translate-y-px"><path d="M3 7l4-4M7 3v4M7 3H3" stroke="currentColor" strokeWidth="1.2" fill="none" strokeLinecap="round" /></svg>
}

function SectionLabel({ children, n }: { children: React.ReactNode; n?: string }) {
  return (
    <div className="flex items-baseline gap-3 mb-4">
      {n && <span className="font-mono text-[10px] tabular-display text-accent">{n}</span>}
      <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">{children}</span>
      <div className="flex-1 h-px bg-border ml-2" />
    </div>
  )
}

export default function LandingPage() {
  return (
    <div className="min-h-screen relative">
      {/* Sticky thin header */}
      <header className="border-b border-border bg-ink/70 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-6">
          <a href="/" className="flex items-baseline gap-2 group">
            <span className="font-serif italic text-lg text-fg leading-none">VericodingEBM</span>
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted group-hover:text-body transition-colors">v1 · hybrid-averse</span>
          </a>
          <nav className="ml-auto flex items-center gap-1 font-mono text-[11px] uppercase tracking-[0.14em]">
            <a href="/manifold"     className="px-2 py-1 rounded text-muted hover:text-fg transition-colors">manifold</a>
            <a href="/landscape"    className="px-2 py-1 rounded text-muted hover:text-fg transition-colors">2d</a>
            <a href="/landscape3d"  className="px-2 py-1 rounded text-muted hover:text-fg transition-colors">3d</a>
            <span className="text-border px-1">/</span>
            <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer"
               className="px-2 py-1 rounded text-muted hover:text-accent transition-colors">github<ExternalArrow /></a>
            <a href="https://huggingface.co/OzLabs/VericodingEBM" target="_blank" rel="noreferrer"
               className="px-2 py-1 rounded text-muted hover:text-accent transition-colors">model<ExternalArrow /></a>
          </nav>
        </div>
      </header>

      {/* HERO */}
      <section className="max-w-7xl mx-auto px-6 pt-20 pb-16 grid grid-cols-1 lg:grid-cols-[1.15fr_1fr] gap-12 lg:gap-16 items-start">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted mb-7 max-w-md">
            Apart × Atlas Computing<br/>
            Secure Program Synthesis Hackathon · Track 3 · Vericoding
          </div>
          <h1 className="text-fg leading-[0.94] tracking-editorial mb-7"
              style={{ fontSize: 'clamp(2.8rem, 6.4vw, 5.4rem)' }}>
            Where to <span className="font-serif italic text-accent">look</span><br/>
            when verification<br/>
            fails.
          </h1>
          <p className="text-body/90 leading-[1.55] max-w-xl"
             style={{ fontSize: 'clamp(1rem, 1.2vw, 1.18rem)' }}>
            A 1.5B-parameter discriminative energy-based model that scores every line of a
            Verus implementation with an energy proxy for <span className="text-fg font-serif italic">this line is the bug.</span>
            Trained on 39k spec/impl pairs, benchmarked against frontier LLMs and a suite of
            static baselines, audited for shortcut learning on the <code className="font-mono text-[0.92em] text-accent">// FAILS</code> debug marker.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-x-2 gap-y-2 font-mono text-[11px]">
            <a href="/manifold"
               className="group inline-flex items-center gap-2 px-4 py-2.5 rounded bg-accent text-ink font-medium uppercase tracking-[0.16em] hover:bg-accent-2 rise">
              open the demo
              <svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 6h6m-3-3l3 3-3 3" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </a>
            <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf"
               target="_blank" rel="noreferrer"
               className="px-3.5 py-2.5 rounded border border-border text-body hover:border-border-2 hover:text-fg rise uppercase tracking-[0.14em]">
              paper · 23pp
            </a>
            <a href="https://huggingface.co/OzLabs/VericodingEBM"
               target="_blank" rel="noreferrer"
               className="px-3.5 py-2.5 rounded border border-border text-body hover:border-border-2 hover:text-fg rise uppercase tracking-[0.14em]">
              🤗 weights
            </a>
            <a href="https://huggingface.co/datasets/OzLabs/VericodingEBM-data"
               target="_blank" rel="noreferrer"
               className="px-3.5 py-2.5 rounded border border-border text-body hover:border-border-2 hover:text-fg rise uppercase tracking-[0.14em]">
              🤗 data
            </a>
          </div>

          {/* Inline stat strip */}
          <div className="mt-12 grid grid-cols-3 gap-6 max-w-lg">
            {[
              { v: '1,492', u: 'dev-test impls'  },
              { v: '17,168', u: 'scorable lines' },
              { v: '4', u: 'trained checkpoints' },
            ].map(s => (
              <div key={s.u}>
                <div className="tabular-display text-fg text-2xl">{s.v}</div>
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted mt-0.5">{s.u}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="lg:pt-6">
          <LandingHeroFigure />
          <div className="mt-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted flex items-center gap-3 flex-wrap">
            <span className="text-accent">● live</span>
            <span className="text-border">·</span>
            <span>hover the map</span>
            <span className="text-border">·</span>
            <a href="/manifold" className="text-body/70 hover:text-accent transition-colors">explore the full manifold →</a>
          </div>
        </div>
      </section>

      {/* RESULTS — editorial divided table */}
      <section className="border-t border-border bg-ink-2/60 relative">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-12">
            <div>
              <SectionLabel n="01">results</SectionLabel>
              <h2 className="font-serif italic text-fg leading-[1.05] tracking-tight-x mb-4"
                  style={{ fontSize: 'clamp(2rem, 3vw, 2.8rem)' }}>
                A 1.5B specialist<br/>
                against the best<br/>
                frontier LLMs.
              </h2>
              <p className="text-body/75 text-sm leading-relaxed max-w-xs">
                Four measurements. Hybrid-Averse wins per-line localization,
                loses whole-impl ranking and CEGIS repair, and sits in a different
                regime than LLMs on the marker-leak audit.
              </p>
            </div>
            <div className="divide-y divide-border border-y border-border">
              {NUMBERS.map((n) => (
                <div key={n.k} className="grid grid-cols-12 gap-4 items-baseline py-6">
                  <div className="col-span-12 sm:col-span-4 text-body/95 text-[15px]">{n.k}</div>
                  <div className="col-span-5 sm:col-span-3 flex items-baseline gap-2">
                    <span className={`tabular-display text-4xl ${
                      n.win === 'us' ? 'text-success' : n.win === 'split' ? 'text-accent' : 'text-fg'
                    }`}>{n.ours}</span>
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted">ours</span>
                  </div>
                  <div className="col-span-5 sm:col-span-3 flex items-baseline gap-2">
                    <span className="tabular-display text-2xl text-body/65">{n.them}</span>
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{n.themLabel}</span>
                  </div>
                  <div className="col-span-2 text-right font-mono text-[10px] uppercase tracking-widest">
                    {n.win === 'us' && <span className="text-success">we win</span>}
                    {n.win === 'them' && <span className="text-muted">llm wins</span>}
                    {n.win === 'split' && <span className="text-accent">distinct regime</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* THE AUDIT — second interactive figure */}
      <section className="border-t border-border relative">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <SectionLabel n="02">the audit</SectionLabel>
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.6fr] gap-10 lg:gap-14 items-start">
            <div>
              <h2 className="font-serif italic text-fg leading-[1.05] tracking-tight-x mb-5"
                  style={{ fontSize: 'clamp(2rem, 3vw, 2.8rem)' }}>
                Strip the marker.<br/>
                Watch the energy<br/>
                <span className="text-accent">crash.</span>
              </h2>
              <p className="text-body/85 leading-relaxed text-[15px] mb-4">
                Every FAIL implementation in the dev-test corpus carries a
                <code className="font-mono text-[0.92em] text-accent mx-1">// FAILS</code> debug marker that
                the model could trivially memorize as a shortcut. The pre-audit checkpoint did exactly that.
              </p>
              <p className="text-body/85 leading-relaxed text-[15px]">
                Hybrid-Averse goes the other way: stripping the marker increases the per-line top-1 by
                <span className="tabular-display text-fg"> 52pp</span>. Frontier LLMs sit near zero. Both signals are
                useful; they're not the same signal.
              </p>
              <a href="/manifold"
                 className="mt-6 inline-block font-mono text-[11px] uppercase tracking-[0.16em] text-accent hover:text-accent-2 transition-colors">
                try the corruption lab →
              </a>
            </div>
            <LandingCorruptionStrip />
          </div>

          {/* Regime axis figure */}
          <div className="mt-16 pt-10 border-t border-border grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-10 items-start">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent mb-2">
                Three regimes
              </div>
              <p className="text-body/80 text-sm leading-relaxed max-w-xs">
                Same scale. Same dev-test corpus. Three trained checkpoints + the LLM cluster, placed by their measured marker-strip delta.
              </p>
            </div>
            <LandingRegimeFigure />
          </div>
        </div>
      </section>

      {/* TRAINING ARC — a new section that gives the project depth */}
      <section className="border-t border-border bg-ink-2/60 relative">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <SectionLabel n="03">training arc</SectionLabel>
          <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-12">
            <div>
              <h2 className="font-serif italic text-fg leading-[1.05] tracking-tight-x mb-4"
                  style={{ fontSize: 'clamp(2rem, 3vw, 2.8rem)' }}>
                Five runs.<br/>
                One that worked.
              </h2>
              <p className="text-body/75 text-sm leading-relaxed max-w-xs">
                We name checkpoints by what makes them distinctive,
                not when they ran. The arc is in the colors.
              </p>
            </div>
            <ol className="divide-y divide-border border-y border-border">
              {TRAINING_ARC.map((r) => (
                <li key={r.n} className="grid grid-cols-12 gap-4 items-baseline py-5">
                  <span className="col-span-1 font-mono text-[10px] tabular-display text-muted">#{r.n}</span>
                  <span className="col-span-12 sm:col-span-3 font-serif italic text-fg text-lg leading-tight">{r.codename}</span>
                  <span className="col-span-9 sm:col-span-7 text-body/85 text-[14px] leading-relaxed">{r.result}</span>
                  <span className={`col-span-3 sm:col-span-1 text-right font-mono text-[10px] uppercase tracking-widest ${VERDICT_TONE[r.verdict]}`}>
                    {r.verdict}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* SURFACES — three rows, ordinals on left */}
      <section className="border-t border-border relative">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <SectionLabel n="04">surfaces</SectionLabel>
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-10 mb-10">
            <h2 className="font-serif italic text-fg leading-[1.05] tracking-tight-x"
                style={{ fontSize: 'clamp(2rem, 3vw, 2.8rem)' }}>
              Three ways<br/>into the same<br/>energy field.
            </h2>
            <p className="text-body/75 text-sm leading-relaxed self-end max-w-md">
              Same precomputed scoring data, three lenses. The Corruption Lab is wired into
              all three so the demo works fully static — no model load in the browser.
            </p>
          </div>

          <div className="divide-y divide-border border-y border-border">
            {SURFACES.map((s, i) => (
              <a
                key={s.href}
                href={s.href}
                className="group block py-7 grid grid-cols-12 gap-6 items-baseline hover:bg-ink-2/40 transition-colors rise"
              >
                <div className="col-span-1 font-mono text-[10px] text-muted tabular-display">
                  0{i + 1}
                </div>
                <div className="col-span-12 sm:col-span-3">
                  <div className="font-serif italic text-fg text-3xl leading-tight group-hover:text-accent transition-colors">
                    {s.label}
                  </div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted mt-1">
                    {s.mono}
                  </div>
                </div>
                <div className="col-span-12 sm:col-span-7 text-body/85 leading-relaxed text-[14px] max-w-2xl">
                  {s.body}
                </div>
                <div className="col-span-12 sm:col-span-1 text-right font-mono text-base text-muted group-hover:text-accent transition-colors">
                  →
                </div>
              </a>
            ))}
          </div>
        </div>
      </section>

      {/* CHECKPOINTS */}
      <section className="border-t border-border bg-ink-2/60 relative">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <SectionLabel n="05">vocabulary</SectionLabel>
          <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-12">
            <div>
              <h2 className="font-serif italic text-fg leading-[1.05] tracking-tight-x mb-4"
                  style={{ fontSize: 'clamp(2rem, 3vw, 2.8rem)' }}>
                The four<br/>checkpoints.
              </h2>
              <p className="text-body/75 text-sm leading-relaxed max-w-xs">
                Used consistently across paper, model card, data card, and demo.
                Sentinel-Reliant is the one that taught us to audit.
              </p>
            </div>
            <ol className="divide-y divide-border">
              {CHECKPOINTS.map((c) => (
                <li key={c.name} className="py-6 grid grid-cols-[48px_1fr] gap-5 items-baseline">
                  <span className="font-serif italic text-4xl text-accent leading-none">{c.sigil}</span>
                  <div>
                    <div className="flex items-baseline gap-3 flex-wrap">
                      <span className="text-fg text-xl font-medium tracking-tight-x">{c.name}</span>
                      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{c.tag}</span>
                    </div>
                    <div className="text-body/95 mt-1 text-[15px]">{c.role}</div>
                    <div className="text-muted text-sm mt-1 leading-relaxed max-w-2xl">{c.detail}</div>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* METHOD — single editorial paragraph */}
      <section className="border-t border-border relative">
        <div className="max-w-3xl mx-auto px-6 py-20">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted mb-4 text-center">
            method
          </div>
          <p className="text-fg/95 text-2xl leading-[1.5] tracking-tight-x font-serif">
            Qwen2.5-Coder-1.5B-Instruct with a LoRA adapter (rank&nbsp;16, alpha&nbsp;32, embed-LoRA&nbsp;8) and
            two heads: a per-line MLP over sentinel-token hidden states, and a scalar attention-pool
            head over the full implementation. Hybrid loss = <span className="text-accent">logistic pairwise + ListNet + semi-hard mining</span>.
            Counterfactual marker-augmentation forces the model away from the
            <span className="font-mono text-base bg-ink-2 px-1.5 py-0.5 rounded border border-border mx-1 text-accent">// FAILS</span>
            shortcut that the pre-audit checkpoint had learned. Evaluated on per-line top-k, whole-impl
            AUROC, and closed-loop CEGIS repair-rate against a real Verus toolchain. McNemar and DeLong
            tests for every comparison; full numbers in the paper.
          </p>
        </div>
      </section>

      {/* CLOSING CTA */}
      <section className="border-t border-border bg-ink-2/60 relative">
        <div className="max-w-5xl mx-auto px-6 py-16 grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-6 items-end">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent mb-3">try it</div>
            <h2 className="font-serif italic text-fg leading-[1.05] tracking-tight-x"
                style={{ fontSize: 'clamp(2.2rem, 3.6vw, 3.4rem)' }}>
              The demo works in your browser.<br/>No model load. No backend.
            </h2>
          </div>
          <a href="/manifold"
             className="inline-flex items-center gap-2 px-5 py-3 rounded bg-accent text-ink font-mono uppercase tracking-[0.16em] text-xs hover:bg-accent-2 rise whitespace-nowrap">
            open the demo
            <svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 6h6m-3-3l3 3-3 3" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </a>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-border">
        <div className="max-w-7xl mx-auto px-6 py-8 flex flex-wrap items-center gap-x-6 gap-y-3 text-[11px] font-mono uppercase tracking-[0.14em] text-muted">
          <span>MIT</span>
          <span className="text-border">·</span>
          <span>apart × atlas sps hackathon · track 3</span>
          <span className="ml-auto flex gap-4">
            <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer" className="hover:text-fg transition-colors">github<ExternalArrow /></a>
            <a href="https://huggingface.co/OzLabs/VericodingEBM" target="_blank" rel="noreferrer" className="hover:text-fg transition-colors">hf model<ExternalArrow /></a>
            <a href="https://huggingface.co/datasets/OzLabs/VericodingEBM-data" target="_blank" rel="noreferrer" className="hover:text-fg transition-colors">hf data<ExternalArrow /></a>
          </span>
        </div>
      </footer>
    </div>
  )
}
