# Warsha design system

Neighbourhood garage UI. Dark, warm metal, oil, paper. Not generic SaaS.

## Locked brand (do not replace)

| Token | Value | Use |
|-------|-------|-----|
| Background | `#0c0a09` | OLED-adjacent garage black (not pure `#000`) |
| Surface | `#14100e` / `#1a1612` | Cards, elevated chrome |
| Paper | `#f5efe6` | Primary text (≥7:1 on background) |
| Muted | `#c4bbb0` | Secondary text (≥4.5:1) |
| Copper | `#c87941` | Brand metal |
| Copper bright | `#e8a066` | CTA, focus ring, live accents |
| Copper dim | `#8a4f28` | CTA gradient end |
| Success | `#8ef0b8` on `#0f3322` | Paid, ready, online |
| Danger | `#ffb4b4` | Cancel, errors |
| Radius | `16px` cards, `9999px` pills | |
| Easing | `cubic-bezier(0.16, 1, 0.3, 1)` | 150–300ms |

## Type

- Arabic UI: **Noto Sans Arabic** (arm’s-length readable)
- Display / wordmark: **Noto Naskh Arabic**
- English / numbers: **DM Sans**, `tabular-nums` for prices and timers
- Body ≥16px on mobile (avoid iOS input zoom)

## UX rules

- Touch targets ≥44×44px, ≥8px gap
- Visible `:focus-visible` copper ring (never `outline: none` alone)
- `cursor-pointer` on clickable controls
- `prefers-reduced-motion: reduce` disables decorative motion
- Status never by color alone — badge + icon + label
- Bottom nav / composer respect `env(safe-area-inset-*)`
- One primary CTA per screen
