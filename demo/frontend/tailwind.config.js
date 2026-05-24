/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ─────────────────────────────────────────────────────────────────
        // Pure-neutral monochrome ramp. No accent color anywhere in chrome.
        // The only color on the site comes from the data figures (inferno
        // colormap on the UMAP scatter). Headlines and CTAs use depth and
        // weight, not hue.
        // ─────────────────────────────────────────────────────────────────
        bg0:    'oklch(98% 0 0)',   // near-white page bg
        bg1:    'oklch(95% 0 0)',
        bg2:    'oklch(92% 0 0)',
        line1:  'oklch(88% 0 0)',
        line2:  'oklch(78% 0 0)',
        text3:  'oklch(56% 0 0)',
        text2:  'oklch(38% 0 0)',
        text1:  'oklch(22% 0 0)',
        text0:  'oklch(14% 0 0)',   // near-black for headlines + CTAs

        // No `accent`. Use text0 (near-black) where we used to use accent.
        // These aliases stay so older components keep compiling, but they
        // all resolve into the neutral ramp.
        accent:    'oklch(14% 0 0)',
        'accent-2':'oklch(22% 0 0)',
        'accent-d':'oklch(0% 0 0)',

        // Semantic — kept ONLY for state inside data figures.
        warm:      'oklch(56% 0.190 25)',
        pos:       'oklch(56% 0.140 152)',
        neg:       'oklch(56% 0.190 25)',

        ink:       'oklch(98% 0 0)',
        'ink-2':   'oklch(95% 0 0)',
        panel:     'oklch(95% 0 0)',
        'panel-2': 'oklch(92% 0 0)',
        border:    'oklch(88% 0 0)',
        'border-2':'oklch(78% 0 0)',
        muted:     'oklch(56% 0 0)',
        body:      'oklch(38% 0 0)',
        fg:        'oklch(14% 0 0)',
        cool:      'oklch(56% 0 0)',
        success:   'oklch(56% 0.140 152)',
      },
      fontFamily: {
        sans: ['"Inter Tight"', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        display: ['"Chillax"', '"Inter Tight"', '-apple-system', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      letterSpacing: {
        'editorial': '-0.035em',
        'crisp':     '-0.015em',
      },
      transitionTimingFunction: {
        'out-strong':    'cubic-bezier(0.23, 1, 0.32, 1)',
        'in-out-strong': 'cubic-bezier(0.77, 0, 0.175, 1)',
      },
    },
  },
  plugins: [],
}
