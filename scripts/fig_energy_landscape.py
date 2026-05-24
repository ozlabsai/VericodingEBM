"""Generate the 3D energy-landscape figure for the paper.

Hits the demo backend (must be running on http://localhost:8765) to fetch the
same KNN-interpolated energy field that the live UI shows, then renders a
publication-quality 3D matplotlib surface with RdBu_r colormap, soft lighting,
and an optional annotated descent trajectory.

Output: docs/figures/fig_energy_landscape.pdf

Usage:
    uv run uvicorn demo.backend.app:app --port 8765 &
    uv run python scripts/fig_energy_landscape.py
"""
from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import LightSource, Normalize
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (registers 3d projection)
import numpy as np


def fetch(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="http://localhost:8765")
    ap.add_argument("--scope", choices=["impl", "line"], default="impl")
    ap.add_argument("--grid", type=int, default=128)
    ap.add_argument("--bandwidth-mul", type=float, default=15.0,
                    help="KNN bandwidth multiplier on the backend (matches the demo's 'smooth' slider).")
    ap.add_argument("--blur-sigma", type=float, default=2.5,
                    help="Post-smoothing Gaussian sigma (in grid cells) for paper aesthetic.")
    ap.add_argument("--descent-start", nargs=2, type=float, default=None,
                    metavar=("X", "Y"),
                    help="If set, draw an annotated descent trajectory from this point.")
    ap.add_argument("--descent-steps", type=int, default=60)
    ap.add_argument("--out", type=Path, default=Path("docs/figures/fig_energy_landscape.pdf"))
    ap.add_argument("--elev", type=float, default=32, help="3D viewing elevation.")
    ap.add_argument("--azim", type=float, default=-130, help="3D viewing azimuth.")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    qs = urllib.parse.urlencode({
        "scope": args.scope, "grid": args.grid, "bandwidth_mul": args.bandwidth_mul,
    })
    field = fetch(f"{args.backend}/api/energy-field?{qs}")
    print(f"fetched field: grid={field['grid']} bandwidth={field['bandwidth']:.3f}", flush=True)

    grid = field["grid"]
    x_min, x_max = field["x_min"], field["x_max"]
    y_min, y_max = field["y_min"], field["y_max"]
    Z = np.array(field["field"], dtype=np.float32).reshape(grid, grid)
    # Optional post-smoothing for the paper aesthetic. The KNN field is honest
    # but bumpy; an additional Gaussian pass gives the soft-clay look from the
    # reference figure. The descent path is unaffected — it's recomputed
    # server-side on the un-blurred field.
    if args.blur_sigma > 0:
        from scipy.ndimage import gaussian_filter
        Z = gaussian_filter(Z, sigma=args.blur_sigma)
    # Y dimension is bottom-up in field; meshgrid is bottom-up too, so no flip.
    xs = np.linspace(x_min, x_max, grid)
    ys = np.linspace(y_min, y_max, grid)
    X, Y = np.meshgrid(xs, ys)

    # ----- the figure -----
    fig = plt.figure(figsize=(8.5, 5.2))
    ax = fig.add_subplot(111, projection="3d", computed_zorder=False)

    # Soft-shaded surface; LightSource gives the clay-like look from the reference.
    ls = LightSource(azdeg=315, altdeg=40)
    vmin = field["energy_min"]
    vmax = field["energy_max"]
    norm = Normalize(vmin=vmin, vmax=vmax)
    rgb = ls.shade(Z, cmap=cm.RdBu_r, norm=norm, vert_exag=1.2, blend_mode="soft")

    surf = ax.plot_surface(
        X, Y, Z,
        facecolors=rgb,
        rstride=1, cstride=1,
        linewidth=0,
        antialiased=True,
        shade=False,
    )

    # ----- optional descent trajectory -----
    if args.descent_start:
        sx, sy = args.descent_start
        body = json.dumps({
            "scope": args.scope, "x": sx, "y": sy,
            "steps": args.descent_steps, "lr": 0.5,
        }).encode()
        req = urllib.request.Request(
            f"{args.backend}/api/descend",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            traj = json.loads(r.read().decode())["trajectory"]
        tx = np.array([p["x"] for p in traj])
        ty = np.array([p["y"] for p in traj])
        tz = np.array([p["energy"] for p in traj]) + 0.1  # tiny lift so the line sits ON the surface

        # Background dashed projection of the path onto the floor.
        floor_z = np.full_like(tx, vmin - 0.5)
        ax.plot(tx, ty, floor_z, color="#444", linestyle=":", linewidth=1.0, alpha=0.6)

        # The arrow trail itself: split into ~6 discrete segments for readability.
        n_seg = 6
        idxs = np.linspace(0, len(tx) - 1, n_seg + 1).astype(int)
        for i in range(n_seg):
            a, b = idxs[i], idxs[i + 1]
            # White→red gradient along the trail.
            t_frac = i / (n_seg - 1) if n_seg > 1 else 0
            color = (1.0, 1.0 - 0.75 * t_frac, 1.0 - 0.95 * t_frac, 0.95)
            ax.plot(tx[a:b + 1], ty[a:b + 1], tz[a:b + 1],
                    color=color, linewidth=2.5, solid_capstyle="round")

        # Start marker (red arrow head) and end ball (white with red glow).
        ax.scatter([tx[0]], [ty[0]], [tz[0]], color="#d62828", s=80, zorder=5,
                   edgecolor="white", linewidth=1.0)
        ax.scatter([tx[-1]], [ty[-1]], [tz[-1]], color="#ffffff", s=140, zorder=6,
                   edgecolor="#d62828", linewidth=1.8)
        ax.text(tx[0], ty[0], tz[0] + 1.5, "input impl",
                fontsize=8, color="#333", ha="left", va="bottom")
        ax.text(tx[-1], ty[-1], tz[-1] - 1.2, "converged",
                fontsize=8, color="#333", ha="center", va="top")

    # ----- view + cosmetics -----
    ax.view_init(elev=args.elev, azim=args.azim)
    ax.set_xlabel("UMAP-x", fontsize=8, labelpad=-2)
    ax.set_ylabel("UMAP-y", fontsize=8, labelpad=-2)
    ax.set_zlabel("energy  E(x, y)", fontsize=8, labelpad=-2)
    ax.tick_params(axis="both", labelsize=7, pad=-2)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.grid(False)
    ax.set_title(
        "EBM energy landscape over the implementation manifold (run #10)",
        fontsize=10, pad=4,
    )

    # Colorbar.
    mappable = cm.ScalarMappable(norm=norm, cmap=cm.RdBu_r)
    cbar = fig.colorbar(mappable, ax=ax, shrink=0.55, pad=0.05, aspect=18)
    cbar.set_label("energy  (low → safe; high → suspicious)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    plt.tight_layout()
    plt.savefig(args.out, dpi=200, bbox_inches="tight")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
