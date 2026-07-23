# Design — Kingdee Sync Tool

A locked design system for this app. Every page redesign reads this file before
emitting code. Do not regenerate per page — extend or amend this file when the
system needs to grow.

## Genre
modern-minimal

## Macrostructure family
- Dashboard pages (Overview, Stats): Stat-Led — grid cards, chart sections, data-first
- App pages (Sync, Forms, History, Settings, Diagnostics): Workbench — tool-oriented, sidebar + content area, high information density
- Detail pages (HistoryDetail): Document — vertical scroll, single-subject focus

## Theme
- `--color-paper`   oklch(100% 0 0)              /* white */
- `--color-paper-2` oklch(97% 0.004 250)         /* soft blue-grey */
- `--color-ink`     oklch(17% 0.022 260)         /* deep navy */
- `--color-ink-2`   oklch(32% 0.03 260)          /* muted navy */
- `--color-rule`    oklch(88% 0.01 250)          /* hairline */
- `--color-accent`  oklch(56% 0.185 255)         /* professional blue */
- `--color-accent-2` oklch(48% 0.16 255)         /* accent hover */
- `--color-focus`   oklch(56% 0.185 255)         /* focus ring */
- `--color-success` oklch(62% 0.13 145)          /* green */
- `--color-warning` oklch(76% 0.14 85)           /* amber */
- `--color-critical` oklch(62% 0.18 25)          /* red */

## Typography
- Display: Inter 600, style normal
- Body:    Inter 400
- Mono:    JetBrains Mono 400
- Display tracking: -0.02em
- Type scale:
  - --text-display: clamp(1.75rem, 2.5vw + 1rem, 2.5rem)
  - --text-xl: 1.375rem
  - --text-lg: 1.125rem
  - --text-md: 0.9375rem
  - --text-sm: 0.8125rem
  - --text-xs: 0.6875rem

## Spacing
4-point named scale. Values in tokens.css. Pages must use named tokens, never raw values.
- --space-3xs: 0.25rem (4px)
- --space-2xs: 0.5rem (8px)
- --space-xs:  0.75rem (12px)
- --space-sm:  1rem (16px)
- --space-md:  1.5rem (24px)
- --space-lg:  2rem (32px)
- --space-xl:  3rem (48px)
- --space-2xl: 4rem (64px)

## Radius
- --radius-sm: 6px
- --radius-md: 8px
- --radius-lg: 12px
- --radius-xl: 16px
- --radius-full: 999px

## Motion
- Easings:
  - --ease-out: cubic-bezier(0.16, 1, 0.3, 1)
  - --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1)
- Durations:
  - --dur-fast: 120ms
  - --dur-short: 200ms
  - --dur-med: 300ms
- Reveal pattern: fade only (no slide, no scale on load)
- Reduced-motion fallback: opacity-only, ≤ 150ms

## Microinteractions stance
- Silent success (no celebratory toasts)
- Hover delay 800ms · focus delay 0ms
- Button press: translateY(1px) + shadow decrease, 120ms
- Card hover: subtle shadow lift, 200ms

## CTA voice
- Primary CTA: filled accent, rounded-md, px-4 py-2, bold, text-white
- Secondary CTA: outline rule, rounded-md, px-4 py-2, medium, text-ink
- Ghost: transparent, text-ink-2, hover: paper-2 bg

## Nav archetype
N3 Side-rail:
- Left vertical rail, 56px min-width when collapsed, 220px when expanded
- Logo top-left, nav items with icons, active indicator (accent left border)
- Status badge at bottom

## Per-page allowances
- Dashboard pages MAY use ECharts with theme-aligned colors
- App pages MUST NOT use enrichment — function carries the page
- All pages: typography and spacing from this system only

## What pages MUST share
- The accent colour and its placement (≤ 5% per viewport)
- Inter + JetBrains Mono fonts
- CTA voice (button shape, border-radius, padding rhythm)
- Side-rail navigation
- Section heading style: uppercase tracking-wide label + bold title

## What pages MAY differ on
- Macrostructure within the page-type family
- Card layout density (dashboard vs app)
- ECharts theme on dashboard pages

## Exports

### tokens.css
```css
:root {
  --color-paper:      oklch(100% 0 0);
  --color-paper-2:    oklch(97% 0.004 250);
  --color-ink:        oklch(17% 0.022 260);
  --color-ink-2:      oklch(32% 0.03 260);
  --color-rule:       oklch(88% 0.01 250);
  --color-accent:     oklch(56% 0.185 255);
  --color-accent-2:   oklch(48% 0.16 255);
  --color-focus:      oklch(56% 0.185 255);
  --color-success:    oklch(62% 0.13 145);
  --color-warning:    oklch(76% 0.14 85);
  --color-critical:   oklch(62% 0.18 25);

  --font-display: "Inter", system-ui, sans-serif;
  --font-body:    "Inter", system-ui, sans-serif;
  --font-mono:    "JetBrains Mono", ui-monospace, monospace;

  --space-3xs: 0.25rem; --space-2xs: 0.5rem; --space-xs: 0.75rem;
  --space-sm:  1rem;    --space-md:  1.5rem; --space-lg: 2rem;
  --space-xl:  3rem;    --space-2xl: 4rem;

  --text-display: clamp(1.75rem, 2.5vw + 1rem, 2.5rem);
  --text-xl: 1.375rem; --text-lg: 1.125rem; --text-md: 0.9375rem;
  --text-sm: 0.8125rem; --text-xs: 0.6875rem;

  --radius-sm: 6px; --radius-md: 8px; --radius-lg: 12px; --radius-xl: 16px; --radius-full: 999px;

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-fast: 120ms; --dur-short: 200ms; --dur-med: 300ms;
}
```

### Tailwind v4 @theme
```css
@theme {
  --color-paper:   oklch(100% 0 0);
  --color-paper-2: oklch(97% 0.004 250);
  --color-ink:     oklch(17% 0.022 260);
  --color-ink-2:   oklch(32% 0.03 260);
  --color-rule:    oklch(88% 0.01 250);
  --color-accent:  oklch(56% 0.185 255);
  --color-success: oklch(62% 0.13 145);
  --color-warning: oklch(76% 0.14 85);
  --color-critical: oklch(62% 0.18 25);
  --font-sans:     "Inter", system-ui, sans-serif;
  --font-mono:     "JetBrains Mono", ui-monospace, monospace;
}
```

### DTCG tokens.json
```json
{
  "color": {
    "paper":    { "$value": "oklch(100% 0 0)", "$type": "color" },
    "ink":      { "$value": "oklch(17% 0.022 260)", "$type": "color" },
    "accent":   { "$value": "oklch(56% 0.185 255)", "$type": "color" },
    "success":  { "$value": "oklch(62% 0.13 145)", "$type": "color" },
    "warning":  { "$value": "oklch(76% 0.14 85)", "$type": "color" },
    "critical": { "$value": "oklch(62% 0.18 25)", "$type": "color" }
  },
  "font": {
    "display": { "$value": "Inter", "$type": "fontFamily" },
    "body":    { "$value": "Inter", "$type": "fontFamily" },
    "mono":    { "$value": "JetBrains Mono", "$type": "fontFamily" }
  }
}
```

### shadcn/ui CSS variables
```css
:root {
  --background:        100 0 0;
  --foreground:        17  0.022 260;
  --primary:           56  0.185 255;
  --primary-foreground: 100 0 0;
  --muted:             97  0.004 250;
  --muted-foreground:  32  0.03 260;
  --border:            88  0.01 250;
  --ring:              56  0.185 255;
  --radius:            8px;
}
```
