# Visual schema editor (structured data) — 2026-06

**Goal (user):** "improve schema control on pages, website products etc … i don't
need manual schema adding code i need nice interface very easy to control."
Chosen approach: **full visual schema editor** — pick a schema.org `@type` from a
friendly list, fill labeled fields (incl. repeatable rows), no JSON typing.
Works for products **and** CMS pages (any object with a SeoMeta).

## What already exists (don't rebuild)

- `seo` plugin auto-generates rich JSON-LD (Product, Article, Organization,
  WebSite, BreadcrumbList, reviews) — zero input needed. That stays.
- `SeoMeta` (generic FK, `content_type`+`object_id`) is the per-object SEO row.
  Its `structured_data` (dict) is **merged** into the one auto payload —
  single-`@type` only, can't hold independent FAQ + HowTo blocks.
- `seo_meta` template tag (templatetags/seo.py:199) is called from **base.html
  `{% block seo %}` on every page** and renders the `<head>` meta + the merged
  `structured_data` as ONE `<script type="application/ld+json">`
  (`_helpers.py:ResolvedMeta.to_html`).
- `meta.py:resolve_meta(obj)` builds `ResolvedMeta` (auto + native + SeoMeta merge).
- `seo_faq_jsonld` tag + `faq_jsonld()` service already exist.

## The make-or-break wiring

Piggyback the existing per-page head injection so authored schema renders
everywhere with **no theme edits**:

1. `SeoMeta.schema_blocks = JSONField(default=list)` — a **list** of fully-formed
   JSON-LD block dicts (each `{"@context":"https://schema.org","@type":…}`).
   Migration: additive JSONField default=list → safe (no FK/cast).
2. `ResolvedMeta.extra_blocks: list` (new). `resolve_meta` populates it from
   `meta.schema_blocks`. `to_html()` emits **one `<script>` per block** after the
   merged `structured_data`.
3. Because `seo_meta` already runs on every storefront page for `seo_object`,
   any product/page/category with `schema_blocks` emits them automatically.

## Registry — `seo/schema_types.py`

Declarative spec; the editor renders forms from it and a serializer turns form
data → JSON-LD block. Initial curated set (Google rich-result types):

- **FAQPage** — repeatable {question, answer}
- **HowTo** — name, totalTime(ISO8601 via friendly mins), repeatable steps{name,text}, repeatable tools/supplies
- **Event** — name, startDate, endDate, location{name,address}, url, offers{price,currency,url}
- **Recipe** — name, repeatable ingredients, repeatable steps, cookTime, prepTime, image, yield
- **Article / NewsArticle** — headline, author, datePublished, image
- **VideoObject** — name, description, thumbnailUrl, uploadDate, contentUrl/embedUrl
- **Course** — name, description, provider
- **Custom** — repeatable {property, value} escape hatch (still no raw JSON object)

Each type: `{key, '@type', label, icon, help, fields:[{name,label,kind,help,required,
repeatable_of?}]}`. `kind ∈ text|textarea|url|date|datetime|number|duration_min|group`.
Helpers: `build_block(type_key, form_data) -> dict` (validate + shape JSON-LD),
`registry_json()` (the spec the editor JS consumes).

## Editor — seo dashboard

- View `schema_editor(request, app_label, model, pk)` →
  `dashboard/seo/schema/<app_label>/<model>/<pk>/` (namespace `seo_dashboard:schema_editor`).
  GET: load SeoMeta (or none), render editor with `registry_json` + existing blocks.
  POST: parse posted blocks JSON (hidden field the JS maintains) → `build_block`
  each → save to `SeoMeta.schema_blocks` (get_or_create the SeoMeta row).
- Index page `schema_index` (nav: SEO → "Structured data", order ~57): lists
  objects that have schema_blocks + a small picker (recent products / pages) to
  open the editor.
- Template + vanilla JS (CSP already allows what the dashboard needs): add-block
  (`@type` picker) → adaptive fields from registry → repeatable rows → live
  JSON-LD preview → serialize to hidden field on submit.

## Entry points (disable-guarded)

- product_form.html: add a prominent **"✦ Visual schema editor"** link to the
  per-object editor, guarded `{% plugin_enabled "seo" %}`. Keep the raw
  `structured_data` textarea but demote to a `<details>` "Advanced (raw JSON)".
- cms page_form.html: same link in the SEO block (shown only once the page has a
  pk), guarded.

## Tests (`seo/tests/test_schema_editor.py`)

- registry: `build_block('FAQPage', {...})` → correct `mainEntity` shape.
- editor POST saves blocks to SeoMeta.schema_blocks; GET renders them.
- emission: a product with schema_blocks → `seo_meta` HTML contains a
  `<script type="application/ld+json">` per block (contract test against
  `resolve_meta`/`to_html`, the real path).
- unknown type rejected; disable-guard (link gone when seo off) covered globally.

## Verify → ship

`DATABASE_URL=sqlite … test seo`, ruff, `manage.py check`, makemigrations --check,
disable-guards. Hold push until user says "ship" (batch rule).

---

## Update — 2026-06-20: Book type + Google Book structured data

Two things shipped together (both per Google's structured-data rules):

1. **Schema editor gained a `Book` type** and **Article was enriched**
   (`schema_types.py`): Book fields = name, author, isbn, book_format
   (→ schema.org Hardcover/Paperback/EBook/AudiobookFormat), in_language,
   date_published, book_edition, url, same_as. Article now also emits
   description, publisher (Organization), dateModified, url. Builders +
   `_BUILDERS` registration; covered by `test_schema_editor.py`.

2. **On-PDP Google Book structured data** — the Work → `workExample`
   (Edition) → `potentialAction` (ReadAction → EntryPoint + Offer) model
   from developers.google.com/.../structured-data/book. This is **separate
   from the Product graph** (Product drives shopping; Book describes the
   title). Built by `jsonld.book_jsonld(data)` — a *pure* dict-in/dict-out
   function (`test_book_jsonld.py`); the PDP view assembles the dict in
   `catalog._book_jsonld_data()` from `book_attrs()` + identifier metafields
   (relation queries by PK) + the GraphQL dict's price — **never** the
   product's deferred `price` field (the djmoney-KeyError 500 landmine;
   guarded by `storefront/tests/test_pdp_book_jsonld.py`, which loads the row
   with the same `.only()` the view uses). Emitted via
   `{% seo_book_jsonld book_jsonld_data %}`.

   Merchant knobs live in `PluginConfig['seo']` (no migration):
   `book_structured_data` (toggle), `book_offer_category`
   (purchase/rental/free/subscription/nologinrequired), `book_eligible_region`
   (ISO-3166 alpha-2, falls back to shipping country), `book_action_platforms`
   (desktop,android,ios). ISBN-10 is auto-converted to ISBN-13.

   **Eligibility caveat:** valid on-page Book markup helps Google understand
   the title and is a prerequisite, but the Book Actions / knowledge-panel
   *rich result* is a gated program (feed + enrollment) — the markup alone
   doesn't guarantee the actionable result.
