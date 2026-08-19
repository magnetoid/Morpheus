# Migrating between Morpheus versions

One section per release that breaks something an integrator depends on, newest
first. If a version isn't listed, it shipped no breaking change to a surface in
[`docs/API_STABILITY.md`](API_STABILITY.md).

---

## v0.50.0 — index rules, and pagination that tells the truth

**Who this affects:** anyone whose app publishes a paginated listing, anyone who
set `SiteSeoSettings.noindex_query_params`, and any theme or app that assumed an
out-of-range `?page=` renders page 1.

### Out-of-range page numbers now 404

`/products/?page=999` used to answer `200` with page 1's products. It now
returns `404`, as does a page number that is not a number. This is the fix for a
live defect: Django's paginator clamps out-of-range numbers, so every integer
anyone appended became a separate indexable page claiming — via a self-referential
canonical — to be the original.

If you paginate a listing of your own, use the same shape:

```python
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404

try:
    page_obj = Paginator(qs, per_page).page(request.GET.get('page') or 1)
except (EmptyPage, PageNotAnInteger):
    raise Http404('No such page of results.') from None
```

…and **put `page_obj` in your template context**. The canonical now trusts
`?page=` only when a real paginator is present, so a listing that paginates
without exposing `page_obj` would canonicalise all of its pages onto page 1.
(The reverse case is what shipped: a listing with no paginator echoed `?page=`
into its canonical anyway.) `?page=1` is 301'd to the clean URL, and page 2
onwards gets `— Page N` appended to its title.

### `noindex_query_params` is superseded

Query-parameter policy now lives in one `IndexRule` row per parameter, edited at
**SEO → Index rules**, with four policies: consolidate, no-index, index only
listed values, and block in robots.txt. Your existing
`SiteSeoSettings.noindex_query_params` list **still applies** — it is read as an
implicit no-index rule, and any real rule for the same parameter overrides it —
but the field goes away with the column in a future release. Move your entries
across when convenient.

One behaviour change comes with it, and it is a fix: a no-indexed parameter page
is now **canonical to itself**. Previously it was `noindex` *and* canonical to
the bare category — two contradictory claims about two URLs, and the documented
risk is that the no-index is applied to the canonical target, i.e. the category.

### robots.txt is contributed, not hardcoded

`/cart/`, `/checkout/` and `/auth/` now come from the `storefront` app through
the `SEO_ROBOTS_RULES` filter (`value` is a `core.robots.RobotsDocument`; call
`disallow()` / `allow()` / `sitemap()` and return it). The rendered file is
unchanged. If your app publishes a private surface, contribute it rather than
asking for an edit to the seo app.

---

## v0.49.0 — products with variants are described as one item

**Who this affects:** nobody has to change anything. This adds markup that was
missing and fixes a case where it disappeared.

### What changed

A product sold in several versions — print and ebook, or several sizes — is now
described as a **ProductGroup** carrying its variants, each with its own price
and its own real stock, rather than a single Product node that mentioned none of
them. The code for this existed since v0.30 and had never run on a product page:
it was guarded on the database row while the page renders a GraphQL payload.

Products on sale now publish their **previous price**, so Google can show the
saving. It is emitted only when the compare-at price is genuinely higher than
what is being charged — a leftover compare-at price equal to the price is not a
sale and is not advertised as one.

### A bug worth knowing about

