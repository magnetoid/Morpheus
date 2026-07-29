"""Importer plugin manifest."""

from __future__ import annotations

from morpheus.plugin import DashboardPage, Plugin


class ImportersPlugin(Plugin):
    name = 'importers'
    label = 'Migration Importers'
    version = '0.2.0'
    description = (
        'Idempotent importers: Shopify, WooCommerce, Magento, BigCommerce, '
        'plus bulk CSV products import/export.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.importers.urls',
            prefix='dashboard/import/',
            namespace='importers',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='csv',
                label='Bulk CSV import / export',
                section='data',
                icon='upload',
                view='plugins.installed.importers.views.csv_index',
                order=10,
                nav='settings',
            ),
            DashboardPage(
                slug='shopify',
                label='Migrate from Shopify',
                section='data',
                icon='download',
                view='plugins.installed.importers.views.shopify_index',
                order=20,
                nav='settings',
            ),
        ]
