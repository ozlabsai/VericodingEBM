/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ─────────────────────────────────────────────────────────────────
        // LIGHT-MODE palette: Gram's Hair (off-white) anchor +
        // Bavarian Gentian (deep indigo) for text + Opal Flame (warm red)
        // for the single accent. From the Suraj design boards.
        //
        // The ramp goes light → dark for bg, dark → light for text.
        // Hue 285 throughout so neutrals carry the same indigo undertone
        // as the accent palette. Chroma kept tiny on neutrals.
        // ─────────────────────────────────────────────────────────────────
        bg0:    'oklch(97% 0.004 285)',   // page background  (~Gram's Hair #F5F6F7)
        bg1:    'oklch(94% 0.006 285)',   // raised panel / sub-band
        bg2:    'oklch(90% 0.010 285)',   // hover / pressed
        line1:  'oklch(86% 0.012 285)',   // 1px hairline
        line2:  'oklch(78% 0.015 285)',   // emphasised hairline
        text3:  'oklch(54% 0.030 285)',   // muted text
        text2:  'oklch(38% 0.045 285)',   // body text
        text1:  'oklch(22% 0.055 285)',   // high-emphasis text
        text0:  'oklch(15% 0.060 285)',   // headlines (Bavarian Gentian, dimmed)

        // ONE accent — Opal Flame. High contrast on off-white, warm-red
        // distinguishes it from the AI-default cobalt-blue.
        accent:    'oklch(62% 0.180 27)',  // a touch deeper than dark-mode use for AA contrast
        'accent-2':'oklch(70% 0.160 27)',
        'accent-d':'oklch(54% 0.195 27)',

        // Semantic — used only for state, not decoration.
        // pos: a calm green (not the bright lichen) so it sits well against off-white
        // neg: deep crimson, kept distinct from the accent in hue
        pos: 'oklch(50% 0.140 152)',
        neg: 'oklch(52% 0.205 18)',

        // Legacy aliases.
        ink:       'oklch(97% 0.004 285)',
        'ink-2':   'oklch(94% 0.006 285)',
        panel:     'oklch(94% 0.006 285)',
        'panel-2': 'oklch(90% 0.010 285)',
        border:    'oklch(86% 0.012 285)',
        'border-2':'oklch(78% 0.015 285)',
        muted:     'oklch(54% 0.030 285)',
        body:      'oklch(38% 0.045 285)',
        fg:        'oklch(15% 0.060 285)',
        warm:      'oklch(52% 0.205 18)',
        cool:      'oklch(50% 0.140 240)',
        success:   'oklch(50% 0.140 152)',
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
