# Collections merge — consolidate Category + Collection into one "Collections" concept

**Decision (user, 2026-05):** Full consolidation. One hierarchical
grouping concept, called **Collections**. Migrate the flat `Collection`
model into the hierarchical model, retire `Collection`.

**Status:** PLANNED — not yet executed. High blast radius + data
migration on the live auto-deploying store, so phased with a
commit + smoke between each phase.

---

## The core problem: FK vs M2M

| Model | Shape | Product link |
|---|---|---|
| `Category` (MPTTModel) | hierarchical (parent/child) | `Product.category` — **single FK** (one per product) |
| `Collection` (flat) | no hierarchy | `Product.collections` — **M2M** (many per product) |

A naive "move Collection rows into Category" loses data: a product in
3 collections can't hold 3 single-FK categories.

**Resolution:** the surviving unified model keeps **MPTT hierarchy**
AND gains **M2M membership**. Then:
- every `Product.category` assignment → a membership
- every `Product.collections` membership → a membership

No data lost. A product can be in multiple Collections, and
Collections can nest.

**Survivor:** keep the `Category` *model* (MPTT is the hard part to
build; Collection is the simpler one to fold in). Relabel it
"Collection(s)" in **all UI** (templates, nav, admin, GraphQL field
descriptions). The Python model/table name stays `Category` —
renaming it across ~79 files + FK columns is enormous churn and pure
risk for zero user-visible benefit. UI says Collections; code says
Category. Document this clearly so it's not a surprise.

> If the user later insists the *code* also be renamed, that's a
> separate, even bigger migration — out of scope here.

---

## Phases (each independently shippable + reversible until Phase 4)

### Phase 1 — additive model capability (non-destructive)
- Add `Product.collection_set` style M2M? No — reuse: add a
  `members = ManyToManyField(Product, related_name='in_collections')`
  to `Category`, OR add `Product.categories` M2M alongside the
  existing `category` FK. **Chosen:** add `Product.categories`
  (M2M → Category) so multi-membership works; keep the old `category`
  FK + `collections` M2M intact for now (dual-write window).
- Migration: schema only (add M2M table). No data moved yet.
- ✅ verify: `migrate` clean, nothing else changes behaviour.

### Phase 2 — data backfill (idempotent management command)
- `manage.py merge_collections_into_categories`:
  - For each Collection: get-or-create a top-level Category with the
    same name/slug/image (slug clash → suffix). Record mapping.
  - For each Product: add its `.category` (if set) + every mapped
    Category from its `.collections` into the new `.categories` M2M.
  - Idempotent (re-runnable; uses get_or_create + add()).
- ✅ verify: counts — every product's old category + collections are
  represented in `.categories`; spot-check 5 products.

### Phase 3 — read-path cutover (storefront + GraphQL + admin read)
- Storefront: breadcrumbs, PDP, PLP filters, `/c/<slug>/`,
  `category_detail`, home rails → read from `.categories` /
  unified Category. Relabel UI strings → "Collection(s)".
- GraphQL: `CollectionType` → alias/forward to Category;
  `collections` query returns top-level Categories; `category` field
  kept but documented as deprecated. Product `categories` exposed.
- Admin: product form uses `categories` M2M (multi-select, was the
  single category dropdown built in 751d181); collection management
  pages point at Category.
- ✅ verify: storefront pages render; GraphQL queries return data;
  Playwright smoke on home + PDP + a collection page.

### Phase 4 — retire Collection (destructive — last, behind a backup)
- Drop `Product.collections` M2M + the `Collection` model (migration).
- Remove dead Collection code paths.
- Keep `Product.category` FK? Decide: either drop it (full M2M) or
  keep as "primary collection" denormalisation. **Lean: keep** as
  `primary_category` for breadcrumb/canonical simplicity, backfilled
  from the first membership.
- ✅ verify: full test suite + live smoke. Take a DB snapshot first.

---

## Files in scope (from survey)

- `plugins/installed/catalog/models.py` — Category M2M, Product.categories, drop Collection
- `plugins/installed/catalog/graphql/{types,queries}.py` — CollectionType, collections query, Product.categories
- `plugins/installed/catalog/management/commands/` — new backfill command
- `plugins/installed/storefront/views/{home,catalog}.py` — rails, PLP filter, category/collection detail
- `plugins/installed/seo/services/{sitemaps,meta}.py` + `templatetags/seo.py` — collection sitemap entries, jsonld
- `plugins/installed/marketing/models.py` — Collection ref
- `plugins/installed/importers/adapters/shopify.py` — maps Shopify collections
- `plugins/installed/demo_data/services.py` — seeds collections
- themes/library/dot_books/templates/storefront/*.html (~7) — labels + rails
- `plugins/installed/admin_dashboard/...` product form + any collection admin

## Rollback
- Phases 1-3 are additive/dual-write → revert commits, data harmless.
- Phase 4 is destructive → DB snapshot before; rollback = restore snapshot + revert.
