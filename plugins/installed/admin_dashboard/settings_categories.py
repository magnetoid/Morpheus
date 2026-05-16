"""Settings categories — the Shopify-style top-level grouping.

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
    icon: str   # any lucide icon name


# Order here is the order shown in the settings sidebar.
SETTINGS_CATEGORIES: list[SettingsCategory] = [
    SettingsCategory('general',       'Store',         'Name, currency, country, basics.',                    'store'),
    SettingsCategory('payments',      'Payments',      'Gateways and payment methods customers can use.',     'credit-card'),
    SettingsCategory('shipping',      'Shipping',      'Zones, rates, and carriers.',                          'truck'),
    SettingsCategory('taxes',         'Taxes',         'Regional rates and overrides.',                       'percent'),
    SettingsCategory('channels',      'Channels',      'Storefront, social, marketplace listings.',           'globe'),
    SettingsCategory('ai',            'AI',            'Provider, model, and agent settings.',                'sparkles'),
    SettingsCategory('marketing',     'Marketing',     'Coupons, email campaigns, CRM defaults.',             'megaphone'),
    SettingsCategory('notifications', 'Notifications', 'Transactional email templates, SMS, and outbound webhooks.', 'bell'),
    SettingsCategory('developer',     'Developer',     'API keys, webhooks, agent tokens, observability.',    'code'),
    SettingsCategory('apps',          'Other plugins', 'Settings exposed by individual plugins.',             'puzzle'),
]


_BY_SLUG = {c.slug: c for c in SETTINGS_CATEGORIES}


def get_category(slug: str) -> SettingsCategory | None:
    return _BY_SLUG.get(slug)
