# Markets, visitor currency and language suggestion (A6) — design

Status: approved by the owner 2026-11-13 (time zone as the country signal). Release 1 shipped as v0.165.0; see "What release 1 built" below. Replaces the markets half of A6 in
`platform-gap-analysis-2026-11.md`; B2B price lists move to A9.

## Why

A store that sells abroad shows every visitor one currency and one language.
Shopify's model (Markets + Languages + Translate & Adapt) is the reference:
a visitor sees and pays in their own currency, is offered their own language,
and can always choose otherwise. Today Morpheus has the parts and none of it
works: `Market` rows change nothing a shopper sees (markets `help.md`), the
`convert` filter has no caller, `ExchangeRate` has no writer, `?currency=`
is the only way to a second currency and only the cart honours it, and the
visitor's country comes from Cloudflare's `CF-IPCountry` header, read directly
by the markets app.

Owner's rules for this work (2026-11-13):
- Markets: countries, currency, languages and a default language.
- Currency: set from the visitor's country on the first visit, no URL change.
- Language: a suggestion only, never a forced redirect.
- The visitor can choose country/currency and language; the choice is kept in a cookie.
- Crawlers are never redirected and never see converted prices.
- **Cloudflare is out of the loop.** Cloudflare is an optional app; everything
  here works natively in core and the markets app, with or without Cloudflare
  or any other CDN in front.

## What the live stores hold (read-only check, 2026-11-13)

| Store | Currency | Languages | Markets | Fixed prices | Orders |
|---|---|---|---|---|---|
| dotbooks | USD | en | `eu` (EUR, no countries, active, not default) | 0 | 13, USD |
| Supernatural | USD | en | none | 27 products with `localized_prices` RSD (3 of them `0`) | 2, USD |
| Irving | USD | en | none | 0 | 0 |
| Montenegro | EUR | en, sr | none | 0 | 0 |
| Croatia | EUR | en, hr | none | 0 | 0 |

No store has a default market, a `ProductMarketPrice` or an `ExchangeRate`. So:
the store itself is the default market (§1); dotbooks' `eu` market detects nobody
until it names countries; Supernatural's RSD prices are the only fixed prices
anywhere, and a `0` there means "none" (a gift mug priced 0 RSD would otherwise
be free).

## Goals

1. A market = countries + currency + languages + default language + price
   adjustment + rounding rule, edited on Settings → General → Markets.
2. The visitor's country is found natively, without Cloudflare or an IP service.
3. Every price a shopper sees on a catalogue page is in their market's currency.
4. Cart, checkout and the order charge in that currency (release 2).
5. Exchange rates update themselves daily; a rate the merchant typed wins.
6. A visitor whose browser prefers another store language, in which the page
   exists, is offered that language.
