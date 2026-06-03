# Affiliate widget — white-label + display control (spec)

Created 2026-06-03. For a fresh session. Goal: give affiliates real control
over the **embeddable shop widget** they place on other sites — styling,
white-labeling, and which fields/digits show — plus a richer affiliate
dashboard UI. Start here (most self-contained), then do vendor control.

## Why
The widget (`/affiliates/embed/<key>` iframe + `.js` snippet) currently renders
a fixed look. Affiliates embedding it elsewhere need it to match their site
and to drop the "powered by" mark (white-label). Requested by the owner.

## First, read (don't assume)
- `plugins/installed/affiliates/models.py` → the **`AffiliateWidget`** model:
  list its existing fields (does it already have a `config`/JSON or style
  columns? a `key`? an FK to `Affiliate`?).
- `plugins/installed/affiliates/urls.py` lines ~21–29: `widgets`, `edit_widget`,
  `embed_iframe`, `embed_js`, `widget_json` routes.
- The embed views (`affiliates/embed_views.py` or similar) — how
  `embed_iframe` / `embed_js` / `widget_json` render today + where the markup
  + inline CSS live.
- `affiliates/templates/affiliates/widgets.html` + `edit_widget` template +
  the embed template — the current editor + rendered widget.

## Scope — per-widget config (store on AffiliateWidget; add a JSONField if none)
Editor form fields (in `edit_widget`), each surfaced into the embed render:
- **Theme:** accent color, background, text color, font family (or "match my
  site" = inherit), border radius, card/shadow on/off.
- **Layout:** grid vs horizontal rail; columns; number of products (digits).
- **Fields:** toggles for price, "From" prefix, author/byline, badges, CTA label.
- **White-label:** hide the "powered by Dot Books" footer (boolean); custom
  heading text; custom CTA text + target.
- **Behavior:** open links in new tab; UTM/affiliate code already injected.

Render path: `embed_iframe` (full HTML doc with `<style>` from config) and
`widget_json` (so the `.js` snippet builds DOM client-side) must BOTH honor the
same config. Centralize config→style in one helper (`_widget_style(widget)`)
so iframe + JSON + JS agree (same lesson as `metafields/identifiers.py`).

## Implementation steps (each with a verify checkpoint)
1. Read the 4 areas above; confirm `AffiliateWidget` fields. → verify: note the
   real field names + whether a JSON config column exists.
2. Add config storage (JSONField `style` if absent) + migration. → verify:
   `makemigrations affiliates` clean; system check passes.
3. `edit_widget` form + template: the controls above, pre-filled, saved to the
   widget. → verify: save round-trips; re-open shows values.
4. `_widget_style(widget)` helper + apply in `embed_iframe`, `widget_json`,
   `embed_js`. → verify: change a color in the editor → embed reflects it;
   white-label toggle hides the footer.
5. Live preview in the editor (iframe of the embed at current settings).
6. Tests: config persists; embed honors white-label + a style; default when
   unset. Run `affiliates` suite.
7. Richer dashboard UI polish (KPIs, link management) — separate pass.

## Out of scope (note, don't silently cut)
- Vendor control (own spec/session).
- New attribution logic; the affiliate code injection already works.

## Landmines (this codebase)
- `{% firstof a b as x %}` stringifies — never feed to `|money` (double `$$`).
  See `firstof-stringifies-landmine` memory + `_product_card.html`.
- Multi-line `{# #}` comments break; use `{% comment %}`.
- Embed is cross-site: sanitize any merchant-supplied CSS/text; the iframe
  doc must set its own CSP-safe inline styles, not pull storefront assets.
- Storefront $ formatting: apply `|money` to raw Money/dict, branch by shape.
