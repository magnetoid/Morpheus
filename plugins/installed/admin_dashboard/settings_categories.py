"""Settings categories — the Shopify-style top-level grouping.

IA redesign phase 3 (docs/plans/dashboard-ia-redesign-2026-06.md): caching
lives as a card in the Developers hub (its /dashboard/settings/caching/
URL is dispatched before the category lookup, so it stays reachable);
product-type panels merged into General.

Each category is one page under ``/dashboard/settings/<slug>/``. A
plugin opts into a category by setting ``category=`` on the
``SettingsPanel`` it returns from ``contribute_settings_panel()``.
Plugins that don't set a category fall into ``apps`` — they still
appear, just at the bottom of the menu.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingsCategory:
    slug: str
    label: str
    description: str
    icon: str  # any lucide icon name


# Order here is the order shown in the settings sidebar.
SETTINGS_CATEGORIES: list[SettingsCategory] = [
    SettingsCategory('general', 'General', 'Store name, currency, country, basics.', 'store'),
    SettingsCategory(
        'payments', 'Payments', 'Gateways and payment methods customers can use.', 'credit-card'
    ),
    SettingsCategory('shipping', 'Shipping', 'Zones, rates, and carriers.', 'truck'),
    SettingsCategory('taxes', 'Taxes', 'Regional rates and overrides.', 'percent'),
    SettingsCategory(
        'channels',
        'Sales channels',
        'Storefront, social, SEO, tracking, marketplace listings.',
        'globe',
    ),
    SettingsCategory('ai', 'AI', 'Provider, model, and agent settings.', 'sparkles'),
    SettingsCategory(
        'marketing', 'Marketing', 'Coupons, email campaigns, CRM defaults.', 'megaphone'
    ),
    SettingsCategory(
        'notifications',
        'Notifications',
        'Transactional email templates, SMS, and outbound webhooks.',
        'bell',
    ),
    SettingsCategory(
        'developer', 'Developer', 'API keys, webhooks, agent tokens, observability.', 'code'
    ),
    SettingsCategory('apps', 'Other apps', 'Settings exposed by individual apps.', 'puzzle'),
]


_BY_SLUG = {c.slug: c for c in SETTINGS_CATEGORIES}


def get_category(slug: str) -> SettingsCategory | None:
    return _BY_SLUG.get(slug)
