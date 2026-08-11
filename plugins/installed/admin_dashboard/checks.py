"""System checks enforcing the dashboard contribution taxonomy.

A SettingsPanel with an unregistered ``category`` renders nowhere — no card
on the settings hub, no sidebar entry, and its category URL 404s (8 plugins
shipped that way before the 2026-07 UX audit). A DashboardPage with an
unknown ``nav`` value is just as silent. Both are contract violations a
human only notices by absence, so they fail ``manage.py check`` (CI runs it
blocking) instead of waiting to be noticed.
"""

from __future__ import annotations

from django.core import checks

_VALID_NAV = ('main', 'settings', 'hidden')


@checks.register('morpheus')
def check_contribution_taxonomy(app_configs=None, **kwargs):
    from plugins.installed.admin_dashboard.settings_categories import get_category
    from plugins.registry import app_registry

    errors = []
    for entry in app_registry.all_settings_panels():
        panel = entry['panel']
        category = getattr(panel, 'category', '') or 'apps'
        if get_category(category) is None:
            errors.append(
                checks.Error(
                    f"SettingsPanel from plugin '{entry['plugin']}' uses unknown settings "
                    f"category '{category}' — the panel would be invisible and "
                    f'/dashboard/settings/{category}/ a 404.',
                    hint='Pick a slug from admin_dashboard/settings_categories.py '
                    "(or leave category blank for the 'apps' bucket).",
                    id='morpheus.E001',
                )
            )
    for page in app_registry.dashboard_pages():
        if page.nav not in _VALID_NAV:
            errors.append(
                checks.Error(
                    f"DashboardPage '{page.label}' from plugin '{page.plugin}' has "
                    f"nav='{page.nav}' — not one of {_VALID_NAV}.",
                    hint="nav controls which sidebar lists the entry: 'main', "
                    "'settings', or 'hidden'.",
                    id='morpheus.E002',
                )
            )
    return errors
