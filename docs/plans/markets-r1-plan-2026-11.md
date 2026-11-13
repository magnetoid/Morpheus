# Markets release 1 — implementation plan (v0.165.0)

**Goal:** markets get real prices and rates, editable by the merchant and Linda;
the storefront offers a page's other language. No shopper sees a currency change
in this release.

**Spec:** `docs/plans/markets-currency-language-2026-11.md` (approved by the owner
2026-11-13, time zone as the country signal). Release 1 = its §1, §4, §6, §8–10.
Release 2 (detection, price swap, selector, charging) is a later plan.

**Branch:** `feat/markets-rates`, stacked on `feat/seo-audit-tools` (#161, v0.164.0).

## Global constraints

- Plugin contract (CLAUDE.md): markets owns market data; core never imports
  `plugins.installed.*`; no plugin imports another's models except declared
  `requires`; cross-app through `core.hooks`.
- Every new setting has a reader in this release; every new scope is in
  `AVAILABLE_SCOPES`, `CAPABILITY_FOR_SCOPE` (`core/assistant/gates.py`) and
  `gates.LINDA_SCOPES`; every write tool has `requires_approval=True`.
- Migrations additive, `db_default` on new NOT NULL columns.
- Store currency = `settings.STORE_CURRENCY` (USD on dotbooks, Supernatural and
  Irving; EUR on Montenegro and Croatia; matches their products).
- Outbound HTTP only through `core.net.outbound_request`.
- Storefront scripts carry `nonce="{{ csp_nonce }}"`; behaviour via
  `addEventListener`, never `on…=` attributes; no inline `style=` in new markup.
- Tests: `DATABASE_URL='sqlite:///:memory:' python manage.py test <labels>`;
  `ruff check` / `ruff format --check` with ruff 0.15.8.
- Copy for merchants: plain words, the assistant is "Linda" (help.md rules,
  `release_notes/tests/test_help_*.py`).

## Review focus

1. A rate the merchant typed is never overwritten by the ECB fetch.
2. A `localized_prices` value of `0` (Supernatural's gift mug) is not a price.
3. Zero-decimal currencies (JPY) and rounding `ninety_nine` on them.
4. A market whose currency has no rate cannot be switched on, from the page or Linda.
5. The language bar never shows on a page that does not exist in the offered
   language, and never for a crawler (no JS) or a single-language store.

---

### Task 1: Currency conversion in core

**Files:** `core/pricing.py`, `core/templatetags/morph.py` (`convert_money`),
test `core/tests/test_currency_convert.py`.

**Produces:**
- `core.pricing.store_currency() -> str` — `settings.STORE_CURRENCY` upper-cased.
- `core.pricing.exchange_rate(base: str, quote: str) -> Decimal | None` — from
  `core.models.ExchangeRate`: direct pair; else 1/inverse pair; else across the
  store currency (base→store × store→quote, each direct or inverse); `1` for the
  same currency; `None` when none of these exist.
- `core.pricing.convert(money: Money, currency: str) -> Money | None` — amount ×
  rate, quantized to the currency's minor unit (`babel.numbers.get_currency_precision`,
  `ROUND_HALF_UP`); `None` when no rate.
- `core.pricing.quantize(amount: Decimal, currency: str) -> Decimal`.

`convert_money` (the `|convert` filter) calls `convert` and returns the input when
it gets `None`.

Tests: direct, inverse, cross through the store currency, same currency, missing
→ `None`, JPY → 0 decimals, filter returns input when no rate.

### Task 2: The market model and its one write path

**Files:** `plugins/installed/markets/models.py`, migration `0003_market_rounding.py`,
new `plugins/installed/markets/services.py` functions (keep `resolve_market`
untouched — release 2 rewrites it), test `markets/tests/test_save_market.py`.

**Produces:**
- `Market.rounding`: `CharField(max_length=12, choices=[('exact','Exact'),('whole','Whole number'),('ninety_nine','Ends in .99')], default='exact', db_default='exact')`.
- `markets.services.save_market(data: dict, market: Market | None = None) -> Market`
  raising `django.core.exceptions.ValidationError` with a plain message. Validates:
  code (slug, unique), label, currency in `babel.numbers.list_currencies()`,
  each country a 2-letter code Babel knows (`babel.Locale('en').territories`),
  adjustment between -90 and 500, rounding in choices; refuses `is_active=True`
  when `currency != store_currency()` and `exchange_rate(store, currency)` is `None`
  ("Add an exchange rate for EUR first"). Keeps the existing single-default rule.
  Used by the dashboard form and Linda (Task 6).
- `markets.services.delete_market(market) -> None`.

Tests: each refusal, success, the rate rule (with and without an `ExchangeRate`).

### Task 3: One market price function

**Files:** new `plugins/installed/markets/pricing.py`, test `markets/tests/test_market_price.py`.

**Produces:** `market_price(product, market, variant=None) -> Money | None`:
1. currency = store currency → the store price (`variant.effective_price` when the
   variant has one, else `variant.price`, else `product.price`) through
   `core.pricing.apply_price_filter(price, product=product, customer=None)`.
2. a `ProductMarketPrice` for (market, product) → its price (filtered as above, no
   rounding: the merchant typed it).
3. else `localized_prices[market.currency]` on the variant, then the product, when
   it parses to a Decimal **> 0** → that price (filtered, no rounding).
4. else the filtered store price × (1 + `base_price_adjustment_pct`/100), converted
   (`core.pricing.convert`), then rounded by `market.rounding`:
   `exact` → minor unit; `whole` → integer `ROUND_HALF_UP`; `ninety_nine` →
   `floor(x) + 0.99` (integer for a zero-decimal currency).
5. `None` when no rate exists.

Tests: each step; `0` in `localized_prices` ignored; Supernatural-shaped data
(`{'RSD': '1050'}` with an RSD market); JPY with `ninety_nine`; adjustment +10 %.

### Task 4: Exchange rates — ECB fetch, manual rates, health

**Files:** new `plugins/installed/markets/rates.py`, new `plugins/installed/markets/tasks.py`,
`plugins/installed/markets/app.py` (beat, setting, health check), test
`markets/tests/test_rates.py`.

**Produces:**
- `rates.ECB_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'`.
- `rates.fetch_ecb() -> dict` — GET through `outbound_request('GET', ECB_URL, timeout=20)`,
  parse `Cube[@currency][@rate]` (ElementTree; fixed trusted URL), add `EUR: 1`,
  then for each currency X ≠ store currency write
  `ExchangeRate(base=store, quote=X, rate=EUR→X / EUR→store, source='ecb')`
  (8 decimals) unless a row for that pair has `source='manual'`. Returns
  `{'written': n, 'kept_manual': [...], 'date': 'YYYY-MM-DD'}`. Raises on HTTP or
  parse failure (caller logs).
- `rates.set_manual_rate(currency: str, rate: Decimal | None) -> None` — `None`
  deletes the manual row (the next fetch fills it if ECB lists the currency).
- `rates.rate_rows() -> list[dict]` — per active market currency: rate, source,
  `fetched_at`, `stale` (older than 3 days or missing).
- Task `markets.fetch_exchange_rates` (`@shared_task(name='markets.fetch_exchange_rates')`
  in `tasks.py`): does nothing when setting `rate_source == 'manual'` or no active
  market has a currency other than the store's; else `fetch_ecb()`.
- `app.py`: `register_celery_beat('markets.fetch_exchange_rates', {...daily 15:30 UTC...})`
  in `ready()`; schema key `rate_source` (`enum ['ecb','manual']`, default `'ecb'`,
  title "Where exchange rates come from"); `HEALTH_CHECKS` subscriber
  "Exchange rates are current" — fails naming each active market whose rate is
  stale or missing; passes when no market needs one.

Tests (outbound mocked with a small ECB XML): rates written across a USD store and
an EUR store; manual row kept; `None` clears; task skips on `manual` and with no
foreign market; health check both ways; the beat entry names a registered task.

### Task 5: Markets dashboard

**Files:** `plugins/installed/markets/views.py`, `templates/markets/edit.html`,
`templates/markets/list.html`, `urls.py`, test `markets/tests/test_dashboard.py`.

- Form posts go through `save_market` / `delete_market`; currency is a `<select>`
  of Babel's currency list (code + English name), rounding a `<select>`.
- The edit page shows, for a market whose currency differs from the store's: the
  rate (1 USD = 0.92 EUR), its source and age, a stale warning, and a form to set
  or clear a manual rate (`POST …/<id>/rate/` → `rates.set_manual_rate`), plus a
  "Fetch rates now" button (`POST /dashboard/markets/rates/refresh/` →
  `rates.fetch_ecb`, messages on failure).
- The edit page shows a price preview: the first 10 active shoppable products,
  store price → `market_price`.
- Reads `@staff_member_required`; writes also `@require_capability('catalog.write')`.
- The list shows each market's rate status.
- help.md (markets) rewritten for what is true after this release: rates, rounding,
  fixed prices, preview; shoppers still see the store currency until a later update.

Tests: boundary trio on create/edit/delete/rate/refresh; form refusal shown;
preview renders with and without a rate; every changed template compiles
(`get_template`).

### Task 6: Linda's markets tools

**Files:** `plugins/installed/markets/agent_tools.py`, `app.py`
(`contribute_agent_tools`), `plugins/installed/agent_mcp/scopes.py`,
`core/assistant/gates.py`, `core/assistant/tools/__init__.py:140` if it names
`markets.list`, test `markets/tests/test_agent_tools.py`.

- Scopes `markets.read` ("Markets · read") and `markets.write` ("Markets · write …
  affects prices shoppers will see"); `CAPABILITY_FOR_SCOPE`: `markets.read →
  catalog.read`, `markets.write → catalog.write`; both in `LINDA_SCOPES`.
- `markets.list` (now `markets.read`), `markets.get(code)` (fields, rate row, 5
  preview prices); writes, each `requires_approval=True`, scope `markets.write`:
  `markets.save` (create or update by code; fields as `save_market`),
  `markets.delete(code)`, `markets.set_product_price(code, product: id or slug,
  amount | null)`, `markets.set_rate(currency, rate | null)`,
  `markets.refresh_rates()`. Errors from `ValidationError` come back as the tool's
  error text.

Tests: each tool's happy path and refusal; scope vocabulary test
(`agent_mcp/tests/test_scopes.py`) and Linda catalogue tests stay green.

### Task 7: Drop per-market hreflang

**Files:** `plugins/installed/seo/head/builder.py` (`_market_alternates` and its
call), its tests.

hreflang stays per language; `?market=` alternates go. Update or delete the tests
that asserted them; head parity re-recorded only if a profile includes them.

### Task 8: The language bar

**Files:** `plugins/installed/localization/app.py` (setting + `global_head` block),
`templates/localization/blocks/language_bar.html`,
`static/localization/language-bar.js`, `static/localization/language-bar.css`,
`locale/sr/…/django.po|mo`, `locale/hr/…/django.po|mo`, help.md, test
`localization/tests/test_language_bar.py`.

- Setting `suggest_language` (boolean, default `false`, title "Offer a page in the
  visitor's language").
- The block renders only when the setting is on and the store has 2+ languages:
  a `<link>` to the CSS and a nonce'd `<script src defer>` plus a
  `<script type="application/json" id="morpheus-language-bar">` holding, for every
  store language, its name and three strings rendered in that language
  ("This page is also in {name}.", "Switch", "Stay") — the same for every visitor.
- The JS: reads alternates from `link[rel=alternate][hreflang]` (skip `x-default`),
  the page language from `<html lang>`, the visitor's from `navigator.languages`
  (primary subtag), the cookie `morpheus_lang_choice`; when the first preferred
  language the store has differs from the page's, has an alternate, and no choice
  is stored, it adds a bar (a `<div role="region" aria-label>` with two buttons) at
  the top of `<body>`. Switch → set the cookie (1 year, `SameSite=Lax`, path `/`)
  to that language and go to the alternate's href; Stay → set it to the page
  language and remove the bar.
- Serbian and Croatian strings added to the catalogs and the `.mo` compiled.
- help.md (localization) gains the setting.

Tests: no block when off, with one language, or for a single-language store; the
block's JSON lists each language with strings in that language; the script and CSS
files exist; template compiles; `themes/test_global_slots.py` still green. Manual
check in the in-app browser on a two-language theme.

### Task 9: Release

`python manage.py release --minor "Markets get real prices and exchange rates" -m …`
(v0.165.0); `release --check` with `RELEASE_CHECK_BASE=origin/feat/seo-audit-tools`;
CLAUDE.md gains a short convention entry (markets own prices in other currencies;
`core.pricing.convert`; manual rates win; the language bar reads hreflang);
`scripts/check_plugin_standard.py --save` if the baseline shrinks. Full suite with
all five opt-in apps before the PR.

## Deferred to release 2

- `Market.languages`, the time-zone table (spec §2) and retiring `is_default`: nothing
  reads them before detection and the price swap.
- Variant-level fixed prices, routing `orders._resolve_unit_price` through
  `market_price`, a per-request memo for `exchange_rate`, and `max_price_change_pct`
  for market prices (spec, "What release 1 built").
