"""Release notes plugin — the in-dashboard "Version & updates" page.

Thin, model-less surface that renders [`docs/RELEASE_NOTES.md`](../../../docs/RELEASE_NOTES.md)
— the single source of truth for the Morpheus OS changelog — under
Dashboard → Settings, alongside the live `MORPHEUS_VERSION`.

House rule (torsor ADR "Versioned release notes" + CLAUDE.md): every version
bump adds a `## vX.Y.Z — YYYY-MM-DD` entry to that document. This plugin only
*displays* it; it owns no data.
"""

from __future__ import annotations

from morpheus import DashboardPage, Plugin


class ReleaseNotesPlugin(Plugin):
    name = 'release_notes'
    label = 'Release notes'
    version = '1.0.0'
    description = (
        'The Settings → Version & updates page. Renders docs/RELEASE_NOTES.md '
        '(the Morpheus OS changelog) next to the running version.'
    )
    has_models = False

    def contribute_dashboard_pages(self) -> list:
        return [
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
