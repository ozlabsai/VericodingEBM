"""Per-line energy heatmap renderer.

Given a (spec, impl, per_line_energies) tuple, produce:
  - An ANSI-colored text rendering (green low energy -> red high) for the terminal
  - An HTML rendering with inline background colors for the writeup hero image
  - An SVG fallback (no matplotlib dep) suitable for embedding in the PDF

We deliberately keep this dependency-light: no matplotlib at runtime. The colors
are simple HSL interpolation: hue=120 (green) at min energy -> hue=0 (red) at
max energy, both via z-score within the impl so the scale is impl-relative.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass


@dataclass
class HeatmapInput:
    """One impl's data for visualization. ``per_line_energies`` is aligned with
    ``scorable_lines`` (one energy per scorable line, in source order).
    """

    spec_text: str
    scorable_lines: list[str]
    per_line_energies: list[float]
    buggy_line_indices: list[int]  # for "ground truth" overlay in eval-time viz
    title: str = "Per-line energy"


def _zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / max(1, len(values))
    sd = math.sqrt(var) or 1.0
    return [(v - mean) / sd for v in values]


def _color_for_z(z: float) -> str:
    """Return CSS rgb(...) string. Green (low) -> Yellow -> Red (high)."""
    # Map z in [-2, 2] to hue in [120, 0]; clamp.
    z_clamped = max(-2.0, min(2.0, z))
    hue = 120.0 * (1.0 - (z_clamped + 2.0) / 4.0)
    # Convert HSL(hue, 70%, 80%) to RGB by hand.
    s, l = 0.70, 0.85
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((hue / 60.0) % 2 - 1))
    m = l - c / 2
    if hue < 60:
        r, g, b = c, x, 0
    elif hue < 120:
        r, g, b = x, c, 0
    else:
        r, g, b = 0, c, x
    r, g, b = int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
    return f"rgb({r},{g},{b})"


def _color_for_z_ansi(z: float) -> str:
    """ANSI 256-color background code for terminal preview."""
    # 16-231 = 6x6x6 color cube; we use a green->red gradient.
    # green = 46, yellow = 226, red = 196.
    z_clamped = max(-2.0, min(2.0, z))
    t = (z_clamped + 2.0) / 4.0  # 0..1, 0 = green
    if t < 0.5:
        # 46 (green) -> 226 (yellow)
        code = int(46 + (226 - 46) * (t / 0.5))
    else:
        # 226 -> 196 (red)
        code = int(226 + (196 - 226) * ((t - 0.5) / 0.5))
    return f"\x1b[48;5;{code}m\x1b[30m"


_ANSI_RESET = "\x1b[0m"


def render_text(h: HeatmapInput) -> str:
    """ANSI-colored terminal preview. Each line gets its own background color."""
    if not h.per_line_energies:
        return "(no energies)"
    z = _zscore(h.per_line_energies)
    buggy = set(h.buggy_line_indices)
    out_lines = [f"== {h.title} ==", "", "[spec]"]
    for s_line in h.spec_text.splitlines():
        out_lines.append(f"   {s_line}")
    out_lines.append("")
    out_lines.append("[impl]")
    for i, (line, e, zi) in enumerate(zip(h.scorable_lines, h.per_line_energies, z)):
        marker = "*" if i in buggy else " "
        col = _color_for_z_ansi(zi)
        out_lines.append(f"{i:3d} {marker} {col}E={e:+.3f} z={zi:+.2f}{_ANSI_RESET}  {line}")
    return "\n".join(out_lines)


def render_html(h: HeatmapInput) -> str:
    """HTML rendering with inline background colors. Use this for the writeup."""
    z = _zscore(h.per_line_energies)
    buggy = set(h.buggy_line_indices)
    rows = []
    for i, (line, e, zi) in enumerate(zip(h.scorable_lines, h.per_line_energies, z)):
        bg = _color_for_z(zi)
        marker = "&#x2735;" if i in buggy else "&nbsp;"
        rows.append(
            f"<tr><td class='num'>{i:3d}</td>"
            f"<td class='mark'>{marker}</td>"
            f"<td class='e'>{e:+.3f}</td>"
            f"<td class='z'>{zi:+.2f}</td>"
            f"<td class='line' style='background:{bg};'><pre>{html.escape(line)}</pre></td></tr>"
        )
    spec_html = html.escape(h.spec_text)
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<title>{html.escape(h.title)}</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 1100px; margin: 2em auto; }}
h1 {{ font-size: 1.4em; }}
.spec {{ background: #f0f0f0; padding: 1em; border-radius: 6px; white-space: pre-wrap; font-family: monospace; font-size: 0.9em; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.92em; }}
td {{ padding: 0.2em 0.5em; vertical-align: top; }}
td.num {{ text-align: right; color: #888; font-family: monospace; }}
td.mark {{ width: 1em; text-align: center; color: #c00; font-weight: bold; }}
td.e, td.z {{ font-family: monospace; color: #555; }}
td.line pre {{ margin: 0; font-family: 'SF Mono', 'Consolas', monospace; white-space: pre-wrap; }}
</style></head><body>
<h1>{html.escape(h.title)}</h1>
<div class='spec'>{spec_html}</div>
<table><thead><tr><th>line</th><th></th><th>E</th><th>z</th><th>impl source (color = energy)</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<p style='color:#666;font-size:0.85em;'>Cells colored by z-score of per-line energy within this impl: green = low, red = high. &#x2735; marks ground-truth buggy lines (where known).</p>
</body></html>"""
