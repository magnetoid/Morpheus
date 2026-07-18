"""Eco impact plugin manifest.

Shows each book's *production* footprint (paper → wood, embodied CO₂ from its
physical attributes) on the storefront product page, and lets shoppers opt in
at checkout to a flat "plant a tree" offset. The offset money is a tracked fund
the merchant fulfils — no external reforestation provider in v1; copy stays
honest ("we direct this to reforestation"), never a fabricated per-order claim.

Boundary: shipping-lane carbon is owned by ``smart_shipping`` (CarrierEmission).
This plugin does NOT recompute shipping carbon — it owns the address-independent
production footprint + the tree offset. The offset rides the canonical
``CART_CALCULATE_BREAKDOWN`` filter (like loyalty/coupons/gift cards), so the
orders plugin fires and we answer — no storefront/theme edits.
"""

# ruff: noqa: PLC0415
# Inline imports keep the manifest importable at settings-import time.
from __future__ import annotations

from morpheus import DashboardPage, Plugin, SettingsPanel, StorefrontBlock, events


class EcoImpactPlugin(Plugin):
    name = 'eco_impact'
    label = 'Eco impact'
    version = '0.1.0'
    description = (
        "Show a book's paper/wood/CO₂ production footprint on its product page, "
        'and let shoppers plant a tree at checkout to offset the order. Tree '
        'pledges are tracked as a fund the merchant fulfils.'
    )
    has_models = True
    requires = ['orders', 'book_product']

    def ready(self) -> None:
        # Add the flat opt-in surcharge to the cart total. High priority number
        # → runs last, so the tree offset sits on top of tax/shipping/discount.
        self.register_hook(events.CART_CALCULATE_BREAKDOWN, self.on_cart_breakdown, priority=60)
        # Void the pledge if the order is cancelled (keeps store totals honest).
        self.register_hook(events.ORDER_CANCELLED, self.on_order_cancelled, priority=50)
        # Own the storefront opt-in endpoints + the public "Save the planet"
        # page. Registry-gated: routes exist only while the plugin is enabled.
        self.register_urls(
            'plugins.installed.eco_impact.urls',
            prefix='',
            namespace='eco_impact',
        )

    # ── checkout surcharge ─────────────────────────────────────────────────

    def on_cart_breakdown(self, value, cart=None, **kwargs):
        """Add the flat tree-offset amount when the cart opted in.

        Mutates ``total`` and records the intent in ``meta['eco_impact']`` so
        order creation can write the pledge ledger row. Fail-soft.
        """
        try:
            if cart is None or not isinstance(value, dict):
                return value
            if not (getattr(cart, 'metadata', None) or {}).get('eco_impact_optin'):
                return value

            from decimal import Decimal

            from djmoney.money import Money

            from plugins.installed.eco_impact.services import surcharge_amount

            currency = str(value.get('currency') or 'USD')
            amt = surcharge_amount()
            base_total = Decimal(str(getattr(value.get('total'), 'amount', 0) or 0))
            value['total'] = Money((base_total + amt).quantize(Decimal('0.01')), currency)
            meta = value.get('meta') or {}
            meta['eco_impact'] = {'trees': 1, 'amount': str(amt)}
            value['meta'] = meta
        except Exception:  # noqa: BLE001 — never break the cart over the offset
            return value
        return value

    def on_order_cancelled(self, order=None, **kwargs):
        if order is None:
            return
        try:
            from plugins.installed.eco_impact.services import remove_pledge

            remove_pledge(order)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.eco_impact').warning(
                'eco pledge void failed for order %s: %s',
                getattr(order, 'order_number', '?'),
                exc,
            )

    # ── contributions ──────────────────────────────────────────────────────

    def contribute_storefront_blocks(self) -> list:
        return [
            # Production-footprint badge under the price on the book PDP.
            StorefrontBlock(
                slot='pdp_below_price',
                template='eco_impact/blocks/pdp_badge.html',
                priority=50,
            ),
            # "Plant a tree" opt-in in the cart summary (the slot the theme
            # actually renders — checkout_extra is not emitted by dot_books).
            StorefrontBlock(
                slot='cart_summary_extra',
                template='eco_impact/blocks/cart_optin.html',
                priority=40,
            ),
            # Footer link to the public impact page.
            StorefrontBlock(
                slot='footer_extra',
                template='eco_impact/blocks/footer_link.html',
                priority=50,
            ),
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'show_on_pdp': {
                    'type': 'boolean',
                    'title': 'Show the footprint badge on product pages',
                    'default': True,
                },
                'tree_price': {
                    'type': 'number',
                    'title': 'Plant-a-tree offset amount',
                    'description': 'Flat amount added when a shopper opts in at checkout.',
                    'minimum': 0.01,
                    'default': 1.50,
                },
                'kg_co2_per_tree': {
                    'type': 'number',
                    'title': 'CO₂ offset per tree (kg)',
                    'description': 'Used to size the offset claim. ~21 kg/yr is the common figure.',
                    'minimum': 1,
                    'default': 21.0,
                },
                'wood_factor': {
                    'type': 'number',
                    'title': 'Wood per kg of paper (kg)',
                    'description': 'Advanced: kg of wood per kg of paper. Default 2.5.',
                    'minimum': 0.1,
                    'default': 2.5,
                },
                'co2_per_kg_paper': {
                    'type': 'number',
                    'title': 'CO₂ per kg of paper (kg)',
                    'description': 'Advanced: production emissions per kg paper. Default 1.3.',
                    'minimum': 0.1,
                    'default': 1.3,
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Eco impact',
            description='Footprint badge + plant-a-tree checkout offset.',
            schema=self.get_config_schema(),
            category='marketing',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Eco impact',
                slug='eco_impact',
                view='plugins.installed.eco_impact.views.dashboard',
                icon='leaf',
                section='marketing',
                order=55,
                url='/dashboard/eco-impact/',
            ),
        ]
