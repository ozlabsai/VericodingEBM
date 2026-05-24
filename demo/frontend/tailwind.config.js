/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ─────────────────────────────────────────────────────────────────
        // LIGHT-MODE palette anchored on board #5 (Suraj boards):
        //   White Solid + Veiling Waterfalls (bg)
        //   Fibonacci Blue #112358 → text/ink anchor
        //   Dynamic Blue   #0192C6 → single accent (data/metric semantic)
        //   Lemon Pie      #F1FF62 → reserved for callouts only (unused yet)
        //
        // Hue 245 throughout (slight cool tint) so neutrals carry the same
        // navy undertone. Chroma tiny on neutrals; accent at full chroma.
        // ─────────────────────────────────────────────────────────────────
        bg0:    'oklch(98% 0.005 245)',   // page background  (~White Solid #F4F5FA)
        bg1:    'oklch(95% 0.010 245)',   // raised panel / sub-band  (~Veiling Waterfalls #D4EAFF tint)
        bg2:    'oklch(91% 0.015 245)',   // hover / pressed
        line1:  'oklch(86% 0.020 245)',   // 1px hairline
        line2:  'oklch(76% 0.025 245)',   // emphasised hairline
        text3:  'oklch(52% 0.045 245)',   // muted text
        text2:  'oklch(36% 0.060 245)',   // body text
        text1:  'oklch(22% 0.075 245)',   // high-emphasis text
        text0:  'oklch(15% 0.090 245)',   // headlines (~Fibonacci Blue #112358)

        // ONE accent — Dynamic Blue. Saturated mid-lightness cyan-blue.
        // Universal "data / metric / chart" semantic. Distinct from the
        // AI-default cobalt because it leans toward cyan, not violet.
        accent:    'oklch(62% 0.150 230)',  // ~Dynamic Blue #0192C6
        'accent-2':'oklch(72% 0.120 230)',
        'accent-d':'oklch(52% 0.165 235)',  // pressed / strong

        // Semantic — only for state.
        //   pos = Fun Green from board #7 — natural "good result"
        //   neg = deep crimson — kept distinct from accent hue
        pos: 'oklch(48% 0.130 152)',        // ~Fun Green #15633D
        neg: 'oklch(52% 0.205 18)',         // deep crimson

        // Legacy aliases.
        ink:       'oklch(98% 0.005 245)',
        'ink-2':   'oklch(95% 0.010 245)',
        panel:     'oklch(95% 0.010 245)',
        'panel-2': 'oklch(91% 0.015 245)',
        border:    'oklch(86% 0.020 245)',
        'border-2':'oklch(76% 0.025 245)',
        muted:     'oklch(52% 0.045 245)',
        body:      'oklch(36% 0.060 245)',
        fg:        'oklch(15% 0.090 245)',
        warm:      'oklch(52% 0.205 18)',
        cool:      'oklch(62% 0.150 230)',
        success:   'oklch(48% 0.130 152)',
      },
      fontFamily: {
        // Work Sans (Google Fonts, OFL) — body default. Humanist sans, very
        // legible at small sizes, more character than Inter.
        sans: ['"Work Sans"', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        // Clash Grotesk (Fontshare, ITF FFL) — display only. h1, h2, CTAs,
        // the wordmark, mono-uppercase eyebrow labels.
        display: ['"Clash Grotesk"', '"Work Sans"', '-apple-system', 'system-ui', 'sans-serif'],
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
