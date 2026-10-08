# Theme Development Guide — the Theme SDK

> Full developer reference for building Morpheus themes.
> For named, repeatable procedures see [`SKILLS.md`](../SKILLS.md).
> For platform laws see [`RULES.md`](../RULES.md).
> For the **App SDK** (the other half of the contract — apps fill the
> slots a theme exposes) see [`PLUGIN_DEVELOPMENT.md`](PLUGIN_DEVELOPMENT.md).
> For the house rule this codifies see [`CLAUDE.md` § Plugin contract](../CLAUDE.md).
> For the live modular-OS refactor + known gaps see
> [`plans/modular-os-2026-06.md`](plans/modular-os-2026-06.md).

A Morpheus theme is a **drop-in template + asset bundle** that overrides the
storefront (or any plugin's) HTML without touching plugin code. Themes do
not run business logic — they style what the platform already serves.

If you've built a Shopify theme, the model will feel familiar. If you've
built a Django app, even more so.

**The WordPress mental model.** Morpheus draws a hard line, the same one
WordPress draws between a *theme* and a *plugin*:

- The **theme** owns presentation and exposes **placeholders** (slots) — the
  Morpheus analogue of WordPress `do_action()` hooks / widget areas. It must
  not hard-code any specific plugin's feature.
- An **app** (plugin) owns its own code and **fills** those slots — the
  analogue of a WordPress plugin hooking `add_action()`.
- **Disabling an app removes every surface it added.** A theme that bakes a
  plugin's feature directly into a template breaks that promise — the surface
  survives the plugin being turned off. Don't.

These two SDKs — Theme and App — are the base everything else builds on.

---

## Table of contents

1. [Quick start (60 seconds)](#1-quick-start-60-seconds)
2. [Anatomy of a theme](#2-anatomy-of-a-theme)
3. [The lifecycle](#3-the-lifecycle)
4. [Metadata reference](#4-metadata-reference)
5. [Template overrides](#5-template-overrides)
6. [Placeholders / slots — the theme's core job](#6-placeholders--slots--the-themes-core-job)
7. [Static assets](#7-static-assets)
8. [Design tokens](#8-design-tokens)
9. [Configuration schema](#9-configuration-schema)
10. [Inheriting from another theme](#10-inheriting-from-another-theme)
11. [Working with the SEO plugin](#11-working-with-the-seo-plugin)
12. [Testing a theme](#12-testing-a-theme)
13. [Distribution as a community theme](#13-distribution-as-a-community-theme)
14. [Cookbook](#14-cookbook)

---

## 1. Quick start (60 seconds)

```bash
python manage.py morph_create_theme nightstand \
    --label "Nightstand" \
    --description "Minimal evening-mode bookshop." \
    --theme-version 0.1.0
```

This generates:

```
themes/library/nightstand/
├── theme.py
├── README.md
├── templates/
│   └── storefront/
│       ├── base.html
│       ├── home.html
│       ├── product_list.html
│       ├── product_detail.html
│       ├── cart.html
│       └── checkout.html
└── static/
    └── nightstand/
        └── style.css
```

Activate it:

```bash
export MORPHEUS_ACTIVE_THEME=nightstand
python manage.py runserver
```

To start from an existing theme as a base, add `--from`:

```bash
python manage.py morph_create_theme nightstand --from dot_books
```

That copies `templates/` and `static/` from `dot_books`. Edit
`theme.py` to update `name` and `class` to your new name.

---

## 2. Anatomy of a theme

```
themes/library/<name>/
├── theme.py                     # ★ MorpheusTheme subclass: the manifest
├── README.md                    # optional but recommended
├── templates/                   # template overrides (mirrors plugin paths)
│   ├── storefront/
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── product_list.html
│   │   ├── product_detail.html
│   │   ├── cart.html
│   │   └── checkout.html
│   ├── admin_dashboard/         # optional: override merchant dashboard
│   └── any_plugin_label/        # optional: override any plugin's templates
└── static/
    └── <name>/                  # ALL static files namespaced under <name>/
        ├── style.css
        ├── preview.png          # 1280×720 thumbnail
        └── assets/
```

The **only required file** is `theme.py`. Everything else is opt-in.

---

## 3. The lifecycle

```
                ┌──────────────────────────────────────────────┐
                │       themes/apps.py: ThemesConfig.ready()   │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │ theme_registry.discover(MORPHEUS_THEMES_DIR) │
                │   imports each themes.library.<name>.theme   │
                │   instantiates the MorpheusTheme subclass    │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │ theme_registry.set_active(MORPHEUS_ACTIVE_  │
                │   THEME) — chooses which theme is live       │
                └─────────────────────┬────────────────────────┘
                                      ▼
                ┌──────────────────────────────────────────────┐
                │ ThemeLoader (Django) resolves templates from │
                │ the active theme's templates/ FIRST. Falls   │
                │ back to plugin templates if no override.     │
                └──────────────────────────────────────────────┘
```

If a theme's `theme.py` raises during import or instantiation, **only that
theme** is dropped from the registry — siblings keep loading.

---

## 4. Metadata reference

| Field | Type | Required | Purpose |
|---|---|---|---|
| `name` | `str` | ✅ | Snake_case identifier. **Must equal the directory name.** |
| `label` | `str` | ✅ | Human-readable name shown in the dashboard's theme picker. |
| `version` | `str` | ✅ | PEP 440-style (e.g. `0.1.0`, `1.2.3a4`). |
| `description` | `str` | recommended | One-line description. |
| `author` | `str` | optional | Defaults to `"Morph Team"`. |
| `url` | `str` | optional | Theme homepage / docs. |
| `preview_image` | `str` | optional | Filename inside `static/<name>/`. Recommended: `preview.png` at 1280×720. |
| `supports_plugins` | `list[str]` | optional | Plugin names this theme provides templates for (informational). |
| `requires_plugins` | `list[str]` | optional | Plugins that MUST be active for this theme to load. The registry will refuse to set the theme active if any are missing. |

The base class **validates** all metadata at class-definition time — typos
fail at import, not at runtime.

---

## 5. Template overrides

Themes override **named templates** of the running plugins. The
[ThemeLoader](../themes/loaders.py) resolves templates from the active
theme's `templates/` directory **first**, falling back to the plugin's own
template only if nothing matches.

### Storefront templates

| Path | Used by |
|---|---|
| `storefront/base.html` | Layout / shell — every other page extends this |
| `storefront/home.html` | `/` (home page) |
| `storefront/product_list.html` | `/products/` (catalog list) |
| `storefront/product_detail.html` | `/products/<slug>/` |
| `storefront/cart.html` | `/cart/` |
| `storefront/checkout.html` | `/checkout/` |

### Other plugins

You can override **any** plugin template by mirroring its path. Examples:

| Path | Plugin |
|---|---|
| `admin_dashboard/home.html` | merchant dashboard home |
| `affiliates/redirect.html` | (if/when it exists) |

Look for the plugin's `templates/<plugin>/` directory to see what's available.

### Block patterns

The dot books `base.html` exposes blocks you'll commonly want:

```django
{% block seo %}{% endblock %}        {# the whole SEO head — see §11 #}
{% block extra_head %}{% endblock %} {# extra <head> content (preloads, page CSS) #}
{% block content %}{% endblock %}    {# main column #}
```

The convention is: **everything reusable lives in the base; pages use
`{% block content %}` plus optional helper blocks.**

---

## 6. Placeholders / slots — the theme's core job

This is the heart of the Theme SDK. Template overrides (§5) decide *how the
page looks*; **slots decide where apps are allowed to draw.** Exposing slots
is the single most important thing a theme does, because it's what lets a
merchant install an app and have it appear on the storefront **without anyone
editing a theme file.**

### What a slot is

A slot is one template tag:

```django
{% load morph %}

<h1>{{ product.name }}</h1>
{# Every enabled app that contributed a StorefrontBlock(slot="pdp_below_price")
   renders here, in priority order. Zero apps → renders nothing. #}
{% storefront_blocks "pdp_below_price" %}
```

That's the entire contract. The **theme owns the slot name and its
position**; the **app matches the name** from
`contribute_storefront_blocks()` (see the App SDK,
[PLUGIN_DEVELOPMENT.md § Modularity contract](PLUGIN_DEVELOPMENT.md#51-modularity-contract-sdk-base)).
It is the direct analogue of WordPress's `do_action('slot')` /
`dynamic_sidebar()` — a named place where *other* code contributes, that
renders empty when nobody does.

The tag is implemented in [`core/templatetags/morph.py`](../core/templatetags/morph.py)
(`storefront_blocks`) and reads from `app_registry.storefront_blocks_for(slot)`.
A block that raises is logged and skipped — **one bad block never breaks the
page.**

### What the block receives

The block template is rendered with the **full surrounding page context**
flattened in, plus `block` (the `StorefrontBlock` instance) and `request`.
So a block in `pdp_below_price` sees `product`; a block in `cart_summary_extra`
sees `cart`; a block in `home_above_grid` sees the home context. Apps read
from that context — they must not query models inside the block template.

### Canonical slot catalog

These are the slots the reference theme (`dot_books`) exposes **today**.
Slot names are case-sensitive and are the contract — never rename one a
plugin might target. The "Renders" column is where the tag physically sits;
the "Context" column is the most useful variable a block can rely on.

| Slot | Page | Renders | Block context |
|---|---|---|---|
| `global_head` | **Every page** | Last thing in `<head>`, after `{% storefront_head %}` and the theme's own CSS | layout context |
| `global_below_body` | **Every page** | End of `<body>`, before the cart drawer | layout context |
| `nav_primary_extra` | **Every page** | Inside the primary nav, after the theme's links (desktop + mobile) | layout context |
| `footer_extra` | **Every page** | In the footer's "Shop" column | layout context |
| `footer_legal` | **Every page** | The footer's legal line, next to the copyright | layout context |
| `home_below_grid` | Home (`/`) | Below the product grid | home page context |
| `home_after_rails` | Home (`/`) | After the merchandising rails | home page context |
| `pdp_below_gallery` | Product detail | Under the image gallery | `product` |
| `pdp_below_price` | Product detail | Between the price and the add-to-cart form | `product` |
| `pdp_below_form` | Product detail | Directly below the add-to-cart form | `product` |
| `pdp_above_long_description` | Product detail | Above the long description / detail tabs | `product` |
| `pdp_below_long_description` | Product detail | Below the long description | `product` |
| `cart_summary_extra` | Cart (`/cart/`) | In the order-summary panel, above the checkout button | `cart` |
| `checkout_extra` | Checkout | In the checkout column | checkout context |
| `order_receipt_extra` | Order confirmation | Below the receipt | `order` |
| `account_nav` | Account pages | In the account sidebar nav | `user` |
| `account_summary_extra` | Account home | In the account summary panel | account context |

`home_above_grid` is deliberately NOT rendered by this theme (its home page
leads with an editorial hero instead of a grid) — see the reason recorded in
`core/tests/test_slot_parity.py`, which fails the build if a theme drops a slot
some app contributes to without recording why.

> Source of truth: `grep -rn '{% storefront_blocks' themes/library/dot_books/`.
> If you add or move a slot in a theme, update this table in the same commit
> (see [`CLAUDE.md` § Living document](../CLAUDE.md)).

`priority` on a `StorefrontBlock` is the sort key within a slot — lower runs
first (`10` ≈ "near the top", `50` = default, `90` ≈ "render last, e.g. a
tracking pixel"). Two blocks with the same priority render in an unspecified
order; an app must not depend on a sibling's position.

### Custom slots

The catalog is **not a fixed contract** the platform enforces — slot names
are loose strings, and a theme may expose extra slots for its own patterns (a
magazine theme might add `magazine_pullquote`). An app targeting a
non-standard slot simply renders nothing when a theme that lacks it is active.
If you add custom slots, document them in your theme's `README.md` so plugin
authors can find them, and put a `{# slot: name #}` comment immediately above
each tag.

### The one rule: themes expose, apps fill

A theme renders **presentation only**. It exposes slots and styles whatever
lands in them. It must **never hard-code a specific plugin's feature** — no
"if loyalty is installed, show the points balance," no reviews markup baked
into `product_detail.html`, no affiliate banner stitched into `base.html`.
Those belong in the plugin, contributed into a slot. The litmus test is the
same one the App SDK uses: **disable the plugin and its surface must vanish.**
A feature welded into a theme template survives the toggle — that's the
anti-pattern.

> **Planned slots (do not rely on yet).** The storefront customer-account
> shell (`/account/`) has **no slot today**, so apps can't contribute account
> tiles, links, or sub-pages the clean way — which is exactly why the loyalty
> points tile is currently hard-coded into the theme (a known debt). The
> [modular-OS plan](plans/modular-os-2026-06.md) adds an `account_nav` /
> `account_page` slot pair plus an `ACCOUNT_SUMMARY_FIELDS` hook to fix this.
> Until those ship, treat account surfaces as **planned**, not available.
> Earlier drafts of [`THEME_EXTENSIONS.md`](THEME_EXTENSIONS.md) sketched a
> much larger aspirational catalog (`every_page_above_header`,
> `pdp_below_title`, `account_sidebar_extra`, …) — those are **proposals, not
> implemented slots.** The table above is the real, current set.

---

## 7. Static assets

Static files MUST be namespaced under `static/<name>/` so they don't
collide with plugin assets.

```
themes/library/dot_books/static/dot_books/
├── style.css
├── preview.png
└── images/cover-fallback.svg
```

Reference them with `{% static "dot_books/style.css" %}`.

The Morpheus `STATICFILES_DIRS` includes the active theme's static
directory automatically (see [`morph/settings.py`](../morph/settings.py)).

---

## 8. Design tokens

A theme exposes a flat tree of **design tokens** via
`get_design_tokens()`. The dashboard renders a live editor for each
declared category, and (in a future release) exports them as CSS variables.

```python
def get_design_tokens(self) -> dict:
    return {
        "colors": {
            "paper":   "#f6f1e7",
            "ink":     "#0e0e0e",
            "accent":  "#e63946",
        },
        "fonts":   {"display": "Fraunces", "body": "Inter"},
        "radii":   {"sm": "4px", "md": "8px", "pill": "9999px"},
        "spacing": {"xs": "4px", "sm": "8px", "md": "16px", "lg": "24px"},
        "shadows": {"card": "0 8px 24px -12px rgba(14,14,14,0.25)"},
        "motion":  {"fast": "150ms", "slow": "400ms"},
    }
```

**Convention:** keep your CSS variables 1:1 with token names so the future
auto-export works. Example:

```css
:root {
  --colors-paper:   #f6f1e7;
  --colors-ink:     #0e0e0e;
  --colors-accent:  #e63946;
  --fonts-display:  'Fraunces', serif;
}
```

Or follow the dot books convention — flat names without the category
prefix (e.g. `--paper`, `--ink`, `--accent`). Both are fine; pick one and
be consistent.

---

## 9. Configuration schema

For *behavioral* settings (toggles, copy strings, feature flags),
implement `get_config_schema()`:

```python
def get_config_schema(self) -> dict:
    return {
        "type": "object",
        "properties": {
            "show_announcement_bar": {"type": "boolean", "default": True},
            "announcement_text": {"type": "string", "default": "Free shipping over $40"},
            "newsletter_pitch": {
                "type": "string",
                "default": "Once a month. No spam. Just books.",
            },
        },
    }
```

Read values in your templates by passing them through context, or in
Python:

```python
self.get_config_value("show_announcement_bar", default=True)
```

Configuration is persisted in the `themes.ThemeConfig` table; the
dashboard renders this schema as a form.

---

## 10. Inheriting from another theme

Two paths.

### Path A — copy at scaffold time (one-shot)

```bash
python manage.py morph_create_theme my_remix --from dot_books
```

This copies `templates/` + `static/` from `dot_books`. From here you own
the copy outright.

### Path B — explicit `{% extends %}` chain

You can have a child theme extend a parent theme's `base.html`:

```django
{# themes/library/my_remix/templates/storefront/base.html #}
{% extends "storefront/base.html" %}   {# resolves to the *active* theme's base #}
```

This is brittle (depends on which theme is active when the child renders)
and rarely worth it. Path A is the recommended approach.

---

## 11. The `<head>` contract (SEO)

**A theme does not do SEO. It makes room for it.** One core tag renders the
entire head — `<title>`, description, canonical, robots, Open Graph, Twitter,
hreflang, pagination links, verification metas and the JSON-LD graph:

```django
{% load morph %}
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {% block seo %}{% storefront_head %}{% endblock %}
  …your css / fonts / scripts…
  {% storefront_blocks "global_head" %}
</head>
```

That is the whole integration. The SEO app resolves *which page this is* on its
own (product, category, journal post, cart, search…) from the URL and the
template context, so a theme never needs a per-page variant of this call.

**Fallback copy.** Pass your theme's own wording for pages that have no object
to describe — normally just the home page:

```django
{% block seo %}{% storefront_head title="Acme — modern goods" description="…" %}{% endblock %}
```

A merchant who fills in Settings → SEO (or edits a product's SEO panel)
overrides it. Everything else — every product, category, collection, vendor,
author, article — needs no arguments at all.

**Declare the contract in your theme class:**

```python
class AcmeTheme(MorpheusTheme):
    head_contract = 1   # I call {% storefront_head %} and emit no SEO markup myself
```

That opts the theme into `themes/test_head_contract.py`, which renders every
page kind and asserts exactly one `<title>`, one canonical, one robots meta and
one JSON-LD block — plus that the page still renders when the SEO app is
disabled. SEO regressions in a theme are invisible in a browser; this is how
they get caught.

### Rules

| Do | Don't |
|---|---|
| Call `{% storefront_head %}` once, inside `<head>` | Emit your own `<title>`, canonical, robots or `og:*` — they duplicate |
| Put theme wording in the tag's `title=` / `description=` arguments | Hardcode the shop's name in templates or views (it comes from settings) |
| Render `{% storefront_blocks "global_head" %}` too | Reverse another app's URL (`{% url 'seo:…' %}`) — it 500s the page when that app is off |
| Let page templates override `{% block seo %}` only to pass different fallbacks | Override the block to change robots — page kind decides that |
| Give a page your own name with `{% block seo %}{% with seo_title=… %}{{ block.super }}{% endwith %}{% endblock %}` | Write `{% block title %}` — no base renders it, so it never reaches the page |
| Use `{% page_href page_obj.next_page_number %}` for pagination links | Build `?page={{ n }}` by hand — page 1 then costs a 301 hop |
| Set `<html lang="{% get_current_language as L %}{{ L }}">` | Hardcode `lang="en"` on a theme any store may run in another language |
| Let the head document emit hreflang and JSON-LD | Paste `<script type="application/ld+json">` or `hreflang` links — apps contribute through `SEO_JSONLD_GRAPH` / `STOREFRONT_HEAD` |

**Error pages.** A theme's `404.html` overrides no head block and passes no
title: the seo app recognises Django's error render and emits the title
("Page not found", translated), the description and `noindex, follow` — no
canonical, no hreflang, no Open Graph, no structured data, because each of
those would name a page that does not exist.

**Words for the marketplace.** Set `vendor_noun` / `vendor_noun_plural` on your
theme class ("Publisher"/"Publishers" on a bookshop, "Host"/"Hosts" on a travel
store); the shell's vendor pages read them for titles and breadcrumbs.

**Sign-in pages** render inside your theme through `templates/account/base.html`
(children fill `heading`, `subheading`, `auth_form`) and
`templates/allauth/layouts/base.html`. The shared sheet maps onto either token
set (`--ink`/`--paper`/`--rule` or the HSL `--foreground`/`--background`/
`--border`); override `account/*.html` only to change the markup.

`themes/test_head_contract.py` enforces all of it for every theme that sets
`head_contract = 1`: the 404 head under each theme, no raw JSON-LD / hreflang /
`lang="en"` in its templates, and no `{% block %}` that no base renders.

### Legacy themes

The per-tag helpers (`{% seo_meta %}`, `{% seo_product_jsonld %}`,
`{% seo_breadcrumb_jsonld %}`, …) still work for themes that have not migrated,
and go silent automatically on a page that called `{% storefront_head %}`, so a
half-migrated theme never double-emits. They are removed in a later release —
see [`MIGRATING.md`](MIGRATING.md).

The dot books theme is the canonical example.

---

## 12. Testing a theme

Drop a `tests.py` next to the theme that asserts each template parses:

```python
# themes/library/<name>/tests.py
from django.test import TestCase
from django.template import Engine

class ThemeSmokeTests(TestCase):
    def test_all_templates_compile(self):
        for tpl in ['storefront/base.html', 'storefront/home.html',
                    'storefront/product_list.html', 'storefront/product_detail.html',
                    'storefront/cart.html', 'storefront/checkout.html']:
            Engine.get_default().get_template(tpl)
```

For visual regression, use Playwright/Cypress to walk
`/, /products/, /products/<slug>/, /cart/, /checkout/` and snapshot.

---

## 13. Distribution as a community theme

Two paths.

### Path A — drop-in under `themes/library/`

The merchant copies your theme into `themes/library/<name>/` and sets
`MORPHEUS_ACTIVE_THEME=<name>`. That's it.

### Path B — pip-installable

Publish your theme as a Python package whose `theme.py` is at
`<your_pkg>/<name>/theme.py`. Merchants then:

```bash
pip install morph-theme-<name>
```

Then symlink (or otherwise place) the theme directory into
`themes/library/`. A future release will support direct discovery from
installed packages — for now, the in-tree convention is canonical.

**Naming convention:** prefix package names with `morph-theme-`.

---

## 14. Cookbook

### Override a single page

Create `themes/library/<name>/templates/storefront/home.html`. Other pages
will continue to come from the storefront plugin (or a parent theme if you
copied via `--from`).

### Add a custom landing page

The storefront plugin owns `/`. To add `/lookbook/` (a custom landing
page), expose a URL via a tiny custom plugin (see
[PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md)) that renders your theme
template:

```python
# plugins/installed/lookbook/views.py
from django.shortcuts import render
def lookbook(request):
    return render(request, 'lookbook/index.html')
```

Then ship the template at
`themes/library/<name>/templates/lookbook/index.html`.

### Switch fonts site-wide

Edit your theme's `static/<name>/style.css`:

```css
:root { --body-font: 'Untitled Sans', system-ui, sans-serif; }
body  { font-family: var(--body-font); }
```

If you want the change reflected in `get_design_tokens()` (so the
dashboard editor shows the right defaults), update there too.

### Add a brand color override per-channel

Use the theme's `get_config_schema()` to expose `accent_color` as a string
property. In the dashboard, the merchant picks a color; your CSS reads it
via a context processor or inline `<style>` block:

```django
{% with cfg=theme.get_config %}
<style>:root { --accent: {{ cfg.accent_color|default:"#e63946" }}; }</style>
{% endwith %}
```

### Use the dot books theme as a starting point

```bash
python manage.py morph_create_theme my_brand --from dot_books
```

Then edit `theme.py` to set `name = "my_brand"`, change the
`get_design_tokens()` palette, and tweak `templates/storefront/base.html`
to taste.

---

## See also

- [`PLUGIN_DEVELOPMENT.md`](PLUGIN_DEVELOPMENT.md) — **the App SDK**, the other
  half of this contract: how an app *fills* the slots a theme exposes, and the
  enable/disable lifecycle.
- [`THEME_EXTENSIONS.md`](THEME_EXTENSIONS.md) — narrative background on the
  slot pattern (note: its catalog includes proposed slots; §6 above is the
  implemented set).
- [`CLAUDE.md` § Plugin contract](../CLAUDE.md) — the house rule this SDK codifies.
- [`plans/modular-os-2026-06.md`](plans/modular-os-2026-06.md) — the refactor
  that finishes "disable an app → its surfaces vanish" (account slots, etc.).
- [`SKILLS.md`](../SKILLS.md) — named, repeatable procedures.
- [`RULES.md`](../RULES.md) — platform laws.
- [`core/templatetags/morph.py`](../core/templatetags/morph.py) — the
  `{% storefront_blocks %}` tag.
- [`themes/base.py`](../themes/base.py) — source of truth for the base class.
- [`themes/registry.py`](../themes/registry.py) — discovery + activation engine.
- [`themes/loaders.py`](../themes/loaders.py) — Django template loader.
