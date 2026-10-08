"""media plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin

logger = logging.getLogger('morpheus.media')


class MediaPlugin(Plugin):
    name = 'media'
    label = 'Asset manager'
    version = '0.2.0'
    description = (
        'Unified asset manager — images, video, audio, PDFs, '
        'spreadsheets, Word docs, and digital downloadable products. '
        'Tabbed library with per-type counts; uploads land in MediaAsset, '
        'digital products live alongside as catalog rows with attached '
        'files. Per-asset alt text + tags + search.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.media.urls',
            prefix='dashboard/media/',
            namespace='media',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.media.agent_tools import media_search_tool  # noqa: PLC0415

        return [media_search_tool]

    def contribute_dashboard_pages(self) -> list:
        # The media library, a tab of the Content section.
        return [
            DashboardPage(
                slug='library',
                label='Media',
                section='content',
                icon='image',
                view='plugins.installed.media.views.library',
                order=50,
                nav='main',
            ),
        ]