One unguarded read of a deferred money field raised `KeyError` (djmoney's
behaviour, which `getattr`'s default does not catch), and the graph's per-node
guard turned that into a product page with **no Product markup at all** — a 200
with the whole node missing. Money fields are read defensively now. If you build
JSON-LD of your own from a partially-loaded row, do the same.

---

## v0.48.0 — product markup states only what is true

**Who this affects:** anyone relying on the shipping, return-policy or
availability values in the storefront's Product JSON-LD, and any app reading
`plugins.feed_mapping.availability_to_schema`. Storefront HTML, GraphQL, REST
and webhooks are unaffected.

### What changed

The Product offer used to carry a complete shipping and return policy that the
SEO app assembled from configuration keys **nothing ever wrote** — they were not
in any settings schema and had no writer anywhere in the tree. Every store
published the same invented policy, and because the free-shipping threshold
defaulted to the truthy string `'0'`, every product page advertised **free
shipping on everything**, whatever the shipping app actually charged.

Those properties now come from the apps that own the data:

| Property | Comes from |
|---|---|
| `offers.shippingDetails` | `shipping` — the cheapest active `ShippingRate` per zone, with its real price, destination countries and transit estimate |
| `offers.hasMerchantReturnPolicy` | `returns_portal` — its configured return window, with the store's country from Settings → General |
| `offers.availability` | `inventory` — real stock per variant, including backorder policy |

Both subscribe to `SEO_JSONLD_GRAPH`. **If an owner has no data, the property is
omitted rather than defaulted.** A missing recommended property costs a warning
in Search Console; an invented one is a Merchant Center policy violation.

### Do I have to change anything?

**Only if you were depending on those values being present.** They now appear
when — and only when — they are configured:

* Configure shipping zones and rates to publish `shippingDetails`.
* Set the store country (Settings → General) to publish a return policy.
* Install/enable `inventory` for real availability; without it a product is
  reported purchasable, as before.

### Other changes in this release

- **Product pages carry their full markup again.** The page renders a GraphQL
  payload, and the markup builder skipped every database-only enrichment when
  handed one — so GTIN/ISBN identifiers, the image gallery, `aggregateRating`,
  individual reviews and the Book subtype were absent from every product page,
  and `sku` was published as `""`. It now reads the rendered payload for price
  and stock and the database row for the rest.
- **`aggregateRating` counts approved reviews only.** It aggregated every row
  while the `Review` nodes filtered, so the rating included reviews the page
  never showed.
- **`SeoMeta.sitemap_include` does something.** It shipped in v0.47.0 with no
  reader. The sitemap now honours it, and excludes `noindex` pages regardless.
- **`plugins.feed_mapping.availability_to_schema` consults `inventory`.** It
  previously read `stock_status` / `is_in_stock` off `catalog.Product`, which has
  neither, so it answered "in stock" for the entire catalogue — in the channel
  feeds as well as the markup.

---

## v0.47.0 — per-entity SEO has one owner, and one editor

**Who this affects:** anyone reading or writing `catalog.Product`'s SEO columns
(or `Category`/`Collection`'s `meta_title` / `meta_description`) from outside
this repo, and any app that read the `seo.ai_answer` metafield. Storefront
output, GraphQL, REST, MCP and webhooks are unaffected.

### What changed

A product's SEO lived in **two** places: thirteen native columns on `Product`,
edited through a block hardcoded in the dashboard's product form, and the
generic `SeoMeta` overlay, edited through a panel that only CMS pages used.
`SeoMeta` won at render time — and because `autofill_meta_for` creates a
`SeoMeta` row for every product on creation, seeded with the product's own
*name*, a merchant who typed a meta title into the product form watched the
storefront keep showing the plain name. The edit was stored and ignored.

As of v0.47 **`SeoMeta` is the single owner**, and one panel edits it for
products, categories, collections and CMS pages alike — contributed into each
form through `PRODUCT_FORM_CARDS` and the new `CATEGORY_FORM_CARDS`,
`COLLECTION_FORM_CARDS` and `PAGE_FORM_CARDS`.

### Do I have to change anything?

**Reading: no.** The native columns are still read as a fallback, and
`resolve_meta` resolves the same way it always did — except that a value a human
typed now beats one the platform autofilled, whichever table it is in.

**Writing: yes, eventually.** Writing `product.meta_title` still works today but
is deprecated: the panel writes `SeoMeta`, and once an entity has a merchant-
edited row the native column is no longer consulted. Write through `SeoMeta`:

```python
from django.contrib.contenttypes.models import ContentType
from plugins.installed.seo.models import SeoMeta

SeoMeta.objects.update_or_create(
    content_type=ContentType.objects.get_for_model(type(product)),
    object_id=str(product.pk),
    defaults={'title': 'A title', 'auto_filled': False},
)
```

The native columns are removed in a later release. To consolidate existing data
now:

```bash
python manage.py seo_backfill_meta --dry-run   # report
python manage.py seo_backfill_meta             # apply
```

It only fills blanks (and replaces values the platform autofilled), so it is
safe to re-run and cannot overwrite a merchant's edit.

### Other changes in this release

- **`seo.ai_answer` metafield → `SeoMeta.ai_answer`.** The metafield is still
  read as a fallback; the panel writes the column.
- **`<meta name="keywords">` is no longer emitted.** Engines have ignored it
  since 2009, and the field now holds the merchant's *internal* focus keyword,
  which the editor promises is not published.
- **Product pages declare `og:type=product`** instead of `website`. Nothing had
  ever written the field; the non-blank default outranked the page kind.
- **`Redirect` gained `match_type` (exact / prefix / regex), `source`, and 410**,
  and `from_path` is unique per match type rather than globally. A redirect
  target must now be site-relative — an absolute URL is refused rather than
  served as a `Location` header.
- **`SeoPage` moved to `core.seo_page`.** Import it from there when answering
  `SEO_RESOLVE_PAGE`; `plugins.installed.seo.pages.types` re-exports it.
- **Every `/dashboard/seo/…` view now requires `seo.read`, and writing requires
  `seo.write`.** Enforcement still defaults to log-only, so nothing is denied
  until a merchant switches rbac to `enforce`.

---

## v0.46.0 — the `<head>` is rendered by one core tag

**Who this affects:** anyone maintaining a **theme** outside this repo, and any
app that emitted `<head>` markup of its own. Merchants, the storefront, the
REST/GraphQL/MCP surfaces and webhook payloads are unaffected.

### What changed

SEO markup used to be the theme's job: `base.html` called `{% seo_meta %}`, page
templates called `{% seo_product_jsonld %}`, `{% seo_breadcrumb_jsonld %}` and
two dozen siblings, and every one of them wrote HTML directly. A theme that
skipped a call silently shipped a page with no canonical; a theme and a page
that both made one shipped duplicates (the product page really did emit two
`og:type` tags).

Now core builds a **head document** and fires `STOREFRONT_HEAD`; the seo app
fills it in. Themes call one tag:

```django
{% load morph %}
{% block seo %}{% storefront_head %}{% endblock %}
```

and declare `head_contract = 1` on their theme class.

### Do I have to change anything?

**Not immediately.** The old tags still work. On a page that has called
`{% storefront_head %}` they render nothing (so a half-migrated theme cannot
double-emit); on a page that has not, they behave exactly as before.

They are **deprecated** and will be removed in a later release. To migrate:

1. Replace the `{% seo_meta … %}` call in `base.html` with `{% storefront_head %}`.
   Pass your fallback copy as `title=` / `description=` if your home page needs it.
2. Delete every other `{% seo_*_jsonld %}`, `{% seo_*_og %}`,
   `{% seo_verification_metas %}`, `{% seo_llms_link %}`, `{% seo_hreflang %}`,
   `{% seo_pagination_links %}` and `{% seo_preconnect %}` call from your templates —
   all of that is in the document now.
3. Delete per-page `{% block seo %}` overrides that existed only to set
   `robots="noindex, …"`. Indexability is decided per page kind (cart, checkout,
   account and internal search are handled for you).
4. Remove any hardcoded shop name from titles: the brand comes from
   Settings → SEO / Settings → General and is applied at render.
5. Set `head_contract = 1` and run `manage.py test themes.test_head_contract`.

Tags that are NOT deprecated: `{% seo_title %}` (a string helper),
`{% seo_responsive_image %}`, `{% seo_meta_panel %}` (dashboard), and
`{% seo_ai_answer_block %}` (page body, not head).

### Two behaviour changes worth knowing

- **`robots.txt`, `sitemap*.xml`, `llms.txt`, `agents.md`, the feeds and
  `/.well-known/security.txt` are no longer language-prefixed.** On a
  multi-language store they used to resolve at `/fr/robots.txt` as well, which
  published a second copy of every discovery file per language. Only the
  unprefixed URLs answer now.
- **The IndexNow key file** is served at `/<key>.txt` only for a key matching
  the protocol's hex shape. The previous catch-all pattern shadowed any other
  root-level `.txt` route.

---

## v0.42.0 — "apps", not "plugins"

**Who this affects:** anyone maintaining an app (plugin) outside this
repository, or tooling that imports the registry. **Nobody else.** If your only
Morpheus code lives in `plugins/installed/` in this repo, it was migrated for
you — every one of the 108 shipped apps was updated in the same commit.

**Who this does not affect:** merchants, the storefront, the REST/GraphQL/MCP
surfaces, webhook payloads, and `MorpheusEvents.*` hook constants. No STABLE
surface from `API_STABILITY.md` changed. Your `.env` does not need editing.

### What changed

| Before | After |
|---|---|
| `plugins/installed/<name>/plugin.py` | `plugins/installed/<name>/app.py` |
| `from morpheus.plugin import Plugin, StorefrontBlock, …` | `from morpheus.app import Plugin, StorefrontBlock, …` |
| `from plugins.registry import plugin_registry` | `from plugins.registry import app_registry` |
| `PluginRegistry` | `AppRegistry` |
| `settings.MORPHEUS_DEFAULT_PLUGINS` | `settings.MORPHEUS_DEFAULT_APPS` |
| `settings.MORPHEUS_EXTRA_PLUGINS` | `settings.MORPHEUS_EXTRA_APPS` |
| `settings.MORPHEUS_PLUGINS_DIR` | `settings.MORPHEUS_APPS_DIR` |

**Deliberately unchanged** — these are not oversights:

- the directory `plugins/installed/<name>/`
- the base class `MorpheusPlugin` (still exported as `Plugin`)
- the `MORPHEUS_EXTRA_PLUGINS` **environment variable**, which is still read as
  a fallback. It lives in your deployment environment, not the repo, so
  renaming only the code would have silently dropped a live deployment's extra
  apps with no error anywhere. Set `MORPHEUS_EXTRA_APPS` when convenient; the
  old name keeps working.

### Find every reference in your codebase

```bash
grep -rnE 'morpheus\.plugin\b|\bplugin_registry\b|\bPluginRegistry\b|MORPHEUS_(DEFAULT|EXTRA)_PLUGINS|MORPHEUS_PLUGINS_DIR' \
  --include='*.py' --include='*.html' --include='*.md' .

# and the manifest filename itself
find . -name 'plugin.py' -path '*/plugins/installed/*'
```

### Apply the rename

```bash
# 1. the manifest file
for f in path/to/your/apps/*/plugin.py; do git mv "$f" "${f%plugin.py}app.py"; done

# 2. the symbols  (\b after 'plugin' protects the 'morpheus.plugins' logger name)
grep -rlE 'morpheus\.plugin\b|\bplugin_registry\b|\bPluginRegistry\b|MORPHEUS_(DEFAULT|EXTRA)_PLUGINS|MORPHEUS_PLUGINS_DIR' \
  --include='*.py' --include='*.html' . \
| xargs perl -pi -e '
    s/\bmorpheus\.plugin\b/morpheus.app/g;
    s/\bplugin_registry\b/app_registry/g;
    s/\bPluginRegistry\b/AppRegistry/g;
    s/\bMORPHEUS_DEFAULT_PLUGINS\b/MORPHEUS_DEFAULT_APPS/g;
    s/\bMORPHEUS_EXTRA_PLUGINS\b/MORPHEUS_EXTRA_APPS/g;
    s/\bMORPHEUS_PLUGINS_DIR\b/MORPHEUS_APPS_DIR/g;
  '
```

### Verify

```bash
python manage.py check          # every app must still be discovered
python manage.py morph_versions # your app must appear with its version
```

A missed manifest rename fails **silently**: the registry simply doesn't find
the app, so it vanishes from the catalogue instead of raising. Check the count
in the boot log (`Plugin system ready: N active`) against what you expect.

### New in the same release

Two optional manifest fields — see
[`docs/PLUGIN_DEVELOPMENT.md`](PLUGIN_DEVELOPMENT.md#4-metadata-reference):

- `protected = True` — no surface offers a disable (merchant toggle *and* AI
  tools both refuse). One-way: a manifest can add protection, never remove it.
- `system = True` — hide the app from the Apps catalogue.
