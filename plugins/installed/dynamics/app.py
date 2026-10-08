"""dynamics plugin manifest.

Smart personalized merchandising. Merchants configure ``DynamicBlock``
rows from this plugin's own dashboard settings page; the storefront then
renders each enabled block into its theme slot, tuned per-visitor by the
engine in ``services.py``.

Automated + self-optimizing (all pure-Python, no ML deps):
``services.calculate_grid_probabilities`` scores every product's real
purchase-propensity nightly; the ``autopilot`` strategy Thompson-reranks that
per visitor-segment (``reranker.py`` + ``BanditArm``, learned nightly from
engagement); and ``autopilot.py`` runs a nightly propose-only AI merchandiser
whose suggestions land in a human-checkpoint review queue. See
``docs/plans/dynamics-autopilot-2026-07.md``.

Modularity (both litmus tests pass):

* **Storefront** — one ``StorefrontBlock`` is contributed per real theme
  slot. Each points at this plugin's own ``_slot.html``, which loops over
  the enabled ``DynamicBlock`` rows for that slot. Adding/removing a block
  from the dashboard needs **no** new contribution and **no** theme edit.
* **Dashboard** — a ``DashboardPage(nav='settings')`` points at this
  plugin's own CRUD views, mounted under ``/dashboard/dynamics/``
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

from morpheus.app import DashboardPage, Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events

logger = logging.getLogger('morpheus.dynamics')

# Slots we contribute a renderer for — the full implemented set. Each maps
# to the same per-slot template, which fans out to the configured blocks.
_SLOTS = [
    'home_above_grid',
    'home_below_grid',
    'home_after_rails',
    'pdp_below_price',
    'pdp_below_form',
    'pdp_above_long_description',
    'cart_summary_extra',
    'checkout_extra',
    'order_receipt_extra',
    'global_below_body',
]

_RECENTLY_VIEWED_CAP = 8


class DynamicsPlugin(Plugin):
    name = 'dynamics'
    label = 'Dynamics'
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
            'plugins.installed.dynamics.urls',
            prefix='dashboard/dynamics/',
            namespace='dynamics',
        )
        # Safety-net behavioral capture. The durable signal is the
        # analytics plugin's product_view event; the session list is
        # normally written by advanced_ecommerce. We subscribe too so the
        # session signal survives advanced_ecommerce being disabled.
        self.register_hook(events.PRODUCT_VIEWED, self.on_product_viewed, priority=72)
        # Surface takeover: control the theme's existing product placeholders
        # (home hero/featured/staff picks, PLP ordering, page-builder sections)
        # when a block is bound to the surface. See placeholders.py.
        from plugins.installed.dynamics import placeholders  # noqa: PLC0415

        self.register_hook(events.STOREFRONT_PRODUCTS, placeholders.provide, priority=40)
        # Automated propensity refresh: a nightly full recompute + a throttled
        # refresh after each order, so DynamicGridItem.purchase_probability tracks
        # real demand with zero merchant effort. Tasks live in tasks.py.
        from celery.schedules import crontab  # noqa: PLC0415

        self.register_celery_tasks('plugins.installed.dynamics.tasks')
        self.register_celery_beat(
            'dynamics:recompute_probabilities',
            {
                'task': 'dynamics.recompute_probabilities',
                'schedule': crontab(hour=3, minute=30),
            },
        )
        # Self-optimizing bandit: rebuild per-segment posteriors nightly, just
        # after the propensity recompute it blends with.
        self.register_celery_beat(
            'dynamics:rebuild_bandit_posteriors',
            {
                'task': 'dynamics.rebuild_bandit_posteriors',
                'schedule': crontab(hour=4, minute=0),
            },
        )
        # AI merchandiser: file merchandising proposals into the review queue
        # each morning (after the propensity + bandit rebuilds it reasons over).
        self.register_celery_beat(
            'dynamics:merchandiser',
            {
                'task': 'dynamics.generate_merchandising_proposals',
                'schedule': crontab(hour=5, minute=0),
            },
        )
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=80)

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
            logger.debug('dynamics: recently_viewed track failed: %s', e)

    def on_order_placed(self, order=None, **kwargs):
        """After a sale, debounce a probability refresh so the grid reflects the
        new demand ahead of the nightly run. Never blocks checkout."""
        try:
            from plugins.installed.dynamics.tasks import (  # noqa: PLC0415
                refresh_probabilities_throttled,
            )

            refresh_probabilities_throttled.delay()
        except Exception as e:  # noqa: BLE001 — a queue hiccup must not fail an order
            logger.debug('dynamics: refresh enqueue failed: %s', e)

    # ── Contributions ────────────────────────────────────────────────────
    def contribute_storefront_blocks(self) -> list:
        # One renderer per slot; the template renders all enabled blocks
        # for that slot. priority=45 so for-you sits just above the
        # personalisation plugin's FBT block (priority 40) when both target
        # the same slot, without fighting it.
        return [
            StorefrontBlock(
                slot=slot,
                template='dynamics/_slot.html',
                priority=45,
                context_keys=['request', 'product', 'cart'],
            )
            for slot in _SLOTS
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Dynamics',
                slug='index',
                view='plugins.installed.dynamics.views.index',
                icon='sparkles',
                section='storefront',
                order=40,
                nav='settings',
                url='/dashboard/dynamics/',
                hint='Personalised merchandising blocks per theme slot',
            ),
            DashboardPage(
                label='Autopilot proposals',
                slug='proposals',
                view='plugins.installed.dynamics.views.proposals',
                icon='wand-2',
                section='storefront',
                order=41,
                nav='settings',
                url='/dashboard/dynamics/proposals/',
                hint='Merchandising changes Autopilot suggests',
            ),
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'auto_apply': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Auto-apply low-risk proposals',
                    'description': (
                        'When on, the nightly merchandiser applies its low-risk '
                        'proposals (turn on Autopilot, feature high-intent products) '
                        'automatically instead of queuing them for review. '
                        'Informational insights still wait for you.'
                    ),
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Autopilot',
            description='Controls for the self-optimizing merchandiser.',
            schema=self.get_config_schema(),
            category='storefront',
        )