7. Linda can list and change markets, prices and rates (writes need the
   merchant's yes).

## Non-goals

- A separate URL, domain or subfolder per market (`/en-de/`). The URL stays the
  language's URL; the currency follows the visitor.
- Per-market product availability (Shopify catalogs), duties and import taxes,
  per-market payment methods or themes.
- B2B price lists (A9) and volume pricing.
- Adding a language from the dashboard (languages stay `MORPHEUS_LANGUAGES`; a
  later item).

## Anti-goals (a failure even if it "works")

- A cached page served to one visitor carrying prices computed for another.
- A price on the product page that differs from the price in the cart.
- Googlebot seeing a currency other than the one in the page's structured data.
- A visitor redirected away from the page they asked for.
- Any code path that needs Cloudflare (or its headers) to function.

## Design

### 1. The market (markets app owns it)

`Market` keeps its fields and gains:
- `languages` — JSON list of store language codes offered in this market
  (empty = all store languages);
- `rounding` — `exact` | `whole` | `ninety_nine` (x.99); default `exact`
  (additive, `db_default`).

`currency` becomes a select of ISO codes, not free text. **The store itself is the
default market**: its currency (the one products are priced in) and all its
languages, for every country no active market names. No live store has a default
market row, so `is_default` is retired (state-only, two releases). A market whose
currency has no rate (§4), or that no configured payment method can charge (§5),
cannot be switched on; an active market that loses either is skipped, not shown.

The existing `default_locale` is the market's default language: the language the
selector (§7) preselects when a visitor picks that market's country by hand. It is
never applied because of where a visitor is.

`ProductMarketPrice` stays the one place for a fixed per-product price in a
market. catalog's `localized_prices` JSON is the same fact in a second table:
it stays readable as a fallback for one release and is then retired (two-release
removal); nothing writes it from now on. (My call — check live rows first.)

### 2. The visitor's country, natively

Core fires a new filter, `VISITOR_COUNTRY` (value: ISO country or `''`;
kwargs: `request`, `hints`). The markets app answers it from **the browser's time
zone**: the page's script sends `Intl.DateTimeFormat().resolvedOptions().timeZone`
once; a committed table maps IANA zone → country (generated from tzdata's
`zone.tab`, which gives each zone one country: `Europe/Zagreb` HR,
`Europe/Podgorica` ME; script in `scripts/`). `Etc/*`, `UTC`, unknown zones and
a country no active market names give the default market.

First step of the build, before anything depends on it: confirm what browsers
report on a system set to Croatia, Montenegro, Serbia and Bosnia, on macOS and on
Windows (Windows names "Central European Standard Time" for all of Sarajevo,
Skopje, Warsaw and Zagreb, and the browser has to pick the zone from the region).
If the major ones collapse into one zone, the time zone is not good enough and the
IP database (below) comes first.

Why the time zone (my call): no database to download and refresh, no client-IP
parsing behind proxies (every hosting differs: Coolify/Traefik, Plesk, nginx,
Cloudflare), no IP address processed at all, and it follows the device, so a VPN
does not move a visitor to the wrong country. An IP database (DB-IP Lite, CC BY,
monthly) can answer the same filter later as its own app if the time zone proves
too coarse. The Cloudflare app does **not** answer it (owner: out of the loop).
`?country=` and `CF-IPCountry` reading in `markets/services.py` are removed.

### 3. Showing prices without breaking caches

Catalogue HTML stays **identical for every visitor**, so any cache in front of
the store (Cloudflare, nginx, Varnish, none) stays correct.

- Each price a shopper sees is rendered as today (store currency) and carries
  its price in every active market, computed on the server by the one pricing
  function (§4) and already formatted for the page's language:
  `<span data-market-prices='{"EUR":"9,50 €","GBP":"£8.49"}'>$10.00</span>`.
  A new tag `{% market_price product_or_variant %}` (and the GraphQL field
  `Product.marketPrices`) produce it; themes swap their visible price spots
  (product cards, PDP, listings, related products, search suggestions) to it.
  Structured data, feeds, meta text and `alt` keep `|money` in the store currency.
- `markets/static/markets/market.js` (contributed to `global_head`, nonce'd):
  reads the `morpheus_market` cookie; on the first visit it asks
  `GET /market/?tz=<zone>&t=<now>` (never cached, like `/csrf/`), which resolves
  the market, sets the cookie and answers `{market, currency}`; then it replaces
  the text of every `[data-market-prices]` element whose market currency differs
  from the page's. Without JavaScript the page shows the store currency.
- No flash of the wrong currency: a few nonce'd lines at the top of `<head>` read
  the cookie and, when it names another currency, mark `<html>` so that
  `[data-market-prices]` is `visibility: hidden` until the swap (space is kept, so
  nothing moves). With at most a handful of markets the attribute adds a few KB to
  a 50-card listing before compression.
- `/market/` answers the default market to a crawler
  (`core.utils.crawlers.is_crawler_user_agent`) and sets no cookie, so Googlebot's
  rendered page matches the page's JSON-LD.
- Cart, checkout, account and the cart drawer are never public-cached; they
  render on the server in the cart's currency (§5).

### 4. One price function, rates and rounding

`markets.pricing.market_price(product, variant, market) -> Money`, the only
place a market price is computed, used by the tag, GraphQL and the cart:
1. a `ProductMarketPrice` for the product (then `localized_prices`, for one release);
2. else the base price × (1 + adjustment %), converted to the market currency;
3. then the market's rounding rule, at the currency's minor unit (JPY has none).

Rounding applies to product prices only. Shipping, discounts and tenders are
converted exactly, so a cart's total is always the sum of what it lists.

Conversion is core: `core/pricing.py:convert(money, currency)` reads
`ExchangeRate` (direct pair, else the inverse, else across the store currency)
and quantizes to the currency's minor unit; the `convert` filter uses it.

Rates: a daily task in the markets app (registered by name in
`CELERY_BEAT_SCHEDULE`) fetches the ECB reference rates through
`core.net.outbound_request`, writes `source='ecb'` rows from the store currency,
and never overwrites a `source='manual'` row. ECB does not publish every
currency (no RSD), so the Markets page shows each market's rate, its source and
age, and takes a manual rate. A rate older than 3 days on an active market is a
health-check failure.

### 5. Charging in the visitor's currency (release 2)

- The cart gets the market's currency when it is created and is re-priced when
  the visitor changes market (`CartService.set_market`); the one-currency-per-cart
  rule stays.
- Unit prices come from `market_price`.
- Every amount the store keeps in its own currency is converted into the cart's
  at the cart's rate when the breakdown runs: shipping rates and free-over
  thresholds, fixed-amount promotions and coupons and their minimums, gift card
  balances, store credit, the money value of loyalty points. Gift cards, store
  credit and points always stay in the store currency; a balance is debited in the
  store currency at the cart's rate, rounded to its minor unit, and a refund
  re-credits it pro rata at the order's stored rate (the existing per-refund
  proration, unchanged).
- Payment methods: each gateway says which currencies it can charge
  (`supports_currency`); checkout offers only those that can charge the cart's
  currency. Bank transfer and cash on delivery charge the store currency only.
  A market no configured method can charge cannot be switched on (§1).
- The order stores the rate (`metadata['fx']`: base, quote, rate, source, time)
  and a nullable `Order.store_total` in the store currency; every report sums
  `Coalesce(store_total, total)` (all existing orders are in the store currency).
- Stripe and the wallet sheet charge `order.total` in the cart's currency (they
  already do); refunds go back in the currency paid; a store-credit refund is
  credited in the store currency at the order's rate.
