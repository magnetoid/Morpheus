"""dynamic_products plugin manifest.

Smart personalized merchandising. Merchants configure ``DynamicBlock``
rows from this plugin's own dashboard settings page; the storefront then
renders each enabled block into its theme slot, tuned per-visitor by the
engine in ``services.py``.

Modularity (both litmus tests pass):

* **Storefront** — one ``StorefrontBlock`` is contributed per real theme
  slot. Each points at this plugin's own ``_slot.html``, which loops over
  the enabled ``DynamicBlock`` rows for that slot. Adding/removing a block
  from the dashboard needs **no** new contribution and **no** theme edit.
* **Dashboard** — a ``DashboardPage(nav='settings')`` points at this
  plugin's own CRUD views, mounted under ``/dashboard/dynamic-products/``
  via ``register_urls``. Nothing is hard-coded into admin_dashboard.
* **Disable** drops every block + the settings page automatically; the
  ``product.viewed`` subscriber stops firing. Nothing survives the toggle.

Behavioral signals are **reused, not rebuilt** — the engine reads the
analytics plugin's durable ``product_view`` events and the session
``recently_viewed`` list maintained by ``advanced_ecommerce``. We keep a
tiny ``product.viewed`` subscriber here only as a safety net so the
session signal exists even if ``advanced_ecommerce`` is disabled; it
writes the same ``session['recently_viewed']`` key (idempotent, capped).
"""

from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin, StorefrontBlock, events

logger = logging.getLogger('morpheus.dynamic_products')

# Slots we contribute a renderer for — the full implemented set. Each maps
# to the same per-slot template, which fans out to the configured blocks.
_SLOTS = [
    'home_above_grid',
    'home_below_grid',
    'pdp_below_price',
    'pdp_below_form',
    'pdp_above_long_description',
    'cart_summary_extra',
    'global_below_body',
]

_RECENTLY_VIEWED_CAP = 8


class DynamicProductsPlugin(Plugin):
    name = 'dynamic_products'
    label = 'Dynamic Products'
    version = '0.1.0'
    description = (
        'Personalized merchandising blocks — for-you, related, recently '
        'viewed, frequently-bought-together — configured per theme slot '
        'from its own dashboard page.'
    )
    has_models = True
    requires = ['catalog', 'orders', 'customers']

    # ── Lifecycle ────────────────────────────────────────────────────────
    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.dynamic_products.urls',
            prefix='dashboard/dynamic-products/',
            namespace='dynamic_products',
        )
        # Safety-net behavioral capture. The durable signal is the
        # analytics plugin's product_view event; the session list is
        # normally written by advanced_ecommerce. We subscribe too so the
        # session signal survives advanced_ecommerce being disabled.
        self.register_hook(events.PRODUCT_VIEWED, self.on_product_viewed, priority=72)

    def on_product_viewed(self, product=None, request=None, **kwargs):
        """Maintain session['recently_viewed'] (idempotent, capped)."""
        if request is None or product is None:
            return
        try:
            session = getattr(request, 'session', None)
            slug = getattr(product, 'slug', None)
            if session is None or not slug:
                return
            slugs = list(session.get('recently_viewed', []) or [])
            if slug in slugs:
                slugs.remove(slug)
            slugs.insert(0, slug)
            session['recently_viewed'] = slugs[:_RECENTLY_VIEWED_CAP]
        except Exception as e:  # noqa: BLE001 — never block the product page
            logger.debug('dynamic_products: recently_viewed track failed: %s', e)

    # ── Contributions ────────────────────────────────────────────────────
    def contribute_storefront_blocks(self) -> list:
        # One renderer per slot; the template renders all enabled blocks
        # for that slot. priority=45 so for-you sits just above the
        # personalisation plugin's FBT block (priority 40) when both target
        # the same slot, without fighting it.
        return [
            StorefrontBlock(
                slot=slot,
                template='dynamic_products/_slot.html',
                priority=45,
                context_keys=['request', 'product', 'cart'],
            )
            for slot in _SLOTS
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Dynamic Products',
                slug='index',
                view='plugins.installed.dynamic_products.views.index',
                icon='sparkles',
                section='marketing',
                order=40,
                nav='settings',
                url='/dashboard/dynamic-products/',
            ),
        ]
