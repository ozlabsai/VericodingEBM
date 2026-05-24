/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Committed monochrome OKLCH ramp. Hue 250 (very slight cool tint),
        // chroma kept low so neutrals stay neutral. Single accent below.
        // Stops chosen perceptually (~equal lightness deltas), not arbitrary hex.
        bg0:    'oklch(13% 0.010 250)',
        bg1:    'oklch(16% 0.010 250)',
        bg2:    'oklch(20% 0.012 250)',
        line1:  'oklch(26% 0.012 250)',
        line2:  'oklch(34% 0.012 250)',
        text3:  'oklch(50% 0.010 250)',
        text2:  'oklch(70% 0.008 250)',
        text1:  'oklch(92% 0.005 250)',
        text0:  'oklch(98% 0.003 250)',

        // ONE accent. Lichen Green — high contrast on the cool dark ramp,
        // not the AI-default purple/blue, not the previous amber.
        accent:    'oklch(78% 0.155 152)',
        'accent-d':'oklch(62% 0.165 152)',
        'accent-2':'oklch(86% 0.140 152)',

        // Semantic — used only for state, not decoration.
        pos: 'oklch(78% 0.155 152)',   // success / model-wins
        neg: 'oklch(66% 0.180 27)',    // fail / regression

        // Legacy aliases (kept so non-landing pages still compile during the
        // gradual migration). All point into the new monochrome ramp.
        ink:       'oklch(13% 0.010 250)',
        'ink-2':   'oklch(16% 0.010 250)',
        panel:     'oklch(20% 0.012 250)',
        'panel-2': 'oklch(26% 0.012 250)',
        border:    'oklch(26% 0.012 250)',
        'border-2':'oklch(34% 0.012 250)',
        muted:     'oklch(50% 0.010 250)',
        body:      'oklch(70% 0.008 250)',
        fg:        'oklch(92% 0.005 250)',
        warm:      'oklch(66% 0.180 27)',
        cool:      'oklch(72% 0.140 220)',
        success:   'oklch(78% 0.155 152)',
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
