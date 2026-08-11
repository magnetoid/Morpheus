# CMS Pages — WordPress-style single registry

## 1. Project Overview

- **Name:** CMS Pages manager
- **Goal:** Make the CMS Pages dashboard list the single authoritative registry of every storefront page. Editable (CMS-managed) pages get full CRUD + TipTap body editing. Hardcoded functional pages (contact, cart, checkout, etc.) are declared by their owning plugin and appear in the list as locked rows, so the list is always complete and passes the plugin-disable litmus test.
- **Target users:** Staff/merchant managing storefront content.
- **Why now:** The current list is read-only and incomplete — /about/, /shipping/, /returns/ bypass it via hardcoded storefront views + theme templates, while the CMS already has orphaned `shipping`/`returns`/`faq` Page rows that nothing links to. Two sources of truth for the same pages.

## 2. Tech Stack & Dependencies

- **Language:** Python 3.12 / Django 5.x (project standard)
- **Styling:** admin_dashboard design system (card / morph-table / pill / form-row CSS)
- **Key libraries:** TipTap 3.23.4 via esm.sh ESM imports — **no new dep**; reuse the exact wiring from [`plugins/installed/admin_dashboard/templates/admin_dashboard/product_form.html:330–487`](../plugins/installed/admin_dashboard/templates/admin_dashboard/product_form.html)

## 3. Data Models / Schemas

`Page` model in [`plugins/installed/cms/models.py`](../plugins/installed/cms/models.py) — no schema changes needed.

Key field choices (document, do not alter):

- `state` choices: `draft`, `scheduled`, `published`, `archived`
- `layout` choices: `default` (single column), `long_form`, `landing`
- `body`: HTML stored after bleach sanitisation (allowlist in models.py lines 27–65). TipTap emits HTML; `Page.save()` sanitises on write — consistent with product descriptions.
- `slug`: unique, db-indexed SlugField(200). Auto-suggested from title on new-page form (JS slugify), editable.
- `publish_at`: `DateTimeField null=True` — only respected when `state='scheduled'`.

No migration required for Phases 1–2. Phase 3 seeds new `Page` rows via a data migration (not a schema migration).

**Hardcoded-page registry** — code only, no DB model, no migration:

```python
# plugins/installed/cms/registry.py
_HARDCODED_PAGES: list[dict] = []

def register_hardcoded_page(slug: str, title: str, url: str, plugin_label: str) -> None:
    _HARDCODED_PAGES.append({"slug": slug, "title": title, "url": url, "plugin": plugin_label})

def get_hardcoded_pages() -> list[dict]:
    return list(_HARDCODED_PAGES)
```

Each owning plugin calls `register_hardcoded_page(...)` in its `AppConfig.ready()`. CMS `pages_list` view merges DB rows with registry rows at render time.

## 4. Key Features & Acceptance Criteria

### Phase 1 — Editor + row actions on editable pages

- [ ] **pages_list shows per-row actions for CMS rows.** New | Edit | Duplicate | Delete (confirm modal).
  - *Acceptance:* Navigate to `/dashboard/cms/pages/` — every CMS Page row has Edit and Delete links. A new Page created via "New" appears immediately in the list.
- [ ] **Edit form.** Fields: title, slug (auto-slugified from title, editable), excerpt, layout picker, state picker, publish_at (datetime, shown only when state=scheduled), body (TipTap).
  - *Acceptance:* Save a page with body containing `<h2>`, `<ul>`, and a link — the public `/p/<slug>/` renders all three correctly.
- [ ] **TipTap wired identically to product_form.html.** `wireTiptap({hiddenId:'page-body', targetId:'body-editor', sourceId:'body-source', toolbarId:'body-toolbar', allowHeadings:true, ariaLabel:'Page body editor', exposeAs:'morphPageBodyEditor'})`. Same ESM imports from esm.sh (pinned 3.23.4). No new CSS class — reuse `.rte-content`/`.rte-btn`/`.rte-divider` from admin_dashboard base or inline.
  - *Acceptance:* `python -m py_compile` passes; template tag balance passes; bold/italic/link toolbar buttons activate on selection.
- [ ] **Delete with confirmation.** POST to a delete view; redirect back to list with a success flash.
  - *Acceptance:* Deleting a published page returns 404 on its public URL.
- [ ] **Duplicate.** POST copies title + body + layout (state reset to `draft`, slug appended `-copy`).
  - *Acceptance:* Duplicate of slug `faq` creates slug `faq-copy` in draft state.

**Files touched (Phase 1) — all inside `plugins/installed/cms/`:**
- `dashboard.py` — add `page_new`, `page_edit`, `page_duplicate`, `page_delete` views
- `urls.py` — add dashboard routes (prefix `dashboard/cms/pages/`)... wait: the CMS plugin registers its own URL prefix via `self.register_urls('plugins.installed.cms.urls', prefix='', namespace='cms')` in [`app.py:25`](../plugins/installed/cms/app.py). Dashboard routes are contributed separately via `contribute_dashboard_pages` + `DashboardPage` objects that the admin_dashboard resolves. Add dashboard routes under a `dashboard/` sub-prefix in `urls.py`.
- `templates/cms/dashboard/pages.html` — replace read-only table with action columns + confirm-delete modal
- `templates/cms/dashboard/page_form.html` — new template with TipTap wiring

