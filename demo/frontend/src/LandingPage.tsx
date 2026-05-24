/* LandingPage.tsx
 *
 * First-impression page at `/`. Goal: in 30 seconds a judge should know
 *   (1) what this is (per-line Verus fault localizer)
 *   (2) the headline numbers (specialist beats baselines, matches LLMs on some)
 *   (3) what to click next (manifold / landscape / corruption lab / paper / HF)
 *
 * Deliberately static — pure markup + tailwind, no API calls, instant render.
 */

const HEADLINE_NUMBERS = [
  { label: 'Per-line top-3 recall',     ours: '0.84', them: '0.74',  themLabel: 'best frontier LLM', win: true  },
  { label: 'Whole-impl AUROC',          ours: '0.78', them: '0.91',  themLabel: 'GPT-5.5',           win: false },
  { label: 'CEGIS repair@1 (n=100)',    ours: '25%',  them: '30%',   themLabel: 'LLM self-judged',   win: false },
  { label: 'Marker-strip top-1 delta',  ours: '−52pp', them: '±5pp', themLabel: 'frontier LLMs',     win: null  },  // distinct / honest
]

const CHECKPOINTS = [
  { name: 'Hybrid-Averse',    role: 'Canonical paper headline. Marker-AVERSE: signal IMPROVES when // FAILS markers are stripped. Post-fix.', color: 'text-emerald-300' },
  { name: 'Sentinel-Reliant', role: 'Pre-audit baseline. Leaks via the // FAILS marker — top-1 collapses from 73% to 27% when the marker is removed.',  color: 'text-rose-300' },
  { name: 'EPA-Stack',        role: 'Post-deadline retry. Same marker-aversion pattern as Hybrid-Averse but slightly milder. Listed only in App E footnote.',         color: 'text-zinc-400' },
]

