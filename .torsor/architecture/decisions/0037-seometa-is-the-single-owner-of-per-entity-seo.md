---
type: decision
status: accepted
tags:
- adr
links:
- '0004-a-domain-with-a-settings-dashboard-page-must-not-also-contribute-a-settingspanel'
- '0007-a-page-title-is-the-clean-page-name-the-brand-is-applied-at-render'
- '0013-app-modularity-disabling-a-plugin-removes-all-its-features-from-storefront-and-dashboard'
- '0023-a-shared-shell-must-render-an-optional-apps-surface-through-a-contribution'
- '0036-the-storefront-head-is-built-by-core-and-filled-in-by-the-seo-app'
created: '2026-08-19T00:00:00'
updated: '2026-08-19T00:00:00'
rules:
- id: seo-writes-go-to-seometa
  pattern: \.(meta_title|meta_description|focus_keyword|og_title|og_description|twitter_title|twitter_description)\s*=
  message: "Per-entity SEO is owned by SeoMeta. The native catalog columns are read
    as a fallback for one release and are removed after that — write through
    SeoMeta (or the panel's save_object_seo) instead of assigning the column."
  where: plugins/installed/**/*.py
  severity: warn
- id: form-saved-needs-a-presence-marker
  pattern: def on_\w+_form_saved
  message: "A *_FORM_SAVED handler must key off a field its own card posts. Keying
    off absence means a POST from a form that never rendered the card writes blanks
    over stored data."
  severity: warn
- id: redirect-targets-are-site-relative
  pattern: HttpResponsePermanentRedirect\(|HttpResponseRedirect\(
  message: "A redirect target that came from the database is staff- and
    assistant-writable. Validate it as site-relative before it reaches a Location
    header, or it is an open redirect."
  where: plugins/installed/**/middleware.py
  severity: warn
---

# ADR 0037: `SeoMeta` is the single owner of per-entity SEO

## Context

A product's SEO lived in two places at once.

Thirteen native columns on `catalog.Product` (`meta_title`, `meta_description`,
`focus_keyword`, `canonical_url`, `og_*`, `twitter_*`, `noindex`, `nofollow`),
edited through a 150-line block hardcoded in `admin_dashboard`'s product form.
And the generic `SeoMeta` overlay, edited through a genuinely good reusable
panel — live Google and social previews, counters, an OG image picker — that
exactly one content type used, the CMS page.

`resolve_meta` preferred `SeoMeta`. That would have been a defensible rule if
`SeoMeta` only ever held merchant input. It does not: `autofill_meta_for` mints
a row for **every** product on creation, seeded with the product's own *name*.
So the resolution order was, in practice:

> a title the platform guessed **beats** a title the merchant typed.

A merchant who filled in the product form's meta title saw the storefront go on
rendering the plain product name. The value was stored correctly, resolved
correctly by the documented precedence, and discarded. Every layer looked right
in isolation, which is why it survived.

Categories and collections had two columns and a bare two-field card;
CMS pages had the good panel; vendors had nothing. Five entity types, three
different editors, two storage locations, and no agreement about what "SEO"
even consisted of.

## Decision

**One owner, one editor, and a human's value beats the platform's guess.**

1. **`SeoMeta` owns per-entity SEO.** It gains the fields the native columns had
   and the panel lacked (`focus_keyword`, `twitter_title`, `twitter_description`,
   `robots_extra`, `sitemap_include`, `ai_answer`, `provenance`). The native
   columns are **read as a fallback** for one release and removed after that;
   `manage.py seo_backfill_meta` consolidates existing data, idempotently.

2. **Autofilled values lose.** `resolve_meta` checks `SeoMeta.auto_filled`: when
   the row was generated rather than edited, a non-empty native column wins. The
   panel and the backfill apply the same rule, so the editor, the renderer and
   the migration cannot disagree. Marking what the platform generated is the
   mechanism — without it, consolidating two stores silently prefers whichever
   one the merge happened to favour.

3. **One panel, contributed into four forms.** The reusable panel reaches the
   product, category, collection and CMS-page forms through `PRODUCT_FORM_CARDS`
   and the new `CATEGORY_FORM_CARDS` / `COLLECTION_FORM_CARDS` /
   `PAGE_FORM_CARDS` (each paired with a `*_FORM_SAVED` event). Disabling the seo
   app removes the card from all four at once (ADR 0013/0023), and `cms` stops
   importing `seo` to save it.

4. **A card-less POST may not write.** `save_object_seo` acts only when the
   panel's own field is present in the POST. The corollary is that removing a
   form's template block without removing its `required=False` form fields and
   its save loop **blanks the columns** — the three go in one change.

## Consequences

- A merchant edits SEO the same way everywhere, and what they type is what
  ships.
- `admin_dashboard` and `cms` stop knowing anything about SEO; the
  `cms → seo` pair leaves the plugin-boundary baseline.
- The head pipeline gains the two controls it was missing a consumer for: the
  thin-PDP threshold (a settings field that had had **no** reader since v0.46)
  and per-entity snippet/AI-preview directives.
- `<meta name="keywords">` stops being emitted. Engines have ignored it since
  2009, and the field now holds the merchant's *internal* focus keyword, which
  the editor tells them is not published.
- Product pages declare `og:type=product`. Nothing had ever written the field;
  a non-blank default outranked the page kind, so every share card was wrong.
- ADR 0004's shape is unchanged: `SiteSeoSettings` remains the site-wide home
  and the `PluginConfig` keys are folded into it when the settings page that
  renders them is rebuilt — moving the data before the UI would leave the
  merchant with knobs they cannot reach.
