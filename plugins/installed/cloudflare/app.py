"""Cloudflare plugin manifest."""
# ruff: noqa: PLC0415 — service/model imports are lazy inside hooks (load-order safe).

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events

logger = logging.getLogger('morpheus.cloudflare')


class CloudflarePlugin(Plugin):
    name = 'cloudflare'
    label = 'Cloudflare'
    version = '0.1.0'
    description = (
        'Cloudflare cache purge + DNS integration. Auto-purges on product/collection updates.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.cloudflare.graphql.queries')
        self.register_graphql_extension('plugins.installed.cloudflare.graphql.mutations')
        self.register_urls(
            'plugins.installed.cloudflare.urls',
            prefix='dashboard/cloudflare/',
            namespace='cloudflare',
        )
        self.register_hook(events.PRODUCT_UPDATED, self.on_product_updated, priority=85)
        self.register_hook(events.PRODUCT_CREATED, self.on_product_updated, priority=85)
        self.register_hook(events.CATEGORY_UPDATED, self.on_category_updated, priority=85)
        # "These URLs changed at the origin" — fired by seo when a meta
        # override, a redirect or a sitemap is written. Those rewrite cached
        # HTML without touching the product or category row, so none of the
        # hooks above sees them and the edge kept serving the old page.
        self.register_hook(events.EDGE_PURGE_URLS, self.on_edge_purge_urls, priority=85)

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Cloudflare',
                slug='overview',
                view='plugins.installed.cloudflare.views.overview',
                icon='cloud',
                section='developer',
                order=15,
                nav='settings',
                url='/dashboard/cloudflare/',
            ),
        ]

    def on_product_updated(self, product, **kwargs):
        try:
            from plugins.installed.cloudflare.services import purge_for_product_update

            purge_for_product_update(product)
        except Exception as e:  # noqa: BLE001 — log + swallow, never break order/catalog flow
            logger.warning('cloudflare: hook purge failed: %s', e, exc_info=True)

    def on_category_updated(self, category=None, **kwargs):
        if category is None:
            return
        try:
            from plugins.installed.cloudflare.models import CloudflareZone
            from plugins.installed.cloudflare.services import (
                purge_for_category_update,
                purge_urls,
            )

            qs = CloudflareZone.objects.filter(
                is_active=True,
                auto_purge_on_collection_update=True,
            ).select_related('account')
            slug = getattr(category, 'slug', '')
            for zone in qs:
                purge_urls(
                    zone=zone,
                    # `/category/<slug>/` — the route the storefront actually
                    # serves. This purged `/c/<slug>` (no trailing slash, wrong
                    # prefix), and a Cloudflare file purge is exact-URL, so
                    # category HTML was never actually dropped from the edge.
                    urls=[f'https://{zone.domain}/category/{slug}/'],
                    triggered_by=f'category:{getattr(category, "id", "")}',
                )
            # Tag purge — drops matching GraphQL responses (see
            # MorpheusGraphQLView._extract_entity_tags).
            purge_for_category_update(category)
        except Exception as e:  # noqa: BLE001
            logger.warning('cloudflare: category hook purge failed: %s', e, exc_info=True)

    def on_edge_purge_urls(self, urls=None, reason='', **kwargs):
        """Purge arbitrary site-relative paths on every auto-purging zone."""
        paths = [u for u in (urls or []) if u]
        if not paths:
            return
        try:
            from plugins.installed.cloudflare.models import CloudflareZone
            from plugins.installed.cloudflare.services import purge_urls

            zones = CloudflareZone.objects.filter(
                is_active=True, auto_purge_on_product_update=True
            ).select_related('account')
            for zone in zones:
                purge_urls(
                    zone=zone,
                    urls=[f'https://{zone.domain}{p}' if p.startswith('/') else p for p in paths],
                    triggered_by=reason or 'edge.purge_urls',
                )
        except Exception as e:  # noqa: BLE001 — a CDN must never fail the write that triggered it
            logger.warning('cloudflare: edge purge failed: %s', e, exc_info=True)

    # Cloudflare config (API token, zones, purge policy) lives on
    # CloudflareAccount + CloudflareZone rows, managed on the Cloudflare
    # dashboard page (views.overview). No separate SettingsPanel for that — it
    # was a duplicate "Cloudflare" entry whose schema nothing read (ADR 0003).

    # Turnstile config IS read (by verify_turnstile + the {% turnstile %} tag),
    # so it's a real schema-driven settings panel, not a duplicate.
    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'turnstile_enabled': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Enable Cloudflare Turnstile',
                    'description': 'Bot/CAPTCHA-free protection on public forms (affiliate apply, contact, signup).',
                },
                'turnstile_site_key': {
                    'type': 'string',
                    'default': '',
                    'title': 'Turnstile site key',
                    'description': 'Public key (0x…). Cloudflare dashboard → Turnstile → your widget.',
                },
                'turnstile_secret_key': {
                    'type': 'string',
                    'format': 'password',
                    'default': '',
                    'title': 'Turnstile secret key',
                    'description': 'Private key — used server-side to verify the challenge. Keep it secret.',
                },
            },
        }

    def contribute_settings_panel(self):
        from morpheus.app import SettingsPanel

        return SettingsPanel(
            label='Turnstile',
            description='Cloudflare Turnstile bot protection for public forms.',
            schema=self.get_config_schema(),
            category='general',
        )
