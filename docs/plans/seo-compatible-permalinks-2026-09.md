# SEO-compatible Permalinks Implementation Plan

> **For Janus:** Execute with isolated implementation/review lanes; do not bypass CMS Menus.

**Goal:** Add a General Shop → Permalinks configuration that is the URL source of truth for dynamic storefront entities, while retaining the existing CMS Menus UI as the sole navigation-structure editor and preserving SEO canonicals, sitemap paths, redirects, JSON-LD and hreflang.

**Architecture:** Store safe path templates in `StoreSettings`; expose a single resolver service which only returns normalized local paths. CMS `MenuItem.url` remains an explicit static override. Themes consume CMS `header_menu`/`mobile_menu`; dynamic MegaMenu entries ask the resolver for entity paths. Existing named Django routes remain runtime fallback until corresponding views are migrated.

**SEO contract:** A path-template change is not auto-applied to routes. The initial release makes every generated UI URL, canonical and sitemap contribution read the same resolver; applying a changed public entity pattern requires a separate route/redirect migration, creating 301 records through the SEO plugin and validating reverse canonical/hreflang links.

**Files likely to change:**
- `core/models.py`, `core/migrations/00xx_store_settings_permalink_templates.py`
- `core/services/permalinks.py` (new) and `core/tests/test_permalinks.py` (new)
- `plugins/installed/admin_dashboard/forms/settings.py`
- `plugins/installed/admin_dashboard/templates/admin_dashboard/settings_category.html`
- `plugins/installed/booking_marketplace/context_processors.py`
- `themes/library/montenegro/templates/storefront/base.html`
- relevant `seo` sitemap/canonical/hreflang hooks and tests only after resolver integration is proven.

## Tasks
1. Add a JSON `permalink_templates` setting with immutable defaults and a resolver that validates allowed route types and placeholders; write failing tests for invalid/out-of-domain paths and required `{slug}` placeholders.
2. Add a compact General settings Permalinks panel, preview data and validation feedback; retain existing General fields unchanged.
3. Integrate resolver into booking/places dynamic navigation under namespaced `montenegro_nav`; do not overwrite generic `nav_categories`.
4. Render existing CMS header/mobile menus in Montenegro and map only recognized dynamic menu kinds to named `montenegro_nav` panels; use explicit MenuItem URLs unchanged.
5. Add an SEO adapter that derives canonical/sitemap URLs using the resolver only for entities whose public route is actually resolver-backed. On a future pattern change, create SEO `Redirect` 301 rules, invalidate caches, verify sitemap, canonical and hreflang reciprocity.
6. Run focused unit/template/SEO tests, `manage.py check`, then a public smoke audit before commit/push.

**Safety:** no mass rewrite of the already indexed Montenegro URL space and no automatic redirect creation in the first UI-only rollout.
