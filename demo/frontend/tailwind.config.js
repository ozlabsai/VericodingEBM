/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // OKLCH neutrals tinted slightly warm so the surface doesn't read as the
        // default cold-blue SaaS dark.
        ink:        'oklch(15% 0.012 250)',
        'ink-2':    'oklch(18% 0.012 250)',
        panel:      'oklch(22% 0.014 250)',
        'panel-2':  'oklch(26% 0.016 250)',
        border:     'oklch(32% 0.018 250)',
        'border-2': 'oklch(40% 0.020 250)',
        muted:      'oklch(58% 0.015 250)',
        body:       'oklch(78% 0.012 250)',
        fg:         'oklch(96% 0.005 250)',

        // Brand accent: amber-orange, committed (not the AI-default cold-blue).
        accent:     'oklch(74% 0.165 65)',
        'accent-2': 'oklch(82% 0.140 65)',
        'accent-d': 'oklch(58% 0.180 50)',

        // Semantic
        warm:       'oklch(64% 0.190 25)',
        cool:       'oklch(72% 0.140 220)',
        success:    'oklch(72% 0.155 152)',
      },
      fontFamily: {
        sans: ['"Inter Tight"', '-apple-system', 'BlinkMacSystemFont', 'Inter', '"Segoe UI"', 'system-ui', 'sans-serif'],
        serif: ['"Instrument Serif"', 'ui-serif', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      letterSpacing: {
        'editorial': '-0.04em',
        'tight-x':   '-0.015em',
      },
      transitionTimingFunction: {
        'out-expo':  'cubic-bezier(0.16, 1, 0.3, 1)',
        'out-quart': 'cubic-bezier(0.25, 1, 0.5, 1)',
      },
    },
  },
  plugins: [],
}
