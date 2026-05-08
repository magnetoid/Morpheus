"""
markets — per-country pricing, currency, and locale.

The platform already has multi-currency primitives (StoreChannel +
ProductChannelListing + ExchangeRate). What it doesn't have is a
Markets abstraction: a logical region — e.g. "European Union",
"United Kingdom", "United States" — with its own currency, default
locale, and tax/shipping policy that resolves automatically based
on the visitor's country.

Shopify Markets is the analogue. The difference here: Markets are
plugin-contributed, so a B2B or wholesale plugin can ship its own
market without forking core.

Plugin layout:
  * `Market` model — code, label, country_codes JSON, currency,
    default_locale, is_active, base_price_adjustment_pct
  * `ProductMarketPrice` — optional per-product price override per
    market (parallel to the existing ProductChannelListing)
  * Middleware — picks the active market from request.country (set
    upstream by Cloudflare via `CF-IPCountry`, or by an explicit
    `?market=` override) and stashes it on `request.market`
  * Storefront context processor — exposes the active market + a
    helper to resolve a product's market-aware price
"""
