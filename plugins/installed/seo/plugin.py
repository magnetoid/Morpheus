"""SEO plugin manifest — deep extension."""
from __future__ import annotations

import logging

from morpheus import events
from morpheus import Plugin
from morpheus import DashboardPage, SettingsPanel

logger = logging.getLogger('morpheus.seo')


class SeoPlugin(Plugin):
    name = 'seo'
    label = 'SEO'
    version = '2.0.0'
    description = (
        'Deep SEO: per-object meta + full JSON-LD (Product / Organization / '
        'BreadcrumbList / WebSite / Article / FAQ / Review), OpenGraph + '
        'Twitter Cards, sitemap.xml + robots.txt, redirects + 404 monitor '
        'with auto-redirect suggester, per-product audit + scoring, '
        'bulk meta editor, keyword tracking, and LLM discovery surfaces '
        '(/llms.txt + /llms-full.txt + /ai/products.json).'
    )
    has_models = True

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.seo.graphql.queries')
        self.register_graphql_extension('plugins.installed.seo.graphql.mutations')
        self.register_urls('plugins.installed.seo.urls', prefix='', namespace='seo')
        self.register_urls(
            'plugins.installed.seo.urls_dashboard',
            prefix='dashboard/seo/', namespace='seo_dashboard',
        )
        self.register_hook(events.PRODUCT_CREATED, self.on_product_created, priority=85)
        self.register_hook(events.PRODUCT_UPDATED, self.on_product_updated, priority=85)

    def on_product_created(self, product, **kwargs):
        try:
            from plugins.installed.seo.services import autofill_meta_for, store_audit, audit_product
            autofill_meta_for(product)
            store_audit(product, audit_product(product))
        except Exception as e:  # noqa: BLE001 — autofill is best-effort
            logger.warning('seo: autofill/audit failed for %s: %s', product.id, e, exc_info=True)
        self._indexnow_push(product)

    def on_product_updated(self, product, **kwargs):
        """Refresh the SEO score when a product changes."""
        try:
            from plugins.installed.seo.services import audit_product, store_audit
            store_audit(product, audit_product(product))
        except Exception as e:  # noqa: BLE001
            logger.debug('seo: refresh-audit failed for %s: %s', product.id, e)
        self._indexnow_push(product)

    def _indexnow_push(self, product) -> None:
        """Notify Bing/Yandex/Naver/Seznam/Yep about this product URL.

        Fire-and-forget — IndexNow failures must never block the
        save/update flow. Skipped when the merchant has disabled
        IndexNow in plugin config.
        """
        try:
            cfg = self.get_config()
            if not cfg.get('indexnow_enabled', True):
                return
            slug = getattr(product, 'slug', '')
            if not slug:
                return
            from plugins.installed.seo.services import _site_base_url, ping_indexnow
            url = f'{_site_base_url().rstrip("/")}/products/{slug}/'
            import threading
            threading.Thread(target=ping_indexnow, args=([url],), daemon=True).start()
        except Exception as e:  # noqa: BLE001
            logger.debug('seo: IndexNow push failed for %s: %s', getattr(product, 'id', '?'), e)

    def contribute_agent_tools(self) -> list:
        from plugins.installed.seo.agent_tools import (
            apply_internal_links_tool, audit_all_tool, audit_product_tool,
            bulk_set_meta_tool, create_redirect_tool, get_meta_tool,
            list_404s_tool, set_meta_tool, set_site_settings_tool,
        )
        return [
            get_meta_tool, set_meta_tool,
            audit_product_tool, audit_all_tool,
            list_404s_tool, create_redirect_tool,
            bulk_set_meta_tool, set_site_settings_tool,
            apply_internal_links_tool,
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='SEO', slug='overview',
                view='plugins.installed.seo.views.seo_overview',
                icon='search', section='seo', order=10,
            ),
            DashboardPage(
                label='Bulk meta', slug='bulk-meta',
                view='plugins.installed.seo.views.bulk_meta',
                icon='edit-3', section='seo', order=20,
            ),
            DashboardPage(
                label='Audit', slug='audit',
                view='plugins.installed.seo.views.audit_page',
                icon='gauge', section='seo', order=30,
            ),
            DashboardPage(
                label='404s', slug='not-found',
                view='plugins.installed.seo.views.not_found_log',
                icon='alert-triangle', section='seo', order=40,
            ),
            DashboardPage(
                label='Keywords', slug='keywords',
                view='plugins.installed.seo.views.keywords_page',
                icon='hash', section='seo', order=50,
            ),
            DashboardPage(
                label='Sitemap', slug='sitemap',
                view='plugins.installed.seo.views.sitemap_page',
                icon='map', section='seo', order=55,
            ),
            DashboardPage(
                label='Site SEO settings', slug='settings',
                view='plugins.installed.seo.views.seo_settings_page',
                icon='settings', section='seo', order=60,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='SEO',
            description='Site-wide SEO defaults, JSON-LD, AI discovery feeds, audits.',
            schema={'type': 'object', 'properties': {}},
            category='channels',
        )
