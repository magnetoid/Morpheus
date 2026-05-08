"""media plugin manifest."""
from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin

logger = logging.getLogger('morpheus.media')


class MediaPlugin(Plugin):
    name = 'media'
    label = 'Media library'
    version = '0.1.0'
    description = (
        'Central asset library — upload images, documents, and other '
        'files once and reference them across products, CMS pages, '
        'email templates, themes, and metafields. Per-asset alt text + '
        'tags + search; soft references rather than orphaning.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.media.urls',
            prefix='dashboard/media/',
            namespace='media',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='library',
                label='Media library',
                section='cms',
                icon='image',
                view='plugins.installed.media.views.library',
                order=20,
                nav='main',
            ),
        ]