function Pill({ href, children, tone = 'default' }: { href: string; children: React.ReactNode; tone?: 'default' | 'accent' }) {
  const cls = tone === 'accent'
    ? 'bg-accent text-ink hover:bg-accent/90'
    : 'bg-panel border border-border text-zinc-200 hover:border-zinc-500 hover:text-white'
  return (
    <a href={href} target={href.startsWith('http') ? '_blank' : undefined} rel="noreferrer"
       className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition ${cls}`}>
      {children}
    </a>
  )
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-ink text-zinc-200 antialiased">
      {/* Header strip */}
      <header className="border-b border-border bg-panel/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-4">
          <h1 className="text-sm font-semibold tracking-tight">
            EBM <span className="text-zinc-500">· Verus per-line fault localizer</span>
          </h1>
          <nav className="ml-auto flex gap-1 text-xs">
            <a href="/manifold"     className="px-2 py-1 rounded hover:bg-zinc-800 text-zinc-300">manifold</a>
            <a href="/landscape"    className="px-2 py-1 rounded hover:bg-zinc-800 text-zinc-300">landscape 2D</a>
            <a href="/landscape3d"  className="px-2 py-1 rounded hover:bg-zinc-800 text-zinc-300">landscape 3D</a>
            <span className="text-zinc-700 px-1">|</span>
            <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer"
               className="px-2 py-1 rounded hover:bg-zinc-800 text-zinc-400">github</a>
            <a href="https://huggingface.co/OzLabs/VericodingEBM" target="_blank" rel="noreferrer"
               className="px-2 py-1 rounded hover:bg-zinc-800 text-zinc-400">model</a>
            <a href="https://huggingface.co/datasets/OzLabs/VericodingEBM-data" target="_blank" rel="noreferrer"
               className="px-2 py-1 rounded hover:bg-zinc-800 text-zinc-400">data</a>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-14 pb-10">
        <div className="text-xs uppercase tracking-wider text-zinc-500 mb-3">
          Apart × Atlas Computing · Secure Program Synthesis Hackathon · Track 3 (Vericoding)
        </div>
        <h2 className="text-4xl md:text-5xl font-semibold tracking-tight text-white mb-4 leading-tight">
          Where to look:<br/>
          <span className="text-accent">energy-based per-line fault localization</span><br/>
          for Verus vericoding.
        </h2>
        <p className="text-lg text-zinc-400 max-w-3xl leading-relaxed mb-6">
          A 1.5B-parameter discriminative EBM (Qwen2.5-Coder + LoRA, sentinel-token per-line
          head) that scores every line of a Verus implementation with an energy proxy for
          <em className="text-zinc-200"> "this line is the bug."</em> Trained, audited, and benchmarked
          against frontier LLMs and a suite of static baselines.
        </p>
        <div className="flex flex-wrap gap-2">
          <Pill href="/manifold" tone="accent">Open the live demo →</Pill>
          <Pill href="https://github.com/ozlabsai/VericodingEBM/blob/main/paper/main.pdf">Read the paper (PDF)</Pill>
          <Pill href="https://github.com/ozlabsai/VericodingEBM">github.com/ozlabsai/VericodingEBM</Pill>
          <Pill href="https://huggingface.co/OzLabs/VericodingEBM">🤗 model</Pill>
          <Pill href="https://huggingface.co/datasets/OzLabs/VericodingEBM-data">🤗 dataset</Pill>
        </div>
      </section>

      {/* Headline numbers */}
      <section className="max-w-6xl mx-auto px-6 py-8 border-t border-border">
        <div className="text-xs uppercase tracking-wider text-zinc-500 mb-4">
          Headline results · Hybrid-Averse (1.5B) vs frontier LLMs
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {HEADLINE_NUMBERS.map((n, i) => (
            <div key={i} className="bg-panel border border-border rounded p-4">
              <div className="text-xs text-zinc-500 mb-2">{n.label}</div>
              <div className="flex items-baseline gap-2">
                <span className={`text-3xl font-semibold tabular-nums ${
                  n.win === true ? 'text-emerald-300' : n.win === false ? 'text-zinc-300' : 'text-amber-300'
                }`}>{n.ours}</span>
                <span className="text-xs text-zinc-500">ours</span>
              </div>
              <div className="text-xs text-zinc-500 mt-1.5">
                {n.them} <span className="text-zinc-600">· {n.themLabel}</span>
              </div>
              {n.win === true  && <div className="text-[10px] text-emerald-400/80 mt-2">specialist wins</div>}
              {n.win === false && <div className="text-[10px] text-zinc-500 mt-2">LLM wins (honest)</div>}
              {n.win === null  && <div className="text-[10px] text-amber-400/80 mt-2">distinct regime — both honest</div>}
            </div>
          ))}
        </div>
        <div className="text-xs text-zinc-500 mt-4 max-w-3xl leading-relaxed">
          The specialist beats every static baseline by wide margins, matches a frontier LLM on per-line top-3,
          and loses on whole-impl AUROC and CEGIS repair-rate. We report all three transparently. The marker-leak
          audit (last column) shows the specialist is in a different regime than LLMs — neither is "wrong,"
          both are honest about what they do.
        </div>
      </section>

      {/* What's in the demo */}
      <section className="max-w-6xl mx-auto px-6 py-8 border-t border-border">
        <div className="text-xs uppercase tracking-wider text-zinc-500 mb-4">
          What's in this demo
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <a href="/manifold" className="block bg-panel border border-border rounded p-4 hover:border-accent transition">
            <div className="text-sm font-semibold text-white mb-1">Manifold</div>
            <div className="text-xs text-zinc-400 leading-relaxed">
              UMAP of impl-level and line-level embeddings, colored by energy. 1,492 impls,
              17,168 scorable lines. Click a point to drill into source code.
            </div>
          </a>
          <a href="/landscape" className="block bg-panel border border-border rounded p-4 hover:border-accent transition">
            <div className="text-sm font-semibold text-white mb-1">Landscape (2D)</div>
            <div className="text-xs text-zinc-400 leading-relaxed">
              KNN-interpolated continuous energy field E(x,y). Arrows are −∇E.
              Click anywhere to drop a ball and watch it descend.
            </div>
          </a>
          <a href="/landscape3d" className="block bg-panel border border-border rounded p-4 hover:border-accent transition">
            <div className="text-sm font-semibold text-white mb-1">Landscape (3D)</div>
            <div className="text-xs text-zinc-400 leading-relaxed">
              Same field, in 3D — height = predicted energy. Valleys are safe regions, peaks
              are suspicious. Curated examples appear as colored spheres.
            </div>
          </a>
        </div>
        <div className="mt-4 bg-panel/60 border border-border rounded p-4">
          <div className="text-sm font-semibold text-zinc-200 mb-1">
            Corruption Lab <span className="text-xs text-zinc-500 font-normal">— available on every view</span>
          </div>
          <div className="text-xs text-zinc-400 leading-relaxed">
            Six hand-picked (FAIL, PASS) sibling pairs from the dev-test corpus, plus a marker-stripped variant
            of each. All variants pre-scored by the live model so the static demo can show energies instantly.
            Pick an example, flip between variants, watch the per-line energy bars and the manifold projection
            change.
          </div>
        </div>
      </section>

      {/* Naming key */}
      <section className="max-w-6xl mx-auto px-6 py-8 border-t border-border">
        <div className="text-xs uppercase tracking-wider text-zinc-500 mb-4">
          Naming key — the four checkpoints referenced everywhere
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {CHECKPOINTS.map(c => (
            <div key={c.name} className="bg-panel border border-border rounded p-4">
              <div className={`text-sm font-semibold mb-1 ${c.color}`}>{c.name}</div>
              <div className="text-xs text-zinc-400 leading-relaxed">{c.role}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Method strip */}
      <section className="max-w-6xl mx-auto px-6 py-8 border-t border-border">
        <div className="text-xs uppercase tracking-wider text-zinc-500 mb-4">
          Method, in one paragraph
        </div>
        <p className="text-sm text-zinc-300 max-w-3xl leading-relaxed">
          Qwen2.5-Coder-1.5B-Instruct with a LoRA adapter (rank 16, alpha 32, embed_lora_rank 8) and two heads:
          a small MLP over per-line sentinel-token hidden states (per-line energies) and a scalar attention-pool
          head over the full impl (whole-impl energy). Hybrid loss = logistic pairwise + ListNet + FaceNet-style
          semi-hard mining. Counterfactual marker-augmentation (described in App B) forces the model away from
          the <code className="text-xs bg-ink/60 px-1 py-0.5 rounded">// FAILS</code> comment-token shortcut
          that the pre-audit checkpoint learned. Eval: per-line top-k, whole-impl AUROC, and closed-loop CEGIS
          repair-rate on a real Verus toolchain. Full numbers + statistical tests (McNemar, DeLong) in the paper.
        </p>
      </section>

      {/* Footer */}
      <footer className="border-t border-border mt-12">
        <div className="max-w-6xl mx-auto px-6 py-6 text-xs text-zinc-500 flex flex-wrap items-center gap-3">
          <span>MIT licensed. Submission for Apart × Atlas SPS Hackathon, Track 3 (Vericoding).</span>
          <span className="ml-auto flex gap-2">
            <a href="https://github.com/ozlabsai/VericodingEBM" target="_blank" rel="noreferrer" className="hover:text-zinc-300">GitHub ↗</a>
            <a href="https://huggingface.co/OzLabs/VericodingEBM" target="_blank" rel="noreferrer" className="hover:text-zinc-300">HF model ↗</a>
            <a href="https://huggingface.co/datasets/OzLabs/VericodingEBM-data" target="_blank" rel="noreferrer" className="hover:text-zinc-300">HF data ↗</a>
          </span>
        </div>
      </footer>
    </div>
  )
}
