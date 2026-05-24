/* LandingPage.tsx — redesigned per impeccable design laws.
 *
 * Aesthetic register: brand. Color strategy: committed (warm amber accent
 * carrying ~25% of the surface) on warm-tinted near-black neutrals. Type:
 * Inter Tight + Instrument Serif italic for the editorial headline. The
 * hero is anchored by a live canvas-rendered manifold figure pulled from
 * the same precomputed data the demo uses, so the first thing a judge sees
 * is the model's actual output, not stock chrome.
 */
import LandingHeroFigure from './LandingHeroFigure'

const NUMBERS = [
  { k: 'Per-line top-3 recall',    ours: '0.84',  them: '0.74',  themLabel: 'Claude Opus 4.7',  win: 'us' },
  { k: 'Whole-impl AUROC',         ours: '0.78',  them: '0.91',  themLabel: 'GPT-5.5',          win: 'them' },
  { k: 'CEGIS repair@1',           ours: '25%',   them: '30%',   themLabel: 'LLM self-judged',  win: 'them' },
  { k: 'Marker-strip Δ top-1',     ours: '−52pp', them: '±5pp',  themLabel: 'frontier LLMs',    win: 'split' },
]

const CHECKPOINTS = [
  { name: 'Hybrid-Averse',
    sigil: 'H',
    role: 'Canonical paper headline.',
    detail: 'Marker-AVERSE — per-line top-1 IMPROVES when // FAILS markers are stripped. The post-fix model.' },
  { name: 'Sentinel-Reliant',
    sigil: 'S',
    role: 'Pre-audit baseline.',
    detail: 'Marker-RELIANT — top-1 collapses from 73% to 27% when the marker is removed. Exposed the leak.' },
  { name: 'EPA-Stack',
    sigil: 'E',
    role: 'Post-deadline retry.',
    detail: 'Same aversion pattern as Hybrid-Averse, slightly milder. Mentioned only in App E footnote.' },
]

const SURFACES = [
  { href: '/manifold',     label: 'Manifold',     mono: 'IMPL × LINE',  body: 'UMAP of impl and line embeddings, colored by energy. Click a point to drill into source. Curated examples available in the right rail.' },
  { href: '/landscape',    label: 'Landscape 2D', mono: 'E(x,y) HEAT', body: 'KNN-interpolated continuous energy field. Arrows are −∇E. Click anywhere to drop a ball and watch it descend.' },
  { href: '/landscape3d',  label: 'Landscape 3D', mono: 'TERRAIN',     body: 'Same field, rendered as terrain. Valleys are safe, peaks are suspicious. Curated examples appear as colored spheres pinned to the surface.' },
]

function ExternalArrow() {
  return <svg width="10" height="10" viewBox="0 0 10 10" className="inline-block ml-1 -translate-y-px"><path d="M3 7l4-4M7 3v4M7 3H3" stroke="currentColor" strokeWidth="1.2" fill="none" strokeLinecap="round" /></svg>
}

