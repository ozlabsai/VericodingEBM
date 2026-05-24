"""Precompute all backend API responses to static JSON files for ship-as-site.

Reads:
  demo/backend/data/{impl,line}_manifold.parquet

Writes (into demo/frontend/dist/data/):
  impls.json                — list of all impl points (light: no impl_text)
  lines.json                — list of all line points
  impl_lines/<impl_id>.json — per-impl payload with source code + lines
  energy_field_impl.json    — precomputed KNN-interp grid for impl scope
  energy_field_line.json    — same for line scope

After running this, the static site in dist/ works without uvicorn.
Live scoring (/api/score-line) and dynamic descent (/api/descend) are not
shipped — the frontend should fall back to a "enable backend for live mode"
notice for those features.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "demo" / "backend"))

import numpy as np
import pyarrow.parquet as pq
from sklearn.neighbors import NearestNeighbors

DATA = REPO / "demo/backend/data"
# Vite copies anything in `public/` into `dist/` at build time. Targeting
# `public/data/` instead of `dist/data/` makes the precompute survive a
# subsequent `vite build`.
OUT = REPO / "demo/frontend/public/data"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "impl_lines").mkdir(parents=True, exist_ok=True)


def _build_field(rows, energy_key, grid=96, arrow_grid=24, k=20, bandwidth_mul=1.2, scope="impl"):
    coords = np.array([[r["x"], r["y"]] for r in rows], dtype=np.float32)
    energies = np.array([r[energy_key] for r in rows], dtype=np.float32)
    x_min, x_max = float(coords[:, 0].min()), float(coords[:, 0].max())
    y_min, y_max = float(coords[:, 1].min()), float(coords[:, 1].max())
    dx = (x_max - x_min) * 0.05; dy = (y_max - y_min) * 0.05
    x_min -= dx; x_max += dx; y_min -= dy; y_max += dy

    sub_n = min(coords.shape[0], 2000)
    nn_sample = NearestNeighbors(n_neighbors=6).fit(coords)
    d, _ = nn_sample.kneighbors(coords[:sub_n])
    bandwidth = float(np.median(d[:, 1:])) * bandwidth_mul or 0.1

    xs = np.linspace(x_min, x_max, grid, dtype=np.float32)
    ys = np.linspace(y_min, y_max, grid, dtype=np.float32)
    gx, gy = np.meshgrid(xs, ys)
    grid_pts = np.stack([gx.ravel(), gy.ravel()], axis=1)
    nn = NearestNeighbors(n_neighbors=min(k, coords.shape[0])).fit(coords)
    dists, idx = nn.kneighbors(grid_pts)
    weights = np.exp(-(dists ** 2) / (2 * bandwidth ** 2))
    weights_sum = weights.sum(axis=1, keepdims=True).clip(min=1e-8)
    field = (weights * energies[idx]).sum(axis=1) / weights_sum.squeeze(1)
    field = field.astype(np.float32)
    energy_min = float(np.quantile(field, 0.05))
    energy_max = float(np.quantile(field, 0.95))

    f2d = field.reshape(grid, grid)
    gy_field, gx_field = np.gradient(f2d)
    arrows = []
    step = max(1, grid // arrow_grid)
    max_grad = float(max(np.abs(gx_field).max(), np.abs(gy_field).max(), 1e-8))
    arrow_len = 0.8 * max((x_max - x_min) / arrow_grid, (y_max - y_min) / arrow_grid)
    for i in range(0, grid, step):
        for j in range(0, grid, step):
            ux = -float(gx_field[i, j]) / max_grad * arrow_len
            uy = -float(gy_field[i, j]) / max_grad * arrow_len
            cx = float(xs[j]); cy = float(ys[i])
            arrows.append({"x0": cx, "y0": cy, "x1": cx + ux, "y1": cy + uy})

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


def main():
    print(f"loading {DATA}/impl_manifold.parquet ...")
    impls = pq.read_table(DATA / "impl_manifold.parquet").to_pylist()
    lines = pq.read_table(DATA / "line_manifold.parquet").to_pylist()
    print(f"  {len(impls)} impls, {len(lines)} lines")

    # impls.json — light payload
    impls_light = [
        {"impl_id": r["impl_id"], "spec_id": r["spec_id"],
         "status": r["status"], "whole_impl_energy": r["whole_impl_energy"],
         "n_lines": r["n_lines"], "has_pass_sibling": r["has_pass_sibling"],
         "x": r["x"], "y": r["y"]}
        for r in impls
    ]
    (OUT / "impls.json").write_text(json.dumps(impls_light))
    print(f"wrote {OUT}/impls.json ({len(impls_light)} entries)")

    # lines.json — all line points
    lines_light = [
        {"impl_id": r["impl_id"], "line_idx": r["line_idx"],
         "line_text": r["line_text"], "energy": r["energy"],
         "is_buggy": r["is_buggy"], "impl_status": r["impl_status"],
         "x": r["x"], "y": r["y"]}
        for r in lines
    ]
    (OUT / "lines.json").write_text(json.dumps(lines_light))
    print(f"wrote {OUT}/lines.json ({len(lines_light)} entries)")

    # impl_lines/<impl_id>.json — heavy payload per impl
    impl_by_id = {r["impl_id"]: r for r in impls}
    lines_by_impl: dict[str, list[dict]] = {}
    for r in lines:
        lines_by_impl.setdefault(r["impl_id"], []).append(r)

    for impl_id, impl in impl_by_id.items():
        impl_lines = sorted(lines_by_impl.get(impl_id, []), key=lambda x: x["line_idx"])
        payload = {
            "impl": {"impl_id": impl["impl_id"], "spec_id": impl["spec_id"],
                     "status": impl["status"],
                     "whole_impl_energy": impl["whole_impl_energy"],
                     "spec_text": impl["spec_text"], "impl_text": impl["impl_text"]},
            "lines": [{"line_idx": r["line_idx"], "line_text": r["line_text"],
                       "energy": r["energy"], "is_buggy": r["is_buggy"],
                       "x": r["x"], "y": r["y"]} for r in impl_lines],
        }
        # Filename-safe impl_id (slashes etc).
        safe = impl_id.replace("/", "__").replace("\\", "__")
        (OUT / "impl_lines" / f"{safe}.json").write_text(json.dumps(payload))
    print(f"wrote {len(impl_by_id)} impl_lines/*.json files")

    # Manifest mapping impl_id -> filename so the frontend can resolve.
    manifest = {iid: iid.replace("/", "__").replace("\\", "__") + ".json"
                for iid in impl_by_id}
    (OUT / "impl_lines_manifest.json").write_text(json.dumps(manifest))
    print(f"wrote {OUT}/impl_lines_manifest.json")

    # Energy fields (impl + line scope).
    print("computing energy field (impl scope, grid=96) ...")
    (OUT / "energy_field_impl.json").write_text(json.dumps(
        _build_field(impls, "whole_impl_energy", scope="impl")))
    print("computing energy field (line scope, grid=96) ...")
    (OUT / "energy_field_line.json").write_text(json.dumps(
        _build_field(lines, "energy", scope="line")))
    print("done.")


if __name__ == "__main__":
    main()
