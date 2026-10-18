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
