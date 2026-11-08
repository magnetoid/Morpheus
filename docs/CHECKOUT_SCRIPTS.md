# Scripts on the payment pages

This is the inventory PCI DSS 4.0.1 requirement 6.4.3 asks for: every script that
runs on a page where a shopper types an address or a card, who put it there and
why. It covers what Morpheus ships. A store that adds tags through its own Google
Tag Manager container owns the inventory of those tags.

## The pages

Each of these views carries `@payment_page` (`core/security_headers.py`), which
sends an **enforced** Content-Security-Policy:

| Page | View |
|---|---|
| Cart (wallet buttons) | `storefront.views.cart.cart` |
| Checkout: address, delivery, review | `storefront.views.checkout.checkout`, `checkout_shipping`, `checkout_review` |
| Checkout: one-page form | `storefront.views.checkout_one_page.checkout_one_page` |
| Checkout: card | `storefront.views.checkout.checkout_payment` |
| Saved cards | `storefront.views.account.account_payment_methods` |
| Membership card form | `subscriptions.views_storefront.subscribe_start_view` |

The same paths under a language prefix (`/sr/checkout/`) are the same views.
Every other storefront page keeps the report-only policy.

## How a script is authorized

The policy's `script-src` is `'nonce-…' 'strict-dynamic'` (plus the origins
below, which only a browser without `'strict-dynamic'` reads). A script runs only
when its tag carries the nonce of that one response, and the nonce is written
only by the server's own templates (`nonce="{{ csp_nonce }}"`) and template tags
(`core.security_headers.script_nonce`). Markup that reaches the page any other
way (a product description, a review, a stored injection) runs nothing. Inline
event attributes (`onclick=`) and `javascript:` links do not run either, and
there is no `'unsafe-eval'`. A script the nonced ones load (Stripe's frames,
Google's tag libraries) is trusted through `'strict-dynamic'`; its vendor
answers for it.

`object-src 'none'`, `base-uri 'self'` and `frame-ancestors 'self'` hold too, and
forms may post only to the store itself and to PayPal (the one-page checkout
redirects a PayPal order to PayPal's approval page). A blocked script files a
report at `/api/csp-report/`, which the self-improvement scanner keeps as a
`csp` signal.

### Integrity

- **The store's own files** (`/static/…`) are served from the store's origin
  under content-hashed names (`core/staticfiles.py`), so a changed file is a new
  name in a new release.
- **Inline scripts** are code in this repository, reviewed like any other.
- **Stripe.js and Google's tags** are versionless: their vendors change them
  without notice, so a fixed hash (Subresource Integrity) would block them.
  Stripe requires Stripe.js to load from `js.stripe.com`, never from a copy.
- **jsDelivr modules** name an exact npm version (`motion@10.18.0`,
  `web-vitals@4.2.4`), and a published npm version never changes.

## Third-party origins

Each origin is in `PAYMENT_PAGE_SCRIPT_ORIGINS`. `core/tests/test_payment_page_csp.py`
fails when a payment page loads a script from an origin this table does not list,
or when the table and the list disagree.

| Origin | Owner | What it is | When it loads |
|---|---|---|---|
| `https://js.stripe.com` | payments | Stripe.js: the card form, wallet buttons and 3-D Secure frames | Stripe is configured (both keys) |
| `https://*.js.stripe.com` | payments | Parts of Stripe.js that Stripe serves from subdomains | With Stripe.js |
| `https://maps.googleapis.com` | storefront | Google Places address suggestions on the checkout address form | `GOOGLE_PLACES_API_KEY` is set |
| `https://www.googletagmanager.com` | tracking, google_shopping | Google Analytics 4 (gtag.js) or the store's Tag Manager container; Google Ads remarketing | A measurement ID or container is set and the shopper allows analytics (remarketing: marketing) |
| `https://cdn.jsdelivr.net` | themes dot_books, supernatural_shop, irving_survival | `motion@10.18.0` (animations) and `web-vitals@4.2.4` (page-speed measurements for the SEO app) | Every page of those themes |
| `https://connect.facebook.net` | meta_commerce | Meta Pixel | Pixel ID set and switched on; shopper allows marketing |
| `https://analytics.tiktok.com` | tiktok_commerce | TikTok Pixel | Pixel ID set; shopper allows marketing |
| `https://s.pinimg.com` | pinterest_commerce | Pinterest Tag | Tag ID set; shopper allows marketing |
| `https://sc-static.net` | snapchat_commerce | Snap Pixel | Pixel ID set; shopper allows marketing |
| `https://www.redditstatic.com` | reddit_ads | Reddit Pixel | Pixel ID set; shopper allows marketing |
| `https://bat.bing.com` | microsoft_commerce | Microsoft Advertising UET tag | Tag ID set; shopper allows marketing |
| `https://challenges.cloudflare.com` | cloudflare | Turnstile, the bot check on the newsletter form in the page footer (the checkout's own forms ask for none) | Turnstile is on, both keys are set and newsletter sign-ups are protected |

A store whose Google tag runs through its own server-side tagging domain loads
`gtag.js` / `gtm.js` from that domain instead of `www.googletagmanager.com`.

## First-party scripts

Served from the store itself, inline or from `/static/`:

- **The theme** (its `storefront/base.html` and the cart drawer): menus, the
  search overlay, the cart drawer, animations, image fallbacks, speculation
  rules for faster navigation.
- **core**: `core/error-capture.js`, which reports the page's script errors to
  the store's error log.
- **storefront**: `csrf-refresh.js` (a fresh form token on a cached page), the
  checkout's submit-button state and address-suggestion setup, the service
  worker registration when caching is on.
- **payments**: `express-cart.js` and the card-form setup that mounts Stripe's
  frames.
- **Apps on every page**, each only while the app is on and configured:
  analytics (page-view beacon to the store), motion and immersive_pdp
  (`/static/` runtimes), pwa (service worker), newsletter (sign-up pop-up), crm
  (support chat), agent_mcp (WebMCP tools for AI browsers), localization
  (language switcher), the tracking and pixel apps' loader snippets above.

## Adding a script to a payment page

1. Give the tag `nonce="{{ csp_nonce }}"`; a template tag that writes one takes
   the context and uses `script_nonce(context)`.
2. Attach behaviour with `addEventListener`, never an `on…=` attribute.
3. A new third-party origin goes into `PAYMENT_PAGE_SCRIPT_ORIGINS` and the table
   above, with its owner and reason, in the same change.

The test renders every payment page under every theme with every script-writing
app switched on and fails on a script without the response's nonce, on an inline
handler, and on an origin missing from the list.
