---
name: morpheus-content-seo
description: >-
  CMS pages, the storefront journal (blog), SEO titles and descriptions, 404s,
  redirects and the sitemap on a Morpheus store.
version: 2.0.0
author: Morpheus OS
license: MIT
metadata:
  janus:
    tags: [morpheus, ecommerce, cms, seo, journal]
    related_skills: [morpheus-store-operator, morpheus-catalog]
---

# Morpheus content and SEO

## Journal and pages

The storefront journal (`/journal/`) is made of CMS pages in the journal
category. Other CMS pages live at `/p/<slug>/`.

| Tool | Use |
|---|---|
| `cms.pages` / `cms.get_page` | List pages; read one |
| `cms.create_page` / `cms.update_page` | Draft or edit (needs a yes) |
| `cms.publish_page` / `cms.unpublish_page` | Visibility (needs a yes) |
| `cms.upsert_block` | Banners and callouts (needs a yes) |
| `cms.delete_page` | Permanent (needs a yes) |
| `cms.recent_form_submissions` | Contact form entries |

## SEO

| Tool | Use |
|---|---|
| `seo.get_meta` | A product's current title and description |
| `seo.audit_product` | Score and issues for one product (runs without asking) |
| `seo.list_404s` | Broken paths customers hit, with suggested redirects |
| `seo.set_meta` / `seo.bulk_set_meta` | Write titles and descriptions (needs a yes) |
| `seo.create_redirect` | Send a 404 to a live page (needs a yes) |
| `seo.audit_all` | Audit every product (needs a yes) |
| `seo.regenerate_sitemap` | After publishing a batch (needs a yes) |

"What are our SEO problems?": `seo.list_404s`, then `seo.audit_product` on a
few important products. Offer `seo.audit_all` or a background job for the rest.

## Rules

1. Never overwrite a title or description the merchant wrote. Fill empty ones,
   from the product's own description, 300 characters at most.
2. A redirect needs a live target page. Check it exists first.
3. Mention AI crawler traffic only if `analytics.ai_traffic` shows some.
