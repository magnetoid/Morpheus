---
type: decision
status: accepted
tags:
- adr
links:
- '0008-every-page-on-the-site-hardcoded-or-model-driven-must-appear-in-the-sitemap'
- '0013-app-modularity-disabling-a-plugin-removes-all-its-features-from-storefront-and-dashboard'
- '0017-advanced-powerful-commerce-core-delivered-through-modularity-supersedes-tiny-core'
- '0022-storefront-language-routing-via-i18n-patterns-on-prefix-urls-only'
created: '2026-08-18T00:00:00'
updated: '2026-08-18T00:00:00'
rules:
- id: head-comes-from-one-tag
  pattern: <title>|rel="canonical"|property="og:|application/ld\+json
  message: "Storefront <head> SEO belongs to the head document, not a template. A theme
    calls {% storefront_head %} once; apps contribute through STOREFRONT_HEAD /
    SEO_JSONLD_GRAPH. A <title>, canonical, og:* or JSON-LD written into a theme or page
    template duplicates the kernel's."
  where: themes/**/*.html, plugins/installed/*/templates/**/*.html
  severity: warn
- id: no-brand-in-view-copy
  pattern: seo_title.*—|seo_title.*·
  message: "A stored/produced page title is the CLEAN page name; the brand is applied at
    render from settings (ADR 0007). Never append the shop name in a view or template."
  severity: warn
- id: machine-endpoints-are-chrome
  pattern: register_urls\(.*robots|sitemap|llms|well-known
  message: "Sitemaps, robots.txt, llms.txt and .well-known files must be registered with
    surface='chrome' so i18n_patterns never prefixes them (/fr/robots.txt is not a thing)."
  severity: warn
---

# ADR 0036: The storefront `<head>` is built by core and filled in by the SEO app

## Context

SEO was a property of the *theme*. `<head>` markup came from ~107 `{% seo_* %}`
calls spread over 60 templates (26 distinct tags), plus `seo_title` /
`seo_description` strings hardcoded in ~52 view sites — including the shop's own
name, 20 times. The consequences were structural, not cosmetic:

- **A different theme got no SEO.** The shipped fallback
  `storefront/base.html` emitted a hardcoded `<title>` and nothing else: no
  canonical, no robots, no Open Graph, no structured data. A store that had not
  installed a designed theme was invisible to search engines.
- **No app could contribute a single tag.** There was no `HEAD_*` seam, so an
  app that wanted to add one meta tag had to own an entire `global_head` block.
- **Duplication was the normal failure.** The PDP emitted `og:type` twice;
  `WebSite` and `CollectionPage` JSON-LD were emitted twice on several page
  types; category, collection and journal titles carried the brand twice.
- **Overriding one thing dropped another.** `/search/` shipped with **no
  `<title>` at all**, because the theme's title lived inside the same
  `{% block seo %}` the page overrode to force `noindex`.
- **Machine endpoints were treated as pages.** Registered at prefix `''`, they
  were wrapped in `i18n_patterns`, so a multi-language store also published
  `/fr/robots.txt`, `/fr/sitemap.xml`, `/fr/llms.txt`.

None of this is visible in a browser, which is why it survived for a year.

## Decision

**Core owns the shape of the head; the SEO app owns its content; a theme makes
room for it.**

1. `core/head.py` defines `HeadDocument` — a *keyed* set of entries (title,
   metas, links, JSON-LD, raw). A later writer with the same key **replaces** an
   earlier one, which is what makes "the shell seeds a fallback title, the SEO
   app supplies the real one" produce exactly one `<title>`.
2. `{% storefront_head %}` (in `core/templatetags/morph.py`, beside
   `storefront_blocks`) seeds the document with the shell's fallback copy, fires
   `STOREFRONT_HEAD` as a filter, and renders the result. A theme calls it once.
3. The `seo` app answers, resolving *which page this is* (`SeoPage`) from the
   URL name and template context, and produces title, description, canonical,
   robots (with a recorded reason), Open Graph, Twitter, hreflang (per language
   and per market), pagination links, verification metas, discovery links and
   **one** JSON-LD `@graph` with stable `@id`s.
4. Other apps contribute through filters, never markup: `SEO_RESOLVE_PAGE`
   (claim a URL shape), `SEO_JSONLD_GRAPH` (enrich a node you own the data for),
   `SEO_ENTITY_ADAPTERS`, `SEO_SITEMAP_SOURCES`, `SEO_ROBOTS_RULES`,
   `SEO_TEMPLATE_TOKENS`, `SEO_STRUCTURED_DATA_FOR_OBJECT`.
5. A theme declares `head_contract = 1` and is then held to it by
   `themes/test_head_contract.py`: exactly one title / canonical / robots meta /
   JSON-LD block per page kind, no hardcoded brand, and the page still renders
   with the SEO app disabled.
6. Machine endpoints register with `surface='chrome'` and are never
   language-prefixed (ADR 0022 applies to *pages*).

Legacy per-tag helpers keep working and go silent once the head document has
rendered, so a half-migrated theme cannot double-emit. They are deprecated
(`docs/MIGRATING.md`).

## Consequences

- Any storefront — a new theme, the fallback base, or a headless client reading
  `HeadDocument.as_dict()` — gets identical, complete SEO with one integration
  point.
- SEO becomes reviewable: one document, one graph, and a golden-profile test
  (`seo/tests/test_head_parity.py`) that snapshots every page type, so a change
  that loses a canonical or a Product node fails the build instead of the
  quarter's traffic.
- The brand lives in settings. Two merchants can run the same theme.
- ADR 0008's intent (every public page in the sitemap) is unchanged; its
  *mechanism* inverts from "add a generator inside seo" to "contribute a source"
  as `SEO_SITEMAP_SOURCES` lands.
- `catalog → seo` and `seo → catalog` leave the plugin-boundary baseline: catalog
  fires an event instead of importing seo's private helpers, and seo declares
  `requires = ['catalog']`, its one real dependency.
