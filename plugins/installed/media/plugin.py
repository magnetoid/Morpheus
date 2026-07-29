"""media plugin manifest."""

from __future__ import annotations

import logging

from morpheus.plugin import DashboardPage, Plugin

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
        # Assets is a core surface — wired directly into the sidebar
        # template (right under Users). Hidden from the
        # plugin-contributed section loop so it doesn't double-render.
        return [
            DashboardPage(
                slug='library',
                label='Assets',
                section='cms',
                icon='image',
                view='plugins.installed.media.views.library',
                order=20,
                nav='main',
            ),
        ]
