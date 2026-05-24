# EBM energy-manifold demo

Interactive UMAP visualization of run #10's per-line and whole-impl energies
over the real-bug corpus (n=1492). Click an impl in the left panel to see its
lines highlighted in the right panel.

**Two modes:**

- **Static** (default in the shipped build): `demo/frontend/dist/` is a
  self-contained site. Open `index.html` directly in a browser, or serve
  with any static server:
  `python3 -m http.server --directory demo/frontend/dist`
  All manifold data is precomputed; live scoring and gradient descent are
  disabled.
- **Dynamic**: run the FastAPI backend (`uvicorn demo.backend.app:app`) and
  rebuild the frontend with `VITE_DEMO_MODE=dynamic npm run build` to enable
  live `/api/score-line` and `/api/descend`.

For the precompute step, see `demo/scripts/precompute_static.py`. Re-run it
whenever the underlying manifold parquets change.

## Architecture

- **Offline**: `demo/scripts/build_manifold.py` runs the run #10 checkpoint on
  every record, extracts sentinel-token hidden states for each line, fits two
  UMAPs (impl-level mean-pooled + line-level per-sentinel), and writes:
  - `demo/backend/data/impl_manifold.parquet`
  - `demo/backend/data/line_manifold.parquet`
  - `demo/backend/data/umap_impl.joblib`
  - `demo/backend/data/umap_line.joblib`

- **Backend**: FastAPI app (`demo/backend/app.py`) serves the precomputed
  parquets and exposes a `/api/score-line` endpoint that runs the model live
  on user-typed text and projects the new embedding into the precomputed
  UMAP (approximate transform).

- **Frontend**: React + Vite + deck.gl (`demo/frontend/`). Two-panel
  WebGL-accelerated scatter plots colored by energy.

## Run locally

```bash
# 1. Build manifold (one-time, ~10 min on MPS / GPU)
uv run python demo/scripts/build_manifold.py \
    --config configs/run10_hybrid.yaml \
    --ckpt-dir checkpoints/run10_final \
    --records artifacts/real_bugs/records.jsonl \
    --out-dir demo/backend/data

# 2. Frontend deps + build
cd demo/frontend && npm install && npm run build && cd ../..

# 3. Run backend (serves frontend at http://localhost:8000)
uv run uvicorn demo.backend.app:app --host 0.0.0.0 --port 8000
```

## Dev loop

```bash
# Terminal 1: backend (auto-reload)
uv run uvicorn demo.backend.app:app --reload --port 8000

# Terminal 2: frontend dev server with HMR (proxies /api to backend)
cd demo/frontend && npm run dev
```

Open http://localhost:5173 (dev) or http://localhost:8000 (production build).

## Deploy notes

- The backend can run on CPU; live `/api/score-line` will take ~1-2s instead
  of ~200ms on GPU. The 1.5B model needs ~3GB RAM in fp16, ~6GB in fp32.
- The precomputed manifold data is ~5MB total — fine to bake into the image.
- `umap.transform()` is approximate; user-typed lines are placed by kNN
  interpolation in the original 1536-d embedding space, not a true joint
  refit. Good enough for "is this line close to other suspicious lines?"
- Set `EBM_DEMO_CKPT` / `EBM_DEMO_CONFIG` / `EBM_DEMO_DATA` env vars to
  override the default paths.
