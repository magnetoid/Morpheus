# Navigation menu builder (header + mobile) — 2026-06

> Make the storefront **desktop nav** and **mobile hamburger drawer**
> merchant-editable from the dashboard, instead of hardcoded in the
> `dot_books` theme. Builds on the **existing `cms.Menu`/`cms.MenuItem`**
> models (DRY — do not create a new plugin). Honours ADR 0009 (DB-driven).

## What already exists (cms plugin)
- `Menu(key, label, is_active)` + `MenuItem(menu, label, url, target, parent, order, icon)`.
- `services.get_menu(key)` → nested `{key,label,items:[{label,url,target,icon,children}]}`.
- `{% cms_menu key %}` tag (renders `cms/_menu.html`).
- `menus_list` dashboard view (LIST only) + 12-line `menus.html`.

## Gaps to fill
1. **`MenuItem.kind`** — `link` (default) | `mega_categories` | `mega_authors`,
   so the dynamic Genres/Authors mega-menus survive as menu items. Migration
   via `makemigrations cms`.
2. **Dashboard CRUD** — a menu editor: create/rename/toggle a menu; add / edit /
   delete / reorder its items (label, url, kind, target). Follow the existing
   Pages-CRUD pattern (`urls_dashboard.py` + `@staff_member_required` views +
   `cms/dashboard/` templates).
3. **Theme wiring** — `dot_books/base.html` renders the desktop nav + mobile
   drawer from the `header` / `mobile` menus. `mega_*` kinds render the existing
   `nav_categories` / `nav_authors` panels; plain items render as links.
   **Fallback:** if a menu is empty/missing, render the current hardcoded nav so
   nothing breaks pre-setup.
4. **Context processor** — `cms.context_processors.nav_menus` → `header_menu` +
   `mobile_menu` (cached, fail-soft), consumed by the theme like `nav_categories`.
5. **Seeder** — `manage.py seed_nav_menus` (idempotent) creates `header` + `mobile`
   menus matching today's nav, so the merchant starts from the live layout.
6. **Tests** — menu-CRUD permission boundaries (anon / no-scope / staff) + a
   `get_menu` kind round-trip.

## Success criteria
- Editing the header menu in the dashboard changes the live desktop nav.
- Editing the mobile menu changes the hamburger drawer.
- Disable cms → nav falls back to the hardcoded default (no breakage).
- `seed_nav_menus` reproduces the current nav exactly.

## Status
- ⬜ in progress (this session).
