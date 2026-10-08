"""System checks enforcing the dashboard contribution taxonomy.

Every dashboard contribution names where it lives — a sidebar section, a
settings category, a landing that renders cards — and a name that matches
nothing renders nowhere, with no error anywhere: 8 settings panels shipped
that way before the 2026-07 UX audit, invisible on the settings hub with
their category URL a 404. So `manage.py check` (CI runs it blocking) says so.

* E001 — a SettingsPanel's category is unknown (old slugs are aliased, see
  `settings_categories.CATEGORY_ALIASES`).
* E002 — a DashboardPage's `nav` is not main/settings/hidden.
* W003 — a listed (`nav='main'`) page names no sidebar section; it is
  reachable from the Apps catalogue only.
* W004 — a `nav='settings'` page names no settings category; its tool card
  lands in "Other apps".
* W005 — a DashboardCard names a section whose landing renders no cards.

The W-level ones are warnings, not errors, on purpose: an out-of-tree app
written against an older taxonomy must not stop a deployment's boot (system
check errors abort `migrate`). The in-tree suite holds them at zero
(`test_contribution_taxonomy.TaxonomyCheckTests.test_live_registry_is_clean`).
"""

from __future__ import annotations

from django.core import checks

_VALID_NAV = ('main', 'settings', 'hidden')


@checks.register('morpheus')
def check_contribution_taxonomy(app_configs=None, **kwargs):
    from plugins.installed.admin_dashboard import navigation
    from plugins.registry import app_registry

    errors = []
    for entry in app_registry.all_settings_panels():
        panel = entry['panel']
        category = getattr(panel, 'category', '') or 'apps'
        if navigation.settings_category_key(category) is None:
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
        errors.extend(_page_problems(page, navigation))
    card_sections = navigation.card_section_keys()
    for card in app_registry.dashboard_cards():
        if navigation.main_section_key(card.section) not in card_sections:
            errors.append(
                checks.Warning(
                    f"DashboardCard '{card.title}' from plugin '{card.plugin}' names section "
                    f"'{card.section}', whose landing renders no cards — it is shown nowhere.",
                    hint=f'Use one of {card_sections}.',
                    id='morpheus.W005',
                )
            )
    return errors


def _page_problems(page, navigation) -> list:
    if page.nav not in _VALID_NAV:
        return [
            checks.Error(
                f"DashboardPage '{page.label}' from plugin '{page.plugin}' has "
                f"nav='{page.nav}' — not one of {_VALID_NAV}.",
                hint="nav decides where the page is listed: 'main' (a tab of its section), "
                "'settings' (a tool card on a settings category) or 'hidden'.",
                id='morpheus.E002',
            )
        ]
    if page.nav == 'main' and navigation.main_section_key(page.section) is None:
        return [
            checks.Warning(
                f"DashboardPage '{page.label}' from plugin '{page.plugin}' names section "
                f"'{page.section}', which is no sidebar section — it is listed only in the "
                'Apps catalogue.',
                hint='Use a key from admin_dashboard/navigation.py SECTIONS.',
                id='morpheus.W003',
            )
        ]
    if page.nav == 'settings' and navigation.settings_category_key(page.section) is None:
        return [
            checks.Warning(
                f"DashboardPage '{page.label}' from plugin '{page.plugin}' names settings "
                f"category '{page.section}', which does not exist — its card lands in "
                "'Other apps'.",
                hint='Use a slug from admin_dashboard/settings_categories.py.',
                id='morpheus.W004',
            )
        ]
    return []
