---
name: morpheus-content-seo
description: >-
  Use when the merchant asks about CMS pages, the storefront journal/blog,
  meta tags, 404s, redirects, or sitemap on a Morpheus shop. Journal is
  cms.Page with metadata.category='journal', not journal.Post. SEO live
  path is SeoMeta.
version: 1.0.0
author: Morpheus OS
license: MIT
metadata:
  janus:
    tags: [morpheus, ecommerce, cms, seo, journal]
    related_skills: [morpheus-store-operator, morpheus-catalog]
---

# Morpheus content + SEO

Operate CMS and SEO for this shop. Merchant-facing name stays **Linda**.

## When to Use

- Journal / blog / pages / "write a post"
- Meta title/description, 404s, redirects, sitemap, "why isn't this indexing"

Do not use for product price/stock (that's `morpheus-catalog`).

## Journal vs CMS vs leftover blog

| Surface | Live on storefront? |
|---|---|
| `cms.Page` with `metadata.category='journal'` | Yes — `/journal/`, home teasers, sitemap |
| `journal.Post` + `journal.Block` | **No** URLs / dashboard / GraphQL |
| Seed `_JOURNAL_ENTRIES` fallback | Bookstore essays if CMS journal is empty |

To publish a journal article: create/update a `cms.Page`
(`state=published`, `metadata.category='journal'`), then `cache.clear()` if
a cache tool exists. Creating `journal.Post` does nothing the customer can
see.

Non-journal CMS lives at `/p/{slug}/`. IndexNow templates that send every
`cms.page` to `/journal/{slug}/` are wrong for those.

## CMS tools

| Tool | Use |
|---|---|
| `cms.pages` / `cms.list_pages` | List |
| `cms.get_page` | One page |
| `cms.create_page` / `cms.update_page` | Draft or edit |
| `cms.upsert_block` | Body blocks |
| `cms.publish_page` / `cms.unpublish_page` | Visibility (confirm) |
| `cms.delete_page` | Destructive (hard-gate) |
| `cms.recent_form_submissions` | Contact / forms |

Writes: tell them the slug + new state, wait for yes, `confirmed=True`.

## SEO — live owner

Render path: `{% storefront_head %}` → `SeoMeta` then native columns then
`SeoTemplate` then view fallbacks. After a merchant `SeoMeta` edit, catalog
GraphQL SEO fields stop affecting the page.

| Tool | Use |
|---|---|
| `seo.get_meta` | Current tags for a URL/object |
| `seo.set_meta` | Write SeoMeta (confirm) |
| `seo.audit_product` / `seo.audit_all` | Gaps |
| `seo.list_404s` | Broken paths |
| `seo.create_redirect` | 404 → live URL (confirm) |
| `seo.bulk_set_meta` | Only `empty_only` fills |
| `seo.set_site_settings` | org name / llms.txt intro |
| `seo.regenerate_sitemap` | After a batch of publishes |
| `seo.apply_internal_links` | Confirm; don't spray |

Fill empty descriptions from stripped `short_description` / `description`
(≤300 chars). **Do not** bulk-set `auto_filled=False`. **Do not** overwrite
merchant-edited SeoMeta.

DotBooks catalog is merchant-edited — do not run bulk SEO guesses there
unless they explicitly asked.

## Daily SEO pulse

1. `seo.list_404s` — fix with redirects when the target is obvious
2. `seo.audit_all` or a sample of new products — empty title/description
3. Mention AI crawlers only if `analytics.ai_traffic` has something real

## Common Pitfalls

1. Publishing `journal.Post` and thinking `/journal/` updated.
2. Bulk SEO on DotBooks without an explicit ask.
3. Setting `auto_filled=False` on guessed copy (locks junk in).
4. Redirecting `/p/{slug}/` pages as if they were `/journal/{slug}/`.
5. Assuming GraphQL `updateProduct` meta_* still wins after SeoMeta exists.

## Verification Checklist

- [ ] Journal work used `cms.Page` + `metadata.category='journal'`
- [ ] SEO writes targeted empty SeoMeta, not merchant-locked rows
- [ ] 404s mapped to a real live URL before creating a redirect
