"""Release notes plugin — the in-dashboard platform-info pages.

Three model-less surfaces under Dashboard → Settings:

* **Help**: /dashboard/help/, every app's guide (its own
  ``plugins/installed/<app>/help.md``) and what the running code says about it,
  searchable and readable by Linda. Spec:
  docs/superpowers/specs/2026-10-18-help-system-design.md.
* **About Morpheus OS**: the project website's About page in its embed mode.
* **Version & updates** — renders [`docs/RELEASE_NOTES.md`](../../../docs/RELEASE_NOTES.md),
  the single source of truth for the Morpheus OS changelog, next to the
  running `MORPHEUS_VERSION` (`views.version_updates`).

House rule (torsor ADR "Versioned release notes" + ADR 0032 + CLAUDE.md): every
production deploy bumps `MORPHEUS_VERSION` and adds a `## vX.Y.Z — YYYY-MM-DD`
entry to that document. This plugin only *displays*; it owns no data.
"""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin
from morpheus.core import MorpheusEvents

#: Appended to Linda's instructions while this app is on (AGENT_SYSTEM_PROMPT):
#: a line in core's base prompt would name tools that vanish when it is off.
HELP_LINE = (
    '\nHELP\n'
    '  • When the merchant asks how to do something in the dashboard, or what an app '
    "does, read the store's own help first: `help.apps` lists the apps or searches their "
    "help, `help.read` gives one app's guide and where its screens are.\n"
)


class ReleaseNotesPlugin(Plugin):
    name = 'release_notes'
    label = 'Release notes'
    version = '1.2.0'
    description = (
        "Help for every app (each app's own guide plus what the running code says "
        "about it), About Morpheus OS (the project website's page) and the Version & "
        'updates changelog (renders docs/RELEASE_NOTES.md next to the running version).'
    )
    has_models = False
    # Help reads the dashboard's sections, tabs and the Apps catalogue's areas.
    requires = ['admin_dashboard']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.release_notes.urls', prefix='dashboard/help/', namespace='help'
        )
        self.register_hook(MorpheusEvents.DASHBOARD_USER_MENU, self.on_user_menu)
        self.register_hook(MorpheusEvents.DASHBOARD_PAGE_HELP, self.on_page_help)
        self.register_hook(MorpheusEvents.AGENT_SYSTEM_PROMPT, self.on_system_prompt, priority=60)

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Help',
                slug='help',
                view='plugins.installed.release_notes.help_views.help_redirect',
                icon='help-circle',
                section='developer',
                order=93,
                nav='settings',
                hint='What every app does and where to find it',
                url='/dashboard/help/',
            ),
            DashboardPage(
                label='About Morpheus OS',
                slug='about',
                view='plugins.installed.release_notes.views.about',
                icon='info',
                section='developer',
                order=94,
                nav='settings',
                hint='What Morpheus OS is, and its licence',
            ),
            DashboardPage(
                label='Version & updates',
                slug='version',
                view='plugins.installed.release_notes.views.version_updates',
                icon='git-commit-horizontal',
                section='developer',
                order=85,
                nav='settings',
                hint='Running version, updates and changelog',
            ),
        ]

    def on_user_menu(self, value, **kwargs):
        """Help, About and Version in the account menu, in place of links the
        shell used to hardcode."""
        from django.conf import settings

        value.extend(
            [
                {'label': 'Help', 'url': '/dashboard/help/', 'icon': 'help-circle', 'order': 10},
                {
                    'label': 'About Morpheus OS',
                    'url': '/dashboard/apps/release_notes/about/',
                    'icon': 'info',
                    'order': 20,
                },
                {
                    'label': 'Version & updates',
                    'url': '/dashboard/apps/release_notes/version/',
                    'icon': 'git-commit-horizontal',
                    'order': 30,
                    'badge': getattr(settings, 'MORPHEUS_VERSION', ''),
                },
            ]
        )
        return value

    def on_page_help(self, value, app='', request=None, **kwargs):
        """The Help link for a page of ``app``: that app's help, else the index."""
        from plugins.registry import app_registry

        if (getattr(request, 'path', '') or '').startswith('/dashboard/help/'):
            return value  # a help page needs no link to help
        inst = app_registry.get(app) if app else None
        if inst is None:
            return {'url': '/dashboard/help/', 'label': 'Help', 'title': 'Help for every app'}
        return {
            'url': f'/dashboard/help/{inst.name}/',
            'label': 'Help',
            'title': f'Help for {inst.label or inst.name}',
        }

    def contribute_agent_tools(self) -> list:
        from plugins.installed.release_notes.help_tools import help_apps_tool, help_read_tool

        return [help_apps_tool, help_read_tool]

    def on_system_prompt(self, value, **kwargs):
        """Tell Linda the store's help exists (AGENT_SYSTEM_PROMPT)."""
        return value + HELP_LINE if isinstance(value, str) else value
