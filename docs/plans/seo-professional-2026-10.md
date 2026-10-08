# Professional SEO + 404 handling across all three stores (v0.80.0)

**Status: shipped in v0.80.0 (2026-10-08).** Every step below is done; the
guards are listed in the release notes. Left for the owner: the publisher
value "DotBooks" vs "DotBooks.store" on dotbooks (two publisher pages).

Owner request (2026-10-08): "fix everything — the stores must look like
professional e-commerce sites and the platform must work without these gaps".
Source: the live audit of dotbooks.store, supernatural-shop.com and
montenegro-experience.me (memory `seo-404-audit-2026-10`).

## What the audit proved

* Real 404s are correct on all three stores (status 404, `noindex, follow`).
* What is wrong is everything AROUND them:
  1. **Soft 404s in the sitemap.** montenegro: 181 of 520 sitemap URLs are empty
     pages answering 200 + `index, follow` — 171 host pages ("0 listings", title
     "<Host> — Publishers"), 7 empty categories, `/products/`, `/categories/`.
     Hosts own BookableService listings the host page never shows.
  2. **404 / noindex pages still claim to be pages**: self-canonical (or a
     canonical to a live page for `?page=999`), `og:url`, hreflang en/sr/x-default
     pointing at the dead URL, an Organization/WebSite/WebPage graph.
  3. **hreflang built from the raw request URI** (echoes `?utm_*`, `?fbclid`),
     while the canonical strips them. dotbooks: market "eu" (no countries) makes
     every page say `hreflang=en → /?market=eu`, a URL that canonicalises away.
  4. **Internal search indexable**: `/search/?q=` → `/products/?q=` = an
     indexable listing on every store; redirect drops the `/sr/` prefix.
  5. **Theme ↔ SEO drift**: ~150 dead `{% block title %}` overrides (no base
     defines it; montenegro's translated 404 title never renders); 12 raw
     `ld+json` blocks in montenegro (+ a static FAQPage on `/bookings/` and
     `/shop/` whose questions are not on the page); `/shop/` h1 says
     "Experiences"; dead raw hreflang on the dot_books PDP; `<html lang="en">`
     hardcoded in dot_books/supernatural; the contract test scans robots +
     canonical only.
  6. **Views answering 200 for nothing**: inactive category, booking/hotel of a
     deactivated host, publisher/series/imprint with only inactive books, author
     with no active books, empty curated genre/topic, `/stockists/` placeholder,
     empty `/staff-picks/`; broad `except → Http404` hides real errors.
  7. **Redirects drop the language prefix** (`/categories/`, `/category/x/`,
     `/search/`, cms journal).
  8. **dotbooks**: 1,527 topic pages and 9 genres without a description; facet
     landings unpaginated (`/format/paperback/` 1.5 MB); `/language/English/`
     duplicates `/language/en/`; journal index shows 50 of 150 posts;
     `/shipping/` + `/p/shipping/` (and returns) are two pages for one policy.
  9. **Unprofessional surfaces**: login on dotbooks/supernatural is the bare
     "Sign in · Morpheus" frame; shared 404 says "never printed" on an
     apothecary; montenegro "Gift cards" links land on the empty catalog; book
     copy ("Send a book back", "Independent presses") in shell SEO strings.
 10. **The SEO app could not see any of it**: the site audit has no soft-404,
     canonical-elsewhere, hreflang or 404-handling checks.

## Rules this release establishes (become CLAUDE.md landmines + tests)

* **An error page is not a page.** Title, description, `noindex, follow` — and
  nothing else: no canonical, no hreflang, no Open Graph, no JSON-LD.
* **A noindex page never names another URL.** No hreflang, no rel prev/next, no
  graph; a canonical only when it is the page itself (no query string).
* **hreflang is derived from the canonical**, never from the request URI, and a
  market alternate exists only when `market` is an indexable parameter and the
  market names its countries.
* **An empty listing is noindex, follow and absent from the sitemap.** Views
  report `seo_item_count` (or a paginator); the resolver applies the rule; the
  sitemap lists a listing only when its owner says it has items.
* **A page lists what its owner says it has.** Host pages show BookableService
  listings via `STOREFRONT_VENDOR_SECTIONS`; vendor counts for the directory and
  the sitemap come from `VENDOR_LISTING_COUNTS`.
* **Structured data comes from the graph only.** No theme emits `ld+json` or
  hreflang; booking pages contribute nodes through `SEO_JSONLD_GRAPH`.

## Work, in order (each step ships with its test)

1. **Head (seo):** error/noindex gating, canonical-derived hreflang, market gate,
   graph url = canonical, view-name kind table (namespaced), search kind for
   `q`, empty-listing rule, `seo_noindex_reason`, translatable titles for auth +
   storefront private routes.
2. **Sitemap (seo + owners):** categories/collections with active products,
   vendors via `VENDOR_LISTING_COUNTS`, authors with active books, conditional
   static pages, `is_active` checks, cms pages claimed by storefront routes
   (`CMS_PAGE_PATH`), booking `/shop/` + regions, list pages only when non-empty.
3. **Storefront views:** inactive category 404, prefix-safe redirects,
   `STOREFRONT_SEARCH_PATH`, vendor sections + counts + theme vocabulary, item
   counts, author 404, paginated journal + vendor page, `/shipping/` and
   `/returns/` render the merchant's CMS policy, neutral shell copy,
   `/stockists/` noindex, affiliates terms 404 when off, `/offline/` noindex,
   private-page titles, narrow excepts.
4. **book_product:** facet 404/noindex, descriptions (term → description →
   generated from the shelf), pagination, language normalisation (301),
   index counts active only, no hardcoded brand.
5. **booking_marketplace:** `SEO_RESOLVE_PAGE` + `SEO_JSONLD_GRAPH`, visible FAQ
   from context (stays), no FAQ on experiences/shop, host-inactive 404, shop
   heading, sections + counts subscribers, search path, sitemap.
6. **Themes:** remove raw ld+json/hreflang and dead blocks, `<html lang>`,
   clean page-1 links, 404 copy (neutral shared + dot_books own), themed auth
   frame for every theme, montenegro shop/gift links, vendor vocabulary.
7. **Errors:** lean plain-text 404 for asset paths (`handler404`), 404 log keeps
   real broken URLs that carry `?page=`.
8. **Site audit:** canonical-elsewhere, hreflang-not-canonical, not-found probe
   (status + head) findings.
9. **Guards:** error head under every contract theme (+ `/sr/`), theme scan for
   ld+json/hreflang/dead blocks, sitemap emptiness, parity profile re-recorded.
10. **Docs + release:** CLAUDE.md, PLUGIN_DEVELOPMENT (new hooks), THEME docs,
    release notes (MINOR), deploy, re-run the live probe + crawl on all three.

## Out of scope (reported, not changed)

* Merchant data: publisher "DotBooks" vs "DotBooks.store" (two publisher pages)
  — owner's call; language "English" is normalised in code instead.
* Product images (handled externally).
