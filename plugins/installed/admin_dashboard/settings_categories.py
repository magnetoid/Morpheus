"""Settings categories — the settings sidebar (docs/plans/dashboard-hubs-2026-10.md).

Each category is one page under ``/dashboard/settings/<slug>/``. Apps file
into one with ``SettingsPanel(category=…)`` (a form) or
``DashboardPage(nav='settings', section=…)`` (a tool card linking to the
app's own settings page); the shell adds its core forms and platform tools.
A category with nothing in it is not listed — General and Notifications
always are, they carry the store's core forms.

``apps`` ("Other apps") is the home of a panel that names no category; no
in-tree app uses it, so it is listed only when an out-of-tree app does.
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
    SettingsCategory(
        'general', 'General', 'Store details, markets, languages and privacy.', 'store'
    ),
    SettingsCategory(
        'payments',
        'Payments & checkout',
        'Payment methods, checkout, fraud checks and subscription billing.',
        'credit-card',
    ),
    SettingsCategory(
        'shipping', 'Shipping & tax', 'Zones, rates, carriers, fulfilment and tax.', 'truck'
    ),
    SettingsCategory(
        'storefront',
        'Storefront',
        'Images, brand, motion and the features shoppers see.',
        'monitor-smartphone',
    ),
    SettingsCategory(
        'channels',
        'Sales channels',
        'Product feeds, ad accounts, SEO and conversion tracking.',
        'globe',
    ),
    SettingsCategory(
        'marketing',
        'Marketing',
        'Loyalty, referrals, newsletter, affiliates and recovery emails.',
        'megaphone',
    ),
    SettingsCategory(
        'ai', 'AI', 'Providers, guardrails, brand voice and Linda’s engine.', 'sparkles'
    ),
    SettingsCategory(
        'notifications', 'Notifications', 'Email sender, SMTP and email templates.', 'bell'
    ),
    SettingsCategory(
        'team',
        'Team & security',
        'Roles, two-factor sign-in, single sign-on and the audit log.',
        'shield-check',
    ),
    SettingsCategory(
        'developer', 'Developer', 'API tokens, webhooks, workflows and platform tools.', 'code'
    ),
    SettingsCategory('data', 'Data', 'Import, export, migration and backups.', 'database'),
    SettingsCategory(
        'apps', 'Other apps', 'Settings from apps that have not picked a category.', 'puzzle'
    ),
]

# Slugs used before v0.81.0, or by apps written against an older Morpheus.
# `/dashboard/settings/<old>/` redirects to the category it now belongs to.
CATEGORY_ALIASES = {
    'taxes': 'shipping',
    'access': 'team',
    'security': 'team',
    'settings': 'general',
    'checkout': 'payments',
    'content': 'storefront',
    'customers': 'marketing',
}


_BY_SLUG = {c.slug: c for c in SETTINGS_CATEGORIES}


def get_category(slug: str) -> SettingsCategory | None:
    return _BY_SLUG.get(slug)
