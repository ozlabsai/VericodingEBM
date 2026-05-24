/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ─────────────────────────────────────────────────────────────────
        // Palette: Bavarian Gentian (deep indigo) + Opal Flame (warm red).
        // From the Suraj design boards. All values OKLCH; ramp is perceptually
        // spaced (equal lightness deltas), chroma scales down toward extremes.
        //
        // The dark anchor is dimmed from the source #20006D into the 12-22%
        // lightness range so it reads as "near-black with an indigo soul"
        // rather than as a saturated purple field. Hue 285 throughout for
        // cohesion.
        // ─────────────────────────────────────────────────────────────────
        bg0:    'oklch(11% 0.045 285)',   // page background
        bg1:    'oklch(15% 0.055 285)',   // panel / section
        bg2:    'oklch(20% 0.065 285)',   // hover / pressed surface
        line1:  'oklch(26% 0.055 285)',   // 1px hairline
        line2:  'oklch(34% 0.055 285)',   // emphasised hairline
        text3:  'oklch(58% 0.025 285)',   // muted text
        text2:  'oklch(80% 0.020 285)',   // body text  (Violet Water-ish)
        text1:  'oklch(93% 0.010 285)',   // high-emphasis text
        text0:  'oklch(98% 0.005 285)',   // headlines  (Gram's Hair-ish)

        // ONE accent — Opal Flame. High contrast on the indigo ramp; warm-red
        // distinguishes it from the AI-default amber AND from the previous
        // Lichen Green.
        accent:    'oklch(70% 0.165 27)',  // ~#E95C4B
        'accent-2':'oklch(78% 0.135 27)',
        'accent-d':'oklch(60% 0.180 27)',

        // Semantic — used only for state, not decoration.
        // pos: Chilly Spice (warm pink) — softer than the accent so they coexist.
        // neg: deep crimson — distinct from accent, reserved for failure/regression.
        pos: 'oklch(80% 0.105 22)',        // ~#FD9989 (Chilly Spice)
        neg: 'oklch(62% 0.190 18)',        // deep crimson, distinct from accent

        // Legacy aliases (kept so older components still compile during
        // gradual migration). All point into the indigo ramp.
        ink:       'oklch(11% 0.045 285)',
        'ink-2':   'oklch(15% 0.055 285)',
        panel:     'oklch(20% 0.065 285)',
        'panel-2': 'oklch(26% 0.055 285)',
        border:    'oklch(26% 0.055 285)',
        'border-2':'oklch(34% 0.055 285)',
        muted:     'oklch(58% 0.025 285)',
        body:      'oklch(80% 0.020 285)',
        fg:        'oklch(93% 0.010 285)',
        warm:      'oklch(62% 0.190 18)',
        cool:      'oklch(72% 0.140 240)',
        success:   'oklch(80% 0.105 22)',
      },
      fontFamily: {
        // Clash Grotesk via Fontshare (free, OFL-equivalent license).
        // Distinctive geometric grotesk — breaks the AI-default Inter reflex.
        sans: ['"Clash Grotesk"', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      letterSpacing: {
        'editorial': '-0.045em',
        'crisp':     '-0.018em',
      },
      transitionTimingFunction: {
        // Emil's strong ease-out and ease-in-out
        'out-strong':    'cubic-bezier(0.23, 1, 0.32, 1)',
        'in-out-strong': 'cubic-bezier(0.77, 0, 0.175, 1)',
      },
    },
  },
  plugins: [],
}