### Phase 2 — Hardcoded-page registry

- [ ] **Registry module.** `plugins/installed/cms/registry.py` with `register_hardcoded_page` / `get_hardcoded_pages`.
  - *Acceptance:* `python -m py_compile plugins/installed/cms/registry.py` passes.
- [ ] **pages_list merges registry rows.** Hardcoded rows rendered with "Managed in code — edit disabled" label, a live-page link, and no edit/duplicate/delete actions.
  - *Acceptance:* Register a test entry from any plugin's `ready()`, reload the dashboard — the locked row appears.
- [ ] **Storefront plugin registers its complex pages.** In `plugins/installed/storefront/apps.py:ready()` call `register_hardcoded_page` for: Contact (`/contact/`), Cart (`/cart/`), Checkout (`/checkout/`), Account/* (`/account/`), Newsletter thanks, Do not sell (`/do-not-sell/`), Journal index (`/journal/`), Journal detail (one representative row).
  - *Acceptance:* Disable storefront plugin → all its locked rows vanish from the CMS Pages list.

**Files touched (Phase 2):**
- `plugins/installed/cms/registry.py` — new file
- `plugins/installed/cms/dashboard.py` — merge registry rows in `pages_list`
- `plugins/installed/cms/templates/cms/dashboard/pages.html` — render locked rows
- `plugins/installed/storefront/apps.py` — register complex pages in `ready()`

### Phase 3 — Migrate About / Shipping / Returns; fix footer

- [ ] **Data migration seeds three CMS Page rows.** Slugs `about`, `shipping`, `returns`. Body seeded from the current theme template content (plain HTML extracted from the template files). State: `published`. This is a reversible Django data migration in `plugins/installed/cms/migrations/`.
  - *Acceptance:* After `migrate`, `Page.objects.filter(slug__in=['about','shipping','returns']).count() == 3`.
- [ ] **Remove hardcoded views + routes.** Delete `about`, `shipping`, `returns` functions from [`plugins/installed/storefront/views/content.py`](../plugins/installed/storefront/views/content.py). Remove `path('about/', ...)`, `path('shipping/', ...)`, `path('returns/', ...)` from [`plugins/installed/storefront/urls.py`](../plugins/installed/storefront/urls.py).
  - **URL preservation strategy (pick: 301 redirects, not path aliases).** Add a `RedirectView` for each old path → `/p/<slug>/` in storefront `urls.py` (e.g. `path('about/', RedirectView.as_view(url='/p/about/', permanent=True))`). This is three lines, needs no middleware, survives SEO crawl recache, and requires no theme edit. Update the dot_books footer links simultaneously.
  - *Acceptance:* `curl -I https://dotbooks.store/about/` returns `301 → /p/about/`; `/p/about/` returns 200.
- [ ] **Footer updated.** [`themes/library/dot_books/templates/storefront/base.html`](../themes/library/dot_books/templates/storefront/base.html) lines 680–694 — replace `/about/`, `/shipping/`, `/returns/`, `/contact/` with `/p/about/`, `/p/shipping/`, `/p/returns/` (contact stays `/contact/` — it's a functional form, registered as hardcoded).
  - *Acceptance:* Footer links resolve without redirect hops for CMS pages; `/contact/` still works.
- [ ] **Remove orphaned theme templates.** Delete `themes/library/dot_books/templates/storefront/about.html`, `shipping.html`, `returns.html` only after the data migration and redirect are confirmed live.
  - *Acceptance:* `find themes/ -name "about.html" -o -name "shipping.html" -o -name "returns.html"` returns empty (or only account_returns.html which is unrelated).

**Files touched (Phase 3):**
- `plugins/installed/cms/migrations/<N>_seed_about_shipping_returns.py` — new data migration
- `plugins/installed/storefront/views/content.py` — remove `about`, `shipping`, `returns` functions
- `plugins/installed/storefront/urls.py` — swap views for `RedirectView`, keep the three paths
- `themes/library/dot_books/templates/storefront/base.html` — update footer hrefs
- `themes/library/dot_books/templates/storefront/about.html`, `shipping.html`, `returns.html` — delete

### Phase 4 — House-rule documentation

- [ ] Add rule to `CLAUDE.md` and `docs/PLUGIN_DEVELOPMENT.md`:
  > Every storefront content page is a CMS Page row and appears in the Pages list. Functional pages (those with POST handling or non-trivial view logic) register as hardcoded (edit-disabled) via `cms.registry.register_hardcoded_page()` in their plugin's `ready()`. No hardcoded content pages in the storefront plugin or the theme.
  - *Acceptance:* `grep "cms.registry.register_hardcoded_page" CLAUDE.md` matches.

## 5. Architectural Constraints

- Everything lives in `plugins/installed/cms/` except each plugin's own `register_hardcoded_page()` call, which lives in that plugin's `apps.py:ready()`. Follows the Morpheus plugin contract — no edits to core, no cross-plugin model imports (see [CLAUDE.md Plugin contract](../CLAUDE.md)).
- Phase 3 is a live storefront migration — deploy-gated. Redirects must land before old templates are deleted.
- The CMS plugin already mounts URLs at root prefix via `self.register_urls(..., prefix='', namespace='cms')`. Dashboard sub-routes go into the same `urls.py` under a `dashboard/` prefix; they are staff-only (`@staff_member_required`).
- No new JS dependencies. TipTap is already paid for by the product form's CSP allowlist (`esm.sh` whitelisted in [`core/security_headers.py`](../core/security_headers.py)).

## 6. Non-Functional Requirements

- **Performance:** Pages list query is already `[:200]` — add `select_related('author')` to avoid N+1 on the author column if it's displayed.
- **Accessibility:** Form labels must have explicit `for` attributes; TipTap editor div needs `role="textbox" aria-multiline="true"` (already set via `ariaLabel` in `editorProps`).

## 7. Security & Privacy

- `Page.body` is sanitised by `bleach.clean()` on every save ([`cms/models.py:69–79`](../plugins/installed/cms/models.py)) — the same allowlist that covers staff-authored HTML. TipTap emits HTML; bleach strips on write. No change to this contract.
- All dashboard views use `@staff_member_required`. The delete view must be POST-only to prevent CSRF-trivial deletion via GET.
- Slug uniqueness is enforced at the DB level (`SlugField(unique=True)`) — duplicate creation must catch `IntegrityError` and return a form error.

## 8. Observability

- No special instrumentation needed for this feature. Existing Django request logs cover dashboard edits.

## 9. Out of Scope

- **PageSection / section composer.** The `PageSection` model and `{% render_page_sections %}` tag exist but are not surfaced in this editor. Body-only TipTap editing is sufficient.
- **Media/image upload in TipTap.** The product form does not support inline image upload either; that's a separate media-library integration.
- **Versioning / revision history.** No undo beyond the TipTap in-session undo stack.
- **Contact page migration.** Contact has a POST → CRM form ([`content.py:107–149`](../plugins/installed/storefront/views/content.py)) — it stays hardcoded and registered as a locked row.
- **Journal posts.** Journal index/detail are registered as hardcoded; the journal CMS migration is a separate workstream.
- **`/p/<slug>/` resolver changes.** The existing public URL resolver ([`cms/urls.py:9`](../plugins/installed/cms/urls.py)) is untouched.
- **Bulk operations.** No bulk publish/delete/duplicate.
- **Storefront plugin disable test for Phases 1–2.** Hardcoded pages registered in storefront's `ready()` disappear when storefront is disabled — but storefront is `PROTECTED_PLUGINS` (cannot be disabled). The registry call still belongs there for correctness and to model the pattern for non-protected plugins.
- **`/do-not-sell/`, `/coming-soon/`, journal views migration.** Out of scope for this spec; registered as hardcoded only.

## 10. Open Questions

None — design is locked.

## 11. Status & next-session pickup (2026-06-02)

- **Phase 1 — DONE, deployed, user-confirmed working.** Editor (TipTap body +
  New/Edit/Duplicate/Delete) live at `/dashboard/cms/pages/` (list) and
  `/dashboard/cms/pages/new/`. Routes in `cms/urls_dashboard.py` (registered in
  `cms/app.py:ready()` under `dashboard/cms/`); views in `cms/dashboard.py`;
  9 tests in `cms/tests/test_page_dashboard.py`. Shared `.rte-*` editor CSS moved
  to `admin_dashboard/base.html`; TipTap pinned 3.23.4 via esm.sh (StarterKit v3
  bundles Link — pass `link:false`).
- **Phase 5 added (user request): GraphQL + MCP write access for CMS entities.**
  Build `cms/graphql/schema.py` (Strawberry; `register_graphql_extension` in
  `ready()`) — Query `cmsPages/cmsPage`, Mutations
  `createPage/updatePage/deletePage/duplicatePage/upsertBlock`. Mirror the
  affiliates pattern (`api.graphql_permissions`: `require_authenticated`,
  `has_scope`) — staff/scope-gated. Add `@tool`s to `cms/agent_tools.py`:
  `cms.update_page`, `cms.delete_page`, `cms.get_page` (scopes `cms.write`,
  `requires_approval`) — `create_page`/`upsert_block` already exist.
- **Remaining:** Phase 2 (registry — non-live, safest, the most direct payoff to
  the original "every page in the CMS list" ask), Phase 3 (migrate
  About/Shipping/Returns — DEPLOY-GATED, touches live storefront), Phase 4 (docs).
- **Landmine hit this session:** dashboard `data-ajax` forms + fetch endpoints
  must return JSON on success AND failure (see the `dashboard-ajax-json-contract`
  memory) — `product_edit` + `image_upload` were swallowing failures.