export default function LandingPage() {
  return (
    <div className="min-h-screen relative">
      {/* Sticky thin header */}
      <header className="border-b border-border bg-ink/70 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-6">
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

      {/* HERO — asymmetric, editorial headline left, live figure right */}
      <section className="max-w-6xl mx-auto px-6 pt-16 pb-14 grid grid-cols-1 lg:grid-cols-[1.05fr_1fr] gap-10 lg:gap-14 items-start">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted mb-6">
            Apart × Atlas Computing<br/>
            Secure Program Synthesis Hackathon · Track 3 · Vericoding
          </div>
          <h1 className="text-fg leading-[0.96] tracking-editorial mb-6"
              style={{ fontSize: 'clamp(2.6rem, 5.4vw, 4.4rem)' }}>
            Where to <span className="font-serif italic text-accent">look</span> when<br/>
            verification fails.
          </h1>
          <p className="text-body/95 leading-relaxed max-w-xl text-lg"
             style={{ fontSize: 'clamp(1rem, 1.15vw, 1.125rem)' }}>
            A 1.5B-parameter discriminative energy-based model that scores every line of a
            Verus implementation with an energy proxy for <span className="text-fg">"this line is the bug."</span>
            Trained, audited, and benchmarked against frontier LLMs and a suite of static baselines.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-x-2 gap-y-2 font-mono text-[12px]">
            <a href="/manifold"
               className="group inline-flex items-center gap-2 px-4 py-2.5 rounded bg-accent text-ink font-medium uppercase tracking-[0.16em] hover:bg-accent-2 rise">
              open the demo
              <svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 6h6m-3-3l3 3-3 3" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </a>
            <a href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf"
               target="_blank" rel="noreferrer"
               className="px-3.5 py-2.5 rounded border border-border text-body hover:border-border-2 hover:text-fg rise uppercase tracking-[0.14em]">
              paper · pdf
            </a>
            <a href="https://github.com/ozlabsai/VericodingEBM"
               target="_blank" rel="noreferrer"
               className="px-3.5 py-2.5 rounded border border-border text-body hover:border-border-2 hover:text-fg rise uppercase tracking-[0.14em]">
              github
            </a>
          </div>
        </div>
        <div className="lg:pt-4">
          <LandingHeroFigure />
          <div className="mt-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted flex items-center gap-3 flex-wrap">
            <span>● live render</span>
            <span className="text-border">·</span>
            <span>hover the map</span>
            <span className="text-border">·</span>
            <a href="/manifold" className="text-body/70 hover:text-accent transition-colors">explore the full manifold →</a>
          </div>
        </div>
      </section>

      {/* RESULTS — editorial table, not a card grid */}
      <section className="border-t border-border bg-ink-2/70 relative">
        <div className="max-w-6xl mx-auto px-6 py-14">
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-10">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted mb-3">
                Results · 04
              </div>
              <h2 className="font-serif italic text-fg text-3xl leading-tight mb-3">
                Honest about<br/>where it wins.
              </h2>
              <p className="text-muted text-sm leading-relaxed">
                Hybrid-Averse (1.5B) versus the strongest frontier LLMs on each measurement.
                We report all three transparently — the marker-leak audit reveals a fourth, distinct regime.
              </p>
            </div>
            <div className="divide-y divide-border">
              {NUMBERS.map((n) => (
                <div key={n.k} className="grid grid-cols-12 gap-4 items-baseline py-5">
                  <div className="col-span-12 sm:col-span-4 text-sm text-body/90">{n.k}</div>
                  <div className="col-span-5 sm:col-span-3 flex items-baseline gap-2">
                    <span className={`tabular-display text-3xl ${
                      n.win === 'us' ? 'text-success' : n.win === 'split' ? 'text-accent' : 'text-fg'
                    }`}>{n.ours}</span>
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted">ours</span>
                  </div>
                  <div className="col-span-5 sm:col-span-3 flex items-baseline gap-2">
                    <span className="tabular-display text-2xl text-body/70">{n.them}</span>
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{n.themLabel}</span>
                  </div>
                  <div className="col-span-2 text-right font-mono text-[10px] uppercase tracking-widest">
                    {n.win === 'us' && <span className="text-success">specialist wins</span>}
                    {n.win === 'them' && <span className="text-muted">llm wins</span>}
                    {n.win === 'split' && <span className="text-accent">distinct regime</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* WHAT'S HERE — three-row split, not three cards */}
      <section className="border-t border-border relative">
        <div className="max-w-6xl mx-auto px-6 py-14">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted mb-3">
            Surfaces · 03
          </div>
          <h2 className="font-serif italic text-fg text-3xl leading-tight mb-10 max-w-xl">
            Three ways into<br/>the same energy field.
          </h2>

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
                  <div className="font-serif italic text-fg text-2xl leading-tight group-hover:text-accent transition-colors">
                    {s.label}
                  </div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted mt-1">
                    {s.mono}
                  </div>
                </div>
                <div className="col-span-12 sm:col-span-7 text-body/85 leading-relaxed text-sm max-w-2xl">
                  {s.body}
                </div>
                <div className="col-span-12 sm:col-span-1 text-right font-mono text-xs text-muted group-hover:text-accent transition-colors">
                  →
                </div>
              </a>
            ))}
          </div>

          <div className="mt-10 bg-ink-2/60 border border-border rounded-lg p-6 grid grid-cols-1 sm:grid-cols-[200px_1fr] gap-6 items-start">
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent">
              corruption lab<br/>
              <span className="text-muted">on every surface</span>
            </div>
            <div className="text-body/85 leading-relaxed text-sm">
              Six hand-picked (FAIL, PASS) sibling pairs from the dev-test corpus, plus a marker-stripped
              variant of each. <span className="text-fg">All variants are pre-scored by the live model</span> — the static
              demo shows energies instantly without loading a 1.5B model in the browser. Pick an example,
              flip between variants, watch the per-line energy bars and the manifold projection change.
            </div>
          </div>
        </div>
      </section>

      {/* CHECKPOINTS — typographic legend, not card grid */}
      <section className="border-t border-border bg-ink-2/70 relative">
        <div className="max-w-6xl mx-auto px-6 py-14">
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-10">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted mb-3">
                Vocabulary · 03
              </div>
              <h2 className="font-serif italic text-fg text-3xl leading-tight mb-3">
                The four<br/>checkpoints.
              </h2>
              <p className="text-muted text-sm leading-relaxed">
                Descriptive names rather than run numbers, used consistently across the paper, the
                model card, the data card, and this demo. The naming key is the first paragraph of §4.
              </p>
            </div>
            <ol className="divide-y divide-border">
              {CHECKPOINTS.map((c, i) => (
                <li key={c.name} className="py-6 grid grid-cols-[40px_1fr] gap-5 items-baseline">
                  <span className="font-serif italic text-3xl text-accent leading-none">{c.sigil}</span>
                  <div>
                    <div className="flex items-baseline gap-3 flex-wrap">
                      <span className="text-fg text-lg font-medium tracking-tight-x">{c.name}</span>
                      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
                        {i === 0 ? 'canonical' : i === 1 ? 'pre-audit' : 'addendum'}
                      </span>
                    </div>
                    <div className="text-body/90 mt-1 text-sm">{c.role}</div>
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
        <div className="max-w-3xl mx-auto px-6 py-16">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted mb-4 text-center">
            method
          </div>
          <p className="text-fg/95 text-xl leading-[1.55] tracking-tight-x font-serif">
            Qwen2.5-Coder-1.5B-Instruct with a LoRA adapter (rank&nbsp;16, alpha&nbsp;32, embed-LoRA&nbsp;8) and
            two heads: a per-line MLP over sentinel-token hidden states, and a scalar attention-pool
            head over the full implementation. Hybrid loss <span className="text-accent">= logistic pairwise + ListNet + semi-hard mining</span>.
            Counterfactual marker-augmentation forces the model away from the
            <span className="font-mono text-base bg-ink-2 px-1.5 py-0.5 rounded border border-border mx-1 text-accent">// FAILS</span>
            shortcut that the pre-audit checkpoint had learned. Evaluation: per-line top-k, whole-impl
            AUROC, and closed-loop CEGIS repair-rate against a real Verus toolchain. Full numbers and
            statistical tests (McNemar, DeLong) in the paper.
          </p>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-wrap items-center gap-x-6 gap-y-3 text-[11px] font-mono uppercase tracking-[0.14em] text-muted">
          <span>MIT</span>
          <span className="text-border">·</span>
          <span>apart × atlas sps hackathon · track 3 · vericoding</span>
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
