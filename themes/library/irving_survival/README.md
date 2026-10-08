# Irving Survival

Calm household-preparedness storefront, built on direction 1a of the owner's
2026-10 design canvases (home "product hero", plus the category, product,
calculator, bundles and checkout pages built on it).

- **Palette:** warm grey ground `#F3F2EE`, white surfaces, ink `#121311`, one
  orange signal `#E8590C` (text tone `#B93D06`), green `#2B8A3E` for "ok".
- **Type:** Geist for everything, Geist Mono for labels and figures.
- **Shape:** pill buttons, 24–28 px tiles, no shadows.

## What the theme expects from the store

| Surface | Source |
|---|---|
| Nav "Bundles", home "Ready-made bundles" | the collection with slug `staff-picks`, shown under its own name |
| Nav "Calculator" | the CMS page with slug `calculator` (published) — this theme's `cms/page.html` renders the supply calculator under its title |
| Nav "Readiness" | the CMS page with slug `readiness` — renders the readiness check |
| Home "Shop by system" | top-level categories (shown from three) |
| Home stage | the first featured product with an image; without one, the household kit list |
| Status line | theme setting `status_text` (default: the 105 power-cut line); `show_status_bar` hides it |

## The planning tools

Both run in the browser (`templates/storefront/_irving_tools_script.html`).
The calculator stores nothing. The readiness answers live in the visitor's
localStorage under `irving.readiness.v1` and never reach the server; a visitor
who has not answered sees a dash, not a score. Water and kit figures follow the
UK Government's Prepare guidance (2.5–3 L of drinking water per person per day,
10 L to cook and wash too) and the pages link to it.

## Slots

Same set as `supernatural_shop`: `global_head`, `global_below_body`,
`nav_primary_extra`, `footer_extra` (Shop column), `footer_legal`,
`home_after_rails`, `home_below_grid`, and the PDP / cart / checkout / account
slots. Activate with `MORPHEUS_ACTIVE_THEME=irving_survival` in the instance env.
