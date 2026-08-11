"""Release notes plugin — the in-dashboard platform-info pages.

Two model-less surfaces under Dashboard → Settings:

* **About Morpheus** — what the platform is + a live catalogue of every
  installed app, read straight from the plugin registry (`views.about`).
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
        'The Settings → About Morpheus page (what the platform is + a live '
        'catalogue of every installed app) and the Version & updates changelog '
        '(renders docs/RELEASE_NOTES.md next to the running version).'
    )
    has_models = False

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='About Morpheus',
                slug='about',
                view='plugins.installed.release_notes.views.about',
                icon='info',
                section='settings',
                order=94,
                nav='settings',
            ),
            DashboardPage(
                label='Version & updates',
                slug='version',
                view='plugins.installed.release_notes.views.version_updates',
                icon='git-commit-horizontal',
                section='settings',
                order=95,
                nav='settings',
            ),
        ]
