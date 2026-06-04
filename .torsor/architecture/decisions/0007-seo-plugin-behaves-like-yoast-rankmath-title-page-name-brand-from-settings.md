---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-04T23:45:54'
updated: '2026-06-04T23:45:54'
rules:
- id: seo-title-no-baked-brand
  pattern: autofill_meta_for|SeoMeta.*title
  message: "SeoMeta.title must store the CLEAN page name only \u2014 the brand is\
    \ applied at render by format_document_title() (settings title_template). Never\
    \ bake STORE_NAME/brand into the stored title."
- id: seo-brand-from-settings
  pattern: STORE_NAME
  message: "Resolve the brand via brand_name() (org_name \u2192 store_name \u2192\
    \ STORE_NAME), not settings.STORE_NAME directly, so the SEO settings + store name\
    \ win."
---

# ADR 0007: SEO plugin behaves like Yoast/RankMath: title = page name + brand from settings

## Context
PDPs showed "Morpheus Store" while other pages showed the real brand. Root cause: autofill_meta_for() baked settings.STORE_NAME (env default "Morpheus Store") into each SeoMeta.title, which resolve_meta served verbatim, bypassing the SEO settings title_template + organization_name. The merchant's configured brand (StoreSettings.store_name = "dotbooks") was ignored on object pages.

## Decision
The SEO app works like a WordPress SEO plugin (Yoast/RankMath): the stored SeoMeta.title holds ONLY the clean page name; the branded document <title> is composed at render by format_document_title() applying SiteSeoSettings.title_template ({title}/{site_name}/{category}). {site_name} resolves SiteSeoSettings.organization_name → core.StoreSettings.store_name → settings.STORE_NAME (brand_name() in seo/services/meta.py). ResolvedMeta gained a document_title field (templated <title>); og:title + schema.org name keep the clean title. Object pages get the templated title; brand-as-fallback pages (homepage/static) keep their fallback so we never render "brand — brand". Idempotent (won't double-append brand) and clamped to title_max_length. Legacy baked rows are repaired by `manage.py seo_rebuild_titles`.

## Consequences
Titles are consistent and merchant-controlled from the SEO settings page with a store-name fallback. New autofill stores clean names. Existing prod rows need `seo_rebuild_titles` run once (post-deploy).
