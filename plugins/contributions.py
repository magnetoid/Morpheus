"""
Plugin contribution surfaces.

When a plugin is *enabled*, it can contribute to:

* **Storefront blocks** — small templates rendered by the active theme
  through the `{% storefront_blocks "slot_name" %}` template tag.
* **Dashboard pages** — entries auto-injected into the merchant
  dashboard's sidebar (icon + label + URL).
* **Settings panel** — declarative JSON Schema rendered as a form on
  `/dashboard/apps/<plugin>/settings/`.

This file provides the small dataclasses; the registry of what each
plugin actually contributes lives on `MorpheusPlugin` (see
`contribute_storefront_blocks`, `contribute_dashboard_pages`,
`contribute_settings_panel`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StorefrontBlock:
    """A small template fragment rendered into a named slot in the theme.

    Slots are loose strings — themes decide which slots they expose.
    Conventional slot names that the dot books theme honors:

      - `home_above_grid`     · `home_below_grid`
      - `pdp_above_price`     · `pdp_below_price`     · `pdp_below_form`
      - `cart_summary_extra`  · `checkout_extra`

    `priority` is a sort key (lower runs first) — same convention as hooks.
    `context_keys` lists names from the parent template's context that the
    block needs; used for documentation only at the moment.
    """
    slot: str
    template: str           # e.g. 'advanced_ecommerce/blocks/recently_viewed.html'
    priority: int = 50
    context_keys: list[str] = field(default_factory=list)
    plugin: str = ''        # filled in by the registry


@dataclass(slots=True)
class DashboardPage:
    """A merchant-dashboard sidebar entry.

    `view` is a callable that takes a request and returns an HttpResponse,
    OR a dotted path string ("plugins.installed.<plugin>.views.my_view")
    so the registry can resolve it lazily without import-time side effects.

    `nav` controls which sidebar lists the entry:
      * 'main'     — daily-use page in the main sidebar (default)
      * 'settings' — admin/setup page that lives in the settings panel
                     alongside the schema-driven SettingsPanel forms

    Routes are unchanged regardless of `nav`; only the sidebar listing
    moves. This mirrors Shopify — Orders/Products/Customers on the main
    rail; Webhooks/Roles/CSV import in the settings panel.
    """
    label: str
    slug: str               # the URL slug, mounted under /dashboard/apps/<plugin>/<slug>/
    view: Any               # callable | str
    icon: str = 'circle'    # any lucide icon name
    section: str = 'plugins'  # 'plugins' | 'sales' | 'apps' | 'settings'
    order: int = 100
    plugin: str = ''
    nav: str = 'main'       # 'main' | 'settings'


@dataclass(slots=True)
class SettingsPanel:
    """Declarative settings panel rendered from a JSON Schema.

    `category` controls which Shopify-style category the panel shows
    under in the unified `/dashboard/settings/<category>/` view. If left
    blank the panel falls into the catch-all 'apps' bucket so it still
    has a home — older plugins that haven't been categorized yet keep
    working without a code change.

    Standard categories (see SETTINGS_CATEGORIES in
    `plugins.installed.admin_dashboard.settings_categories`):
      * 'general'        — Store name, currency, locales
      * 'payments'       — Stripe, PayPal, manual, …
      * 'shipping'       — Carriers, zones, rates
      * 'taxes'          — Regions, rates
      * 'channels'       — Storefront SEO, marketplaces, social
      * 'ai'             — Provider, model, agent settings
      * 'marketing'      — Email, coupons, CRM defaults
      * 'notifications'  — Email/SMS templates, webhooks
      * 'developer'      — API keys, agent tokens, observability
      * 'apps'           — Catch-all for plugin-specific config
    """
    label: str
    schema: dict            # JSON Schema; usually `plugin.get_config_schema()`
    description: str = ''
    plugin: str = ''
    category: str = 'apps'  # one of the standard category slugs above
