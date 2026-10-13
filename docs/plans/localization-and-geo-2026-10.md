# Localization step 1 (real translations) and step 2 (geolocation) — design

Owner, 2026-10-13: "the language and localization system should have a geolocation option and
redirects as a feature, and what else is needed?" Agreed order: make translations real first,
then geolocation (a Serbian visitor sent to `/sr/` must find Serbian content there).

## Today (measured 2026-10-13)

- `/sr/` routing works (`i18n_patterns`, `prefix_default_language=False`) and internal links stay
  in the language tree (`core/i18n_links.py`). Theme strings are translated (`locale/sr`).
- **Translated content is never shown.** `core.i18n.Translation` (object, field, language) and its
  services and template helpers exist; no view, template or GraphQL resolver reads them. Products,
  categories, CMS pages, journal posts and menus render in the core language under `/sr/`.
- **Languages come from the server** (`MORPHEUS_LANGUAGES` env). The dashboard's language settings
  write keys nothing reads, and `set_enabled_languages` fails (`StoreSettings.set` does not exist).
- The Translations page is always empty (`localization/views.py` reads `t.language`, the field is
  `language_code`). `Content-Language` says the core language on `/sr/` pages.
- No geolocation: only `markets` reads `CF-IPCountry`, and nothing uses the market it resolves.

## Step 1 — translations that show

**Languages: the dashboard decides, without a restart.** `settings.LANGUAGES` becomes every language
Morpheus supports (14), so routing exists for all of them; which are *on* is a store setting
(Settings → Languages), read through one function, `core.i18n.enabled_languages()`. A request for a
language that is not on gets a 404 (it is not a page of this store). The switcher, hreflang and the
sitemap list only enabled languages. `MORPHEUS_LANGUAGES` stays as the default for a store that has
not chosen yet, so nothing changes on deploy.

**Content: localized where it is loaded, not in 4 themes × N templates.** One function,
`core.i18n.localize(obj, fields)`, returns the object with the request language's translations
applied (falling back field by field to the core language). It is called where storefront data is
built: product dicts (GraphQL `Product` resolvers: name, short/long description, SEO title and
description), category pages (name, intro, long description), CMS pages, journal posts, menus and
the booking marketplace's listings, places and events. Themes keep printing `product.name`.

**Untranslated pages are not duplicates.** A `/sr/` page whose object has no Serbian text renders
the English text (better than a 404), but its canonical points to the core-language URL and it is
left out of hreflang and the sitemap, so search engines see one page, not two copies.

**Editing and coverage.**
- The product, category, page and post editors get language tabs (the core language plus each
  enabled one).
- Settings → Languages shows coverage per language ("Serbian: 412 of 1,027 products, 61 of 71
  categories…") and links each gap.
- Linda translates with `i18n.translate` (any translatable object); her text is saved flagged
  `is_machine_translated` and listed for review until a person edits or approves it. Writes need the
  merchant's yes, like every write.

**Fixes on the way:** `StoreSettings` gains a typed key/value store for these settings; the
Translations page reads `language_code`; `Content-Language` follows the request language.

## Step 2 — geolocation

**What is detected.** The visitor's country (Cloudflare's `CF-IPCountry` when the store is behind
it; otherwise a local country database, DB-IP Lite, CC-BY 4.0, refreshed monthly by a Celery task —
no third-party call per request) and their browser languages (`Accept-Language`). The language
suggested is the first browser language the store has enabled; failing that, the country's language
(the market's `default_locale`, or a country → language table).

**Per-store mode** (Settings → Languages → Visitors):
- **Off.**
- **Suggest** (default): a small bar, "This page is in Srpski — Switch / Stay in English". Dismissing
  or choosing is remembered.
- **Redirect:** the first page view is sent to the suggested language's version.

**Rules that keep search and caching safe:**
- Search engines and other crawlers are never redirected (`is_crawler_user_agent`); Google advises
  against IP-based redirects for exactly this reason, which is why Suggest is the default.
- Only the first visit, only from a core-language URL, only to a page that exists in the target
  language. A language the visitor chose (cookie from the switcher) always wins; a prefixed URL
  (`/sr/…`) is never redirected away.
- Pages stay CDN-cacheable: the decision is made by a tiny uncached request (`/i18n/suggest/`, like
  `/csrf/`) and applied by a small script, so a cached page never carries one visitor's redirect to
  the next. Montenegro's pages are edge-cached, so this is not optional.
- Staff can preview as a country (`?geo=RS`, staff only) on any page.

**Linda:** `i18n.routing` reads and changes the mode and the enabled languages, with the merchant's
yes.

## Not in these two steps

Step 3 (markets that change currency and prices through checkout, daily exchange rates, one price
system instead of markets + channels) and step 4 (emails in the customer's language, sitemap
language alternates for every object, translated URL slugs, right-to-left) follow.

## Tests that prove it

- A product, category, CMS page and journal post render their Serbian text under `/sr/` and their
  English text under `/`; a missing field falls back; GraphQL returns the same.
- An untranslated object's `/sr/` page canonicalizes to the English URL and is absent from hreflang
  and the sitemap.
- Turning a language off in the dashboard removes it from routing (404), the switcher, hreflang and
  the sitemap, without a restart.
- Suggest: the endpoint is never cached and answers per visitor; a crawler gets nothing; a chosen
  language is never overridden; a prefixed URL is never redirected.
- Redirect mode sends a first-time Serbian browser on `/` to `/sr/`, once.
