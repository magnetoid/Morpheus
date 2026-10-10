"""Release notes plugin — the in-dashboard platform-info pages.

Two model-less surfaces under Dashboard → Settings:

* **Help** and **About Morpheus OS** — pages of the project website
  (``MORPHEUS_SITE_URL``, morpheus.direct) shown in its embed mode, so they are
  written once for every store (`views.help_page`, `views.about`).
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
    version = '1.1.0'
    description = (
        "Help and About Morpheus OS (the project website's pages, shown in the "
        'dashboard) and the Version & updates changelog (renders '
        'docs/RELEASE_NOTES.md next to the running version).'
    )
    has_models = False

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Help',
                slug='help',
                view='plugins.installed.release_notes.views.help_page',
                icon='help-circle',
                section='developer',
                order=93,
                nav='settings',
                hint='How the dashboard works',
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