- A visitor never sees one currency on a product page and pays in another: the
  catalogue switches currency in the same release that charges in it (see Releases).

### 6. Language suggestion

`market.js` also compares `navigator.languages` with the languages the page
actually exists in — the `<link rel="alternate" hreflang>` tags in its head,
which after #157 name only the languages the content is translated into. When the
visitor's first preferred store language is not the page's and the page exists in
it, a small bar offers it, written in that language: "Ova stranica postoji na
srpskom — Prebaci · Ostani". "Prebaci" goes to the alternate URL; either choice is
remembered in the `morpheus_lang_choice` cookie and the bar never comes back for it. The
bar's strings for every store language are in the script's data, rendered the same
for everyone. A market's `languages` limit what it offers; nothing is offered by
location. Settings switch: `suggest_language`, default off.

Crawlers and audit tools get no bar and the store currency: `/market/` treats a
missing user agent as a crawler, so Lighthouse and axe audit what Google sees.

### 7. The visitor's own choice

A selector (country → currency, and language) contributed to the footer slot
next to the language switcher; it writes `morpheus_market` (1 year, `SameSite=Lax`,
readable by the script) and re-prices the cart. A stored choice always beats
detection. A choice the visitor makes is stored as part of the service they asked
for. A cookie set by detection follows the consent app: if it has a preferences
category and the store manages consent, detection still prices the page but
stores nothing until that category is allowed.

### 8. SEO

- hreflang stays per language. `seo/head/builder.py:_market_alternates`
  (`?market=<code>` alternates per region) is removed: a market no longer has its
  own URL, so those alternates would name identical pages. (My call.)
- `?market=` stops selecting a market; old links answer the page as usual.
- Offers in JSON-LD, feeds and sitemaps stay in the store currency.

### 9. Linda

`markets.list`, `markets.get` (read); `markets.create`, `markets.update`,
`markets.delete`, `markets.set_product_price`, `markets.set_rate`,
`markets.refresh_rates` (write, `requires_approval=True`). Scopes
`markets.read`/`markets.write` in `AVAILABLE_SCOPES`, `_CAPABILITY_FOR_SCOPE`
(mapped to `catalog.read`/`catalog.write`, which roles already hold) and
`gates.LINDA_SCOPES`.

### 10. Settings (markets app)

- `detect_country` (default on; does nothing while only the default market is active)
- `suggest_language` (default off)
- `rate_source` (`ecb` | `manual`, default `ecb`)

## Releases

1. **Markets, rates and the language bar** (minor). §1, §4, §6, §8–10 and the
   zone table with its browser check (§2). The Markets page, rates (ECB + manual),
   `market_price`, Linda's tools and the language bar (off by default). Shoppers
   see no currency change yet: nothing detects or swaps currencies.
2. **Visitors see and pay in their currency** (minor). §2–3, §5, §7: detection,
   the price swap, the selector, cart and checkout in the market currency,
   tenders, payment methods, refunds, `store_total` and reports, all at once, so
   no page ever shows a currency the checkout does not charge.

(My call: the first draft split "show" from "charge", which would have shown one
currency and charged another, the anti-goal above.)

## What release 1 built, and what moved to release 2

Release 1 (v0.165.0, `docs/plans/markets-r1-plan-2026-11.md`) built §1 without
`Market.languages` and without retiring `is_default`, §4, §6, §8–10. These moved to
release 2, because nothing reads them before detection and the swap:
- `Market.languages`, the zone table and its browser check (§2), and retiring
  `is_default` (§1).
- `detect_country` (§10): its reader is detection.

Settled while building:
- `suggest_language` lives in the localization app (it owns the bar); the cookie is
  `morpheus_lang_choice`.
- Linda's create and update are one tool, `markets.save`.
- A fixed price applies only in the currency it was set in; changing a market's
  currency removes its fixed prices.
- Every ECB currency is stored while any active market needs a rate, so a new
  market's rate is ready the day it is added.

Release 2 must also decide:
- **Variants:** a product-level `ProductMarketPrice` applies to every variant, and a
  product-level `localized_prices` entry to a variant priced differently from the
  product.
- **Charging:** `orders._resolve_unit_price` goes through `market_price`. Today it
  reads a typed `'0'` as a price and accepts lowercase currency keys.
- **Speed:** memoize `exchange_rate` per request, since every price on a listing is
  converted.
- **The price-change guardrail:** `max_price_change_pct` applies to market prices and
  adjustments once shoppers see them.
- **Visibility:** what `ProductMarketPrice.is_visible=False` means.

## Left to the builder

Template names, the exact zone table format, the selector's markup per theme,
the bar's styling, test layout. Every new setting has its reader; every new
event both ends; migrations additive (`db_default`).

## Open question for the owner

Time zone as the country signal (no IP, no database; checked against real
browsers first), with an IP database as a later app only if the check fails — or
an IP database from the start?
