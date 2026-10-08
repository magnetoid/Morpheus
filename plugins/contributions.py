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
    template: str  # e.g. 'advanced_ecommerce/blocks/recently_viewed.html'
    priority: int = 50
    context_keys: list[str] = field(default_factory=list)
    plugin: str = ''  # filled in by the registry


@dataclass(slots=True)
class DashboardPage:
    """A merchant-dashboard page: a tab in one of the dashboard's sections.

    `view` is a callable that takes a request and returns an HttpResponse,
    OR a dotted path string ("plugins.installed.<plugin>.views.my_view")
    so the registry can resolve it lazily without import-time side effects.

    `nav` decides where the page is listed:
      * 'main'     — a tab in the main-sidebar `section` it names (default)
      * 'settings' — a tool card on the Settings category `section` names
      * 'hidden'   — routed but listed nowhere; reached from a card, a link
                     or the command palette. It still belongs to `section`,
                     so the sidebar and breadcrumb know where you are.

    `section` is a key from `admin_dashboard/navigation.py`: for 'main' a
    sidebar section (orders, products, customers, marketing, channels,
    content, analytics, seo, vendors, ai), for 'settings' a settings
    category (general, payments, shipping, storefront, channels, marketing,
    ai, notifications, team, developer, data). Older keys (growth, cms,
    catalog, marketplace, access, taxes, …) are aliased; an unknown key is
    reported by `manage.py check` and the page is listed only in the Apps
    catalogue.

    `group` folds pages into one tab: pages of a section that share a group
    label render as a single tab ("Affiliates") with the pages as sub-tabs.

    Routes are unchanged regardless of `nav`; only the listing moves.
    """

    label: str
    slug: str  # the URL slug, mounted under /dashboard/apps/<plugin>/<slug>/
    view: Any  # callable | str
    icon: str = 'circle'  # any lucide icon name
    section: str = 'plugins'
    order: int = 100
    plugin: str = ''
    nav: str = 'main'  # 'main' | 'settings' | 'hidden'
    # Optional canonical URL — when set, the tab links here instead of
    # /dashboard/apps/<plugin>/<slug>/. Lets a plugin that owns its own
    # URL prefix (via register_urls) point the entry at the primary URL
    # without losing the discovery surface in /dashboard/apps/.
    url: str = ''
    group: str = ''  # tab-group label; '' = the page is its own tab
    hint: str = ''  # one line for a settings tool card and the palette


@dataclass(slots=True)
class DashboardCard:
    """A small widget an app places on a dashboard section's landing page.

    Cards are how two apps share one page: the Marketing overview shows the
    coupons card next to the gift-cards card, the Products list carries the
    stockout forecast. The shell draws every card the same way; the app only
    supplies the numbers.

    `data` is a callable ``(request) -> dict | None`` (or a dotted path to
    one), called when the landing renders. Keys of the dict, all optional:

      * ``value``   — the headline ('12', '$1,250.00', '82/100')
      * ``caption`` — one line under it ('active coupons')
      * ``rows``    — up to five ``(label, value)`` pairs, or dicts with
                      ``label``, ``value`` and an optional ``url``
      * ``tone``    — '' | 'ok' | 'warn' | 'danger' (colours the headline)
      * ``empty``   — text shown instead when there is nothing to report yet
      * ``url``     — overrides the card's link for this render

    Return ``None`` to leave the card off the page. A card whose callable
    raises renders an error state and logs — it never takes the page down.

    `section` names a landing that renders cards: home, orders, products,
    customers, marketing or analytics (see admin_dashboard/navigation.py).
    `capability` gates the card the way ``@require_capability`` gates a
    page: under rbac's ``enforce`` mode a user without it does not see it.
    """

    section: str
    title: str
    data: Any  # callable(request) -> dict | None, or a dotted path
    url: str = ''  # the card's link (its full page)
    cta: str = 'Open'
    icon: str = 'circle'
    order: int = 100
    capability: str = ''
    plugin: str = ''  # filled in by the registry


@dataclass(slots=True)
class SettingsPanel:
    """Declarative settings panel rendered from a JSON Schema.

    `category` controls which settings category the panel shows under in
    `/dashboard/settings/<category>/`. If left blank the panel falls into
    the 'apps' bucket ("Other apps", listed only while something is in it)
    so an uncategorised out-of-tree app still has a home.

    Categories (see SETTINGS_CATEGORIES in
    `plugins.installed.admin_dashboard.settings_categories`):
      * 'general'        — store details, markets, languages, privacy
      * 'payments'       — gateways, checkout, fraud, billing
      * 'shipping'       — zones, rates, carriers, fulfilment, tax
      * 'storefront'     — images, brand, motion, storefront features
      * 'channels'       — feeds, ad accounts, SEO, conversion tracking
      * 'marketing'      — loyalty, referrals, newsletter, affiliates
      * 'ai'             — providers, guardrails, brand voice
      * 'notifications'  — sender, SMTP, email templates
      * 'team'           — roles, two-factor, single sign-on
      * 'developer'      — API tokens, webhooks, platform tools
      * 'data'           — import, export, backups
    Older slugs ('taxes', 'access', 'security', …) are aliased.
    """

    label: str
    schema: dict  # JSON Schema; usually `plugin.get_config_schema()`
    description: str = ''
    plugin: str = ''
    category: str = 'apps'  # one of the standard category slugs above


@dataclass(slots=True)
class EmailTemplateDef:
    """A transactional email template a plugin contributes to the CENTRAL email
    registry (Settings → Notifications → Email templates) — the WooCommerce
    `WC_Email` analog.

    The plugin OWNS its default template files
    (`plugins/installed/<name>/templates/emails/<key>.{html,txt}`); the merchant
    edits/overrides them centrally (stored on `cms.EmailTemplate`, keyed by
    `key`, with reset-to-default). Contributing a def makes the email appear in
    the one central list, grouped under the owning app; disabling the plugin
    removes it (modularity contract). Send the email via
    `core.emails.send_templated_email(key, ...)` so DB overrides apply.
    """

    key: str  # globally-unique, namespaced — e.g. 'loyalty_points_earned'
    label: str  # 'Loyalty points earned'
    default_subject: str  # 'You earned {{ points }} points'
    group: str = 'Other'  # display group in the central list — e.g. 'Loyalty'
    description: str = ''  # what triggers it (shown as a hint)
    plugin: str = ''  # set by the registry


def dashboard_trail(section_label: str, section_url: str, *items) -> list[dict]:
    """``[Dashboard › <section> › <items…>]`` for a view's ``breadcrumb_trail``.

    The one shared breadcrumb builder for plugin dashboard pages. Every
    dashboard-contributing plugin used to carry its own ``_trail()`` copy;
    the first consolidation homed it in ``admin_dashboard.breadcrumbs``,
    which made eight plugins import a sibling plugin — so it lives here in
    the SDK instead (beside ``DashboardPage``, the thing it decorates).

    ``items`` are either ready-made ``{'label': …, 'url': …}`` dicts or
    plain strings (rendered as an unlinked leaf crumb).
    """
    trail = [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': section_label, 'url': section_url},
    ]
    for item in items:
        trail.append(item if isinstance(item, dict) else {'label': str(item)})
    return trail
