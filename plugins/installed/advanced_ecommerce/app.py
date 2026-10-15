"""
Advanced Ecommerce — bundle plugin.

Demonstrates the three plugin contribution surfaces (storefront blocks,
dashboard pages, settings panel) shipped in PR #14. When the merchant
enables this plugin from `/dashboard/apps/`, the storefront and dashboard
both light up with extra features in one move.

What turning this on does
-------------------------
Storefront:
  * "Recently viewed" rail under the home grid.
  * "Low stock" badge in product detail.

Dashboard:
  * "Bulk price edit" page under Plugins.
  * "Low-stock alerts" page under Plugins.

Operations:
  * Hooks into `product.viewed` to track recently-viewed slugs in the
    request session for the storefront block.

Settings (admin):
  * `low_stock_threshold` (int, default 5) — shown as the badge cutoff.
"""

from __future__ import annotations

import logging

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events

logger = logging.getLogger('morpheus.advanced_ecommerce')


class AdvancedEcommercePlugin(Plugin):
    name = 'advanced_ecommerce'
    label = 'Advanced Ecommerce'
    version = '0.1.0'
    description = (
        'Adds advanced storefront blocks (recently-viewed, low-stock badge) '
        'and dashboard tools (bulk price edit, low-stock alerts).'
    )
    has_models = False
    requires = ['catalog', 'orders']

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def ready(self) -> None:
        self.register_hook(events.PRODUCT_VIEWED, self.on_product_viewed, priority=70)

    # ── Hooks ────────────────────────────────────────────────────────────────

    def on_product_viewed(self, product=None, request=None, **kwargs):
        """Track up to 8 recently-viewed product slugs in the session."""
        if request is None or product is None:
            return
        from core.utils.crawlers import is_crawler_user_agent

        # A crawler has no use for a recently-viewed list, and writing one gave
        # every crawled product page a database session and a cookie.
        if is_crawler_user_agent(request.META.get('HTTP_USER_AGENT')):
            return
        try:
            session = getattr(request, 'session', None)
            if session is None:
                return
            slugs = list(session.get('recently_viewed', []) or [])
            slug = getattr(product, 'slug', None)
            if not slug:
                return
            if slug in slugs:
                slugs.remove(slug)
            slugs.insert(0, slug)
            session['recently_viewed'] = slugs[:8]
        except Exception as e:  # noqa: BLE001 — never block product page on session writes
            logger.debug('advanced_ecommerce: recently_viewed track failed: %s', e)

    # ── Contributions ────────────────────────────────────────────────────────

    def contribute_storefront_blocks(self):
        return [
            StorefrontBlock(
                slot='home_after_rails',
                template='advanced_ecommerce/blocks/collection_rails.html',
                priority=30,
                context_keys=['staff_picks_collection'],
            ),
            StorefrontBlock(
                slot='home_below_grid',
                template='advanced_ecommerce/blocks/recently_viewed.html',
                priority=20,
                context_keys=['request'],
            ),
            StorefrontBlock(
                slot='pdp_below_price',
                template='advanced_ecommerce/blocks/low_stock_badge.html',
                priority=20,
                context_keys=['product'],
            ),
        ]

    def contribute_dashboard_pages(self):
        # Both pages (Bulk price edit, Low-stock alerts) used to live as
        # sidebar entries. They now surface in more contextual places:
        #   * Bulk price edit  → button on the Products list page.
        #   * Low-stock alerts → "Stock alerts" section on dashboard home,
        #     visible only when at least one variant is below threshold.
        # The underlying URLs still exist for deep-linking.
        return []

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Advanced Ecommerce',
            description='Behavior toggles for storefront blocks and admin tools.',
            schema=self.get_config_schema(),
            category='storefront',
        )

    # ── Config schema ────────────────────────────────────────────────────────

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enable_collection_rails': {
                    'type': 'boolean',
                    'title': 'Show featured-collection rails on the homepage',
                    'description': 'Each Collection marked "featured" becomes a shoppable slider on the home page.',
                    'default': True,
                },
                'collection_rail_products': {
                    'type': 'integer',
                    'title': 'Products per collection rail',
                    'default': 8,
                },
                'max_collection_rails': {
                    'type': 'integer',
                    'title': 'Max collection rails on the homepage',
                    'default': 3,
                },
                'low_stock_threshold': {
                    'type': 'integer',
                    'title': 'Low-stock badge cutoff',
                    'description': 'PDP shows a "low stock" badge when available units fall below this.',
                    'default': 5,
                },
            },
        }
