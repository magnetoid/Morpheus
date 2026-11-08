# SEO, answer engines and AI search — Nov 2026 pass

Owner's ask (2026-11-08): study Google's documentation and the current SEO / AEO /
GEO practice, improve the SEO app so all four stores get more and better traffic,
and fix the dotbooks sitemap.

## What the research says (2025–2026)

- **Google rich results narrowed.** FAQ rich results ended on 2026-05-07, HowTo
  earlier; Book actions are partner-only. The markup still describes a page to
  answer engines, so it stays, but nothing should be built *for* those results.
- **Merchant listings are judged per item.** Each variant of a `ProductGroup` is
  its own listing: it needs a name, an image and an offer. `variesBy` takes six
  values only (color, size, suggestedAge, suggestedGender, material, pattern).
- **Store-level policies.** Since June 2025 an `Organization` can carry
  `hasMerchantReturnPolicy`, and since Nov 2025 `hasShippingService`; a policy on
  the product's offer still wins over the store's.
- **Sitemaps.** Google uses `lastmod` only when it is consistently accurate and
  ignores `changefreq` and `priority`; `xhtml:link` is its hreflang extension and
  nothing else.
- **Thin pages.** A filtered or faceted page with too little on it should be
  `noindex` (or 404 when it has nothing), and kept out of the sitemap.
- **Answer engines.** Retrieval bots fetch at answer time and decide citations:
  OAI-SearchBot, ChatGPT-User, Claude-SearchBot, Claude-User, PerplexityBot,
  Perplexity-User, DuckAssistBot, meta-webindexer, meta-externalfetcher,
  Amzn-SearchBot, Amzn-User, MistralAI-User. Training bots (GPTBot, ClaudeBot,
  Applebot-Extended, meta-externalagent, Amazonbot, CCBot) are the store's choice.
  Google-Extended gates Gemini training and grounding, not Search or AI Overviews.
  Google does not read `llms.txt`.
- **What earns citations.** Pages with concrete numbers, quotations and named
  sources are cited more; freshness matters for ChatGPT.

## Shipped in this branch

Sitemap (dotbooks report):
- no Markdown `xhtml:link` alternates in the sitemap (still announced in the PDP head);
- `lastmod` to the second, and real `lastmod` on genre and topic pages;
- topics with fewer than `TOPIC_MIN_BOOKS` books are `noindex, follow` and left out
  of the sitemap (1,186 of 1,526 dotbooks topics held one book);
- the sitemap index gives `sitemap.xml` its newest entry's date instead of "now";
- IndexNow pings a CMS page at its real path (it pinged `/journal/<slug>/` for
  every page, a 404) and pings a deleted product, category or collection.

Structured data:
- editions are named after the book ("The Valley of Fear – Print"), carry the
  product's image when they have none, a `gtin` when the barcode is one, and an
  `@id`; `variesBy` claims only Google's values (no more `bookFormat`);
- the store node takes its name, logo and e-mail from Settings → General when the
  SEO settings are empty (never the 1200×630 share image as a logo, never the
  "Morpheus Store" default name); `WebSite.alternateName` is the domain;
- the return policy is on the store node too (returns_portal), so every page says it;
- a listing's `ItemList` counts the whole listing and page 2 continues the positions;
- robots.txt names the answer bots it was missing.

## Follow-ups (not in this branch)

1. `hasShippingService` on the store node from the shipping app's rates (the new
   `ShippingService` shape; needs a validator run before it ships).
2. Shipping details on each edition's offer, only for editions that ship.
3. Facet combinations with no products answer 404 (Google's faceted-navigation guidance).
4. `MemberProgram` / member prices from subscriptions, when a store sells memberships.
5. The news sitemap writes `<news:language>en</news:language>` on every store
   (`sitemaps.py`), which is wrong on `/sr/` and `/hr/` content.
6. `slug_history.py` still maps cms pages to `/journal/<slug>/`, the bug fixed here
   for IndexNow.
7. The "AI answer block" on the PDP is off by default on every store; turn it on
   where a merchant writes the answer.
8. Merchant Center: Google is retiring the Content API for Shopping in favour of
   the Merchant API; check the sunset date and move the push integration first.

## For the owner

- Search Console → Settings: set "Search generative AI" (AI Mode / AI Overviews
  use of the site) to Include on each store, and submit `sitemap-index.xml`.
- Bing Webmaster Tools: verify all four stores (Copilot answers from Bing's index;
  IndexNow pings reach Bing but the site report needs a verified site).
- Settings → General on each store: upload a square logo and a contact e-mail, so
  the store node in search carries them.
