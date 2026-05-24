/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ─────────────────────────────────────────────────────────────────
        // LIGHT-MODE pastel palette anchored on board #4:
        //   Ice Chip            #F3F6F6 → bg
        //   Celestial Powder    #A3E4FA → secondary surface
        //   Marshmallow Blue    #90D6F9 → accent (data/chart)
        //   Cotton Candy        #FFBCD9 → callout / pos
        //   Pink Ciklet         #FFA8C5 → secondary callout
        //   Black Box           #0F282F → text/ink anchor (deep petrol-green near-black)
        //
        // Bg ramp hue 200 (cyan-cool), text/ink hue 200 too. Accent kept
        // mid-lightness so it pops against off-white. Black Box has a slight
        // petrol-green tint that pairs cleanly with cyan AND pink callouts.
        // ─────────────────────────────────────────────────────────────────
        bg0:    'oklch(97% 0.006 200)',   // page background  (~Ice Chip #F3F6F6)
        bg1:    'oklch(95% 0.010 200)',   // raised panel
        bg2:    'oklch(92% 0.020 200)',   // hover / pressed
        line1:  'oklch(88% 0.020 200)',   // 1px hairline
        line2:  'oklch(80% 0.030 200)',   // emphasised hairline
        text3:  'oklch(54% 0.030 200)',   // muted text
        text2:  'oklch(36% 0.045 200)',   // body text
        text1:  'oklch(24% 0.040 200)',   // high-emphasis text
        text0:  'oklch(20% 0.035 200)',   // headlines (~Black Box #0F282F)

        accent:    'oklch(72% 0.130 220)',  // ~Marshmallow Blue, deepened for contrast
        'accent-2':'oklch(82% 0.100 220)',  // ~Celestial Powder territory
        'accent-d':'oklch(60% 0.155 220)',  // pressed / strong

        // Secondary callout — Pink Ciklet.
        warm:      'oklch(80% 0.110 12)',

        // pos = pinkish-rose for wins (matches pastel-editorial vibe);
        // neg = deep crimson, distinct from accent + pos.
        pos: 'oklch(72% 0.140 350)',
        neg: 'oklch(56% 0.195 22)',

        // Legacy aliases.
        ink:       'oklch(97% 0.006 200)',
        'ink-2':   'oklch(95% 0.010 200)',
        panel:     'oklch(95% 0.010 200)',
        'panel-2': 'oklch(92% 0.020 200)',
        border:    'oklch(88% 0.020 200)',
        'border-2':'oklch(80% 0.030 200)',
        muted:     'oklch(54% 0.030 200)',
        body:      'oklch(36% 0.045 200)',
        fg:        'oklch(20% 0.035 200)',
        cool:      'oklch(72% 0.130 220)',
        success:   'oklch(72% 0.140 350)',
      },
      fontFamily: {
        // General Sans (Fontshare, ITF FFL) — body, humanist.
        sans: ['"General Sans"', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        // Sentient (Fontshare, ITF FFL) — editorial display serif.
        display: ['"Sentient"', 'ui-serif', 'Georgia', 'serif'],
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
