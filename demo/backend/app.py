"""FastAPI backend for the EBM energy-manifold demo.

Endpoints:
  GET  /api/manifold/impls
       Returns precomputed impl-level scatter data (x, y, energy, status, etc.).

  GET  /api/manifold/impl/{impl_id}/lines
       Returns per-line scatter for a specific impl + its source code.

  GET  /api/manifold/lines
       Returns ALL ~30k line points in the per-line manifold (paginated).

  POST /api/score-line
       Body: {"spec_text": str, "impl_text": str, "target_line_idx": int}
       Runs the model live, returns:
         - per_line_energies for the whole impl
         - 2D (x, y) projection of the target line into the precomputed manifold

Static assets (built React app) are served from /
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pyarrow.parquet as pq
import torch
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ebm_verus.data.line_policy import scorable_line_indices
from ebm_verus.data.tokenize import tokenize_example
from ebm_verus.data.types import Example, Source, Status
from ebm_verus.model.scorer import EnergyScorer

DATA_DIR = Path(os.environ.get("EBM_DEMO_DATA", REPO_ROOT / "demo/backend/data"))
CONFIG = Path(os.environ.get("EBM_DEMO_CONFIG", REPO_ROOT / "configs/run10_hybrid.yaml"))
CKPT_DIR = Path(os.environ.get("EBM_DEMO_CKPT", REPO_ROOT / "checkpoints/run10_final"))
FRONTEND_DIST = REPO_ROOT / "demo/frontend/dist"

app = FastAPI(title="EBM Energy Manifold")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev convenience; tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----- model lazy-loading -----

_MODEL_LOCK = threading.Lock()
_MODEL: dict[str, Any] = {}


def _pick_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _ensure_model():
    """Lazy-load model on first scoring request. Keeps the API responsive when
    the user is only browsing precomputed data and never types a new line."""
    with _MODEL_LOCK:
        if _MODEL:
            return _MODEL
        print("[demo] loading model on first scoring request...", flush=True)
        with CONFIG.open() as f:
            cfg = yaml.safe_load(f)
        device = _pick_device()
        dtype_str = cfg["train"]["precision"]
        dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[dtype_str]
        if device.type == "mps":
            dtype = torch.float32
            # Workaround for MPS GQA SDPA bug.
            import transformers
            _orig = transformers.AutoModelForCausalLM.from_pretrained
            def _p(name, **kw):
                kw.setdefault("attn_implementation", "eager")
                return _orig(name, **kw)
            transformers.AutoModelForCausalLM.from_pretrained = _p

        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
        if tok.pad_token_id is None:
            tok.pad_token_id = tok.eos_token_id

        lora = cfg["model"]["lora"]
        scalar_head = (CKPT_DIR / "scalar_head.pt").exists()
        model = EnergyScorer(
            backbone_name=cfg["model"]["backbone"],
            lora_rank=int(lora["rank"]),
            lora_alpha=int(lora["alpha"]),
            lora_dropout=float(lora["dropout"]),
            lora_target_modules=tuple(lora["target_modules"]),
            embed_lora_rank=int(lora["embed_lora_rank"]),
            head_hidden_dim=int(cfg["model"]["head"]["hidden_dim"]),
            head_dropout=float(cfg["model"]["head"]["dropout"]),
            head_init_std=float(cfg["model"]["head"]["init_std"]),
            torch_dtype=dtype,
            gradient_checkpointing=False,
            scalar_head=scalar_head,
        ).to(device)
        model.load_trainable(CKPT_DIR)
        model.eval()
        _MODEL.update({
            "model": model, "tokenizer": tok, "device": device, "cfg": cfg,
            "scalar_head": scalar_head,
            "umap_impl": joblib.load(DATA_DIR / "umap_impl.joblib"),
            "umap_line": joblib.load(DATA_DIR / "umap_line.joblib"),
        })
        print(f"[demo] model loaded on {device}", flush=True)
        return _MODEL


# ----- precomputed data (eager-load at startup) -----

print(f"[demo] loading precomputed manifold from {DATA_DIR} ...", flush=True)
_IMPL_TABLE = pq.read_table(DATA_DIR / "impl_manifold.parquet").to_pylist()
_LINE_TABLE = pq.read_table(DATA_DIR / "line_manifold.parquet").to_pylist()
_IMPL_BY_ID = {r["impl_id"]: r for r in _IMPL_TABLE}
_LINES_BY_IMPL: dict[str, list[dict]] = {}
for r in _LINE_TABLE:
    _LINES_BY_IMPL.setdefault(r["impl_id"], []).append(r)
print(f"[demo]   {len(_IMPL_TABLE)} impls, {len(_LINE_TABLE)} lines", flush=True)


# ----- energy field (KNN-interpolated continuous surface over the 2D manifold) -----

def _build_field(scope: str, grid: int = 96, arrow_grid: int = 24,
                 k: int = 20, bandwidth_mul: float = 1.2) -> dict:
    """KNN-Gaussian-weighted energy interpolation over a regular grid.

    For each grid cell (gx, gy):
      w_i = exp(-||(gx,gy) - p_i||^2 / (2 * bandwidth^2))  for K nearest points
      E(gx, gy) = sum(w_i * energy_i) / sum(w_i)
    Bandwidth = median nearest-neighbour distance among data points; this auto-
    adapts to the manifold scale and gives a sensible smoothness for any UMAP.

    Returns:
      {
        "scope": "impl" | "line",
        "grid": grid,                       # field is grid x grid
        "x_min/x_max/y_min/y_max": bounds,
        "field": flat float32 list (length grid*grid, row-major y then x),
        "energy_min/energy_max": for color scale,
        "arrows": list of {x0,y0,x1,y1} for vector field display,
        "points": list of {x,y,energy,is_buggy?} thinned for overlay,
      }
    """
    rows = _IMPL_TABLE if scope == "impl" else _LINE_TABLE
    energy_key = "whole_impl_energy" if scope == "impl" else "energy"
    coords = np.array([[r["x"], r["y"]] for r in rows], dtype=np.float32)
    energies = np.array([r[energy_key] for r in rows], dtype=np.float32)
    if coords.shape[0] == 0:
        return {}

    # 5% padding around the data bounds so the heatmap shows a frame.
    x_min, x_max = float(coords[:, 0].min()), float(coords[:, 0].max())
    y_min, y_max = float(coords[:, 1].min()), float(coords[:, 1].max())
    dx = (x_max - x_min) * 0.05
    dy = (y_max - y_min) * 0.05
    x_min -= dx; x_max += dx
    y_min -= dy; y_max += dy

    # Bandwidth = median 5-NN distance (data-driven smoothing).
    from sklearn.neighbors import NearestNeighbors
    sub_n = min(coords.shape[0], 2000)
    nn_sample = NearestNeighbors(n_neighbors=6).fit(coords)
    d, _ = nn_sample.kneighbors(coords[:sub_n])
    bandwidth = float(np.median(d[:, 1:])) * bandwidth_mul or 0.1

    # Build grid.
    xs = np.linspace(x_min, x_max, grid, dtype=np.float32)
    ys = np.linspace(y_min, y_max, grid, dtype=np.float32)
    gx, gy = np.meshgrid(xs, ys)
    grid_pts = np.stack([gx.ravel(), gy.ravel()], axis=1)  # (G*G, 2)

    # Query k nearest data points for every grid cell.
    nn = NearestNeighbors(n_neighbors=min(k, coords.shape[0])).fit(coords)
    dists, idx = nn.kneighbors(grid_pts)  # both (G*G, k)
    weights = np.exp(-(dists ** 2) / (2 * bandwidth ** 2))
    # Floor to avoid divide-by-zero in totally empty regions.
    weights_sum = weights.sum(axis=1, keepdims=True).clip(min=1e-8)
    field = (weights * energies[idx]).sum(axis=1) / weights_sum.squeeze(1)
    field = field.astype(np.float32)

    # Robust color scale: 5–95 percentile so a few extreme outliers don't wash
    # the colormap out.
    energy_min = float(np.quantile(field, 0.05))
    energy_max = float(np.quantile(field, 0.95))

    # Gradient (finite differences) on the field, then subsample for arrows.
    f2d = field.reshape(grid, grid)
    gy_field, gx_field = np.gradient(f2d)  # (grid, grid) each
    arrows = []
    step = max(1, grid // arrow_grid)
    cell_dx = (x_max - x_min) / (grid - 1)
    cell_dy = (y_max - y_min) / (grid - 1)
    # Arrow length scales so the longest one is ~0.8 cell of the arrow_grid.
    max_grad = float(max(np.abs(gx_field).max(), np.abs(gy_field).max(), 1e-8))
    arrow_len = 0.8 * max((x_max - x_min) / arrow_grid, (y_max - y_min) / arrow_grid)
    for i in range(0, grid, step):
        for j in range(0, grid, step):
            ux = -float(gx_field[i, j]) / max_grad * arrow_len
            uy = -float(gy_field[i, j]) / max_grad * arrow_len
            cx = float(xs[j])
            cy = float(ys[i])
            arrows.append({"x0": cx, "y0": cy, "x1": cx + ux, "y1": cy + uy})

    # Thin points for overlay (cap at 3000 for line scope).
    if scope == "line" and len(rows) > 3000:
        sel = np.linspace(0, len(rows) - 1, 3000, dtype=int)
        sample_rows = [rows[i] for i in sel]
    else:
        sample_rows = rows
    points = []
    for r in sample_rows:
        p = {"x": r["x"], "y": r["y"], "energy": r[energy_key]}
        if scope == "line":
            p["is_buggy"] = r.get("is_buggy", False)
        else:
            p["status"] = r.get("status")
        points.append(p)

    return {
        "scope": scope, "grid": grid,
        "x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max,
        "energy_min": energy_min, "energy_max": energy_max,
        "bandwidth": bandwidth,
        "field": field.tolist(),
        "arrows": arrows,
        "points": points,
    }


_FIELD_CACHE: dict[str, dict] = {}


@app.get("/api/energy-field")
def get_energy_field(scope: str = "impl", grid: int = 96, k: int = 20,
                     bandwidth_mul: float = 1.2):
    """Continuous E(x, y) interpolation over the 2D manifold + gradient field.
    Cached per (scope, grid, k, bandwidth_mul)."""
    key = f"{scope}:{grid}:{k}:{bandwidth_mul:.2f}"
    if key not in _FIELD_CACHE:
        if scope not in {"impl", "line"}:
            raise HTTPException(400, "scope must be 'impl' or 'line'")
        print(f"[demo] computing energy field {key} ...", flush=True)
        _FIELD_CACHE[key] = _build_field(scope, grid=grid, k=k,
                                          bandwidth_mul=bandwidth_mul)
    return _FIELD_CACHE[key]


class DescendRequest(BaseModel):
    scope: str = "impl"
    x: float
    y: float
    steps: int = 60
    lr: float = 0.5


@app.post("/api/descend")
def descend(req: DescendRequest):
    """Gradient-descend on the KNN field from (x, y). Returns the trajectory
    as a list of (x, y, energy) — for the 'watch the ball roll' animation.

    Uses the same KNN-interpolated field as /api/energy-field so the visual
    descent matches the visible gradient arrows exactly.
    """
    rows = _IMPL_TABLE if req.scope == "impl" else _LINE_TABLE
    energy_key = "whole_impl_energy" if req.scope == "impl" else "energy"
    coords = np.array([[r["x"], r["y"]] for r in rows], dtype=np.float32)
    energies = np.array([r[energy_key] for r in rows], dtype=np.float32)

    from sklearn.neighbors import NearestNeighbors
    nn = NearestNeighbors(n_neighbors=min(20, coords.shape[0])).fit(coords)
    sample_d, _ = nn.kneighbors(coords[: min(coords.shape[0], 2000)])
    bandwidth = float(np.median(sample_d[:, 1:])) * 1.2 or 0.1

    def _energy_at(pts: np.ndarray) -> np.ndarray:
        d, ix = nn.kneighbors(pts)
        w = np.exp(-(d ** 2) / (2 * bandwidth ** 2))
        w_sum = w.sum(axis=1, keepdims=True).clip(min=1e-8)
        return (w * energies[ix]).sum(axis=1) / w_sum.squeeze(1)

    def _grad_at(pt: np.ndarray, eps: float = 1e-2) -> np.ndarray:
        # Two-sided finite difference.
        pt_plus_x = pt + np.array([[eps, 0]])
        pt_minus_x = pt + np.array([[-eps, 0]])
        pt_plus_y = pt + np.array([[0, eps]])
        pt_minus_y = pt + np.array([[0, -eps]])
        ex = (_energy_at(pt_plus_x) - _energy_at(pt_minus_x)) / (2 * eps)
        ey = (_energy_at(pt_plus_y) - _energy_at(pt_minus_y)) / (2 * eps)
        return np.array([ex[0], ey[0]])

    p = np.array([[req.x, req.y]], dtype=np.float32)
    trajectory = []
    for _ in range(req.steps):
        e = float(_energy_at(p)[0])
        trajectory.append({"x": float(p[0, 0]), "y": float(p[0, 1]), "energy": e})
        g = _grad_at(p)
        # Normalize gradient so step size is roughly constant in screen units.
        g_norm = np.linalg.norm(g)
        if g_norm < 1e-6:
            break
        p = p - req.lr * (g / g_norm) * bandwidth
    return {"trajectory": trajectory}


# ----- endpoints -----

@app.get("/api/manifold/impls")
def get_impls():
    """All impl-level points. Keep payload light: omit impl_text/spec_text."""
    return [
        {
            "impl_id": r["impl_id"],
            "spec_id": r["spec_id"],
            "status": r["status"],
            "whole_impl_energy": r["whole_impl_energy"],
            "n_lines": r["n_lines"],
            "has_pass_sibling": r["has_pass_sibling"],
            "x": r["x"], "y": r["y"],
        }
        for r in _IMPL_TABLE
    ]


@app.get("/api/manifold/lines")
def get_all_lines(limit: int = 0, offset: int = 0):
    """All line-level points. Pass limit=0 (default) for everything."""
    rows = _LINE_TABLE if limit == 0 else _LINE_TABLE[offset: offset + limit]
    return [
        {
            "impl_id": r["impl_id"],
            "line_idx": r["line_idx"],
            "line_text": r["line_text"],
            "energy": r["energy"],
            "is_buggy": r["is_buggy"],
            "impl_status": r["impl_status"],
            "x": r["x"], "y": r["y"],
        }
        for r in rows
    ]


@app.get("/api/manifold/impl/{impl_id}/lines")
def get_impl_lines(impl_id: str):
    if impl_id not in _IMPL_BY_ID:
        raise HTTPException(404, f"impl_id {impl_id} not found")
    impl = _IMPL_BY_ID[impl_id]
    lines = _LINES_BY_IMPL.get(impl_id, [])
    return {
        "impl": {
            "impl_id": impl["impl_id"],
            "spec_id": impl["spec_id"],
            "status": impl["status"],
            "whole_impl_energy": impl["whole_impl_energy"],
            "spec_text": impl["spec_text"],
            "impl_text": impl["impl_text"],
        },
        "lines": [
            {
                "line_idx": r["line_idx"],
                "line_text": r["line_text"],
                "energy": r["energy"],
                "is_buggy": r["is_buggy"],
                "x": r["x"], "y": r["y"],
            }
            for r in sorted(lines, key=lambda x: x["line_idx"])
        ],
    }


class ScoreLineRequest(BaseModel):
    spec_text: str
    impl_text: str


class ScoreLineResponse(BaseModel):
    per_line_energies: list[float]
    line_xys: list[tuple[float, float]]   # projection of each line into precomputed line manifold
    whole_impl_energy: float
    whole_impl_xy: tuple[float, float]    # projection into precomputed impl manifold


@app.post("/api/score-line", response_model=ScoreLineResponse)
def score_line(req: ScoreLineRequest):
    state = _ensure_model()
    model = state["model"]
    tok = state["tokenizer"]
    device = state["device"]
    cfg = state["cfg"]
    scalar_head = state["scalar_head"]
    max_len = int(cfg["data"]["max_seq_len"])
    lse_t = float(cfg["model"]["lse"]["temp_end"])

    ex = Example(
        source=Source.SFT_SAFE,
        spec_id="user-typed",
        impl_id="user-typed",
        spec_text=req.spec_text,
        impl_text=req.impl_text,
        status=Status.UNKNOWN,
        buggy_lines=set(),
    )
    t = tokenize_example(ex, tok, max_length=max_len)
    if t is None or not t.sentinel_positions:
        raise HTTPException(400, "tokenize_example failed (impl_text too short or unparseable)")

    input_ids = torch.tensor([t.input_ids], device=device)
    attn = torch.ones_like(input_ids)
    sent_pos = torch.tensor(t.sentinel_positions, device=device)

    with torch.no_grad():
        hidden = model._hidden_states(input_ids, attn)
        h_lines = hidden[0].index_select(0, sent_pos)
        e_lines = model.head(h_lines.float()).squeeze(-1)
        if scalar_head:
            e_whole = model.scalar_head(hidden[0].float(), attn[0])
        else:
            from ebm_verus.model.scorer import normalized_lse
            e_whole = normalized_lse(e_lines, lse_t)

    line_embeds = h_lines.float().cpu().numpy()      # (n_lines, D)
    impl_embed = line_embeds.mean(axis=0, keepdims=True)  # (1, D)

    # Project into precomputed UMAP spaces (approximate kNN-based transform).
    line_xys = state["umap_line"].transform(line_embeds).tolist()
    impl_xy = state["umap_impl"].transform(impl_embed)[0].tolist()

    return ScoreLineResponse(
        per_line_energies=e_lines.float().cpu().tolist(),
        line_xys=line_xys,
        whole_impl_energy=float(e_whole.float().cpu().item()),
        whole_impl_xy=tuple(impl_xy),
    )


# ----- static frontend (mount last) -----

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # SPA fallback: any non-API route returns index.html so React Router can handle it.
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
