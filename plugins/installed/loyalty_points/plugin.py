"""Loyalty points plugin manifest.

Redemption (v1)
---------------
Points can be spent for a store-currency discount at the rate configured
in the settings panel (``redemption_rate``: points per 1.00 unit,
default 100). The discount math + ledger live in ``services_redeem.py``;
the *application* of a redemption to an order total rides the existing
``CART_CALCULATE_BREAKDOWN`` filter (``on_cart_breakdown`` below) — the
same hook gift cards and coupons use. This keeps loyalty decoupled from
the orders plugin: orders fires the filter, we answer it.

Remaining checkout wiring (deferred — see
``docs/plans/morph-backlog-2026-06.md`` → "Loyalty redemption"):

  1. A cart-side endpoint (``/checkout/points/apply/`` +
     ``/checkout/points/remove/``) that writes the shopper's chosen spend
     to ``cart.metadata['loyalty_points_redeem']`` (an int), bounded by
     ``services_redeem.max_redeemable(customer, order_total)``. The
     breakdown hook below already *reads* that key, so until the endpoint
     exists the hook is a no-op on live carts.
  2. Recording the spend at order-creation time. ``OrderService.
     create_from_cart`` already redeems gift cards from ``breakdown.meta``;
     mirror that: when ``meta['loyalty_points']`` is present, call
     ``services_redeem.redeem_points(customer, points, order=order)`` and,
     on cancel/refund, ``reverse_redemption(...)``. This is the only edit
     that touches the orders plugin and is left out of v1 deliberately.

The account surface (``/account/points/``) lets a logged-in customer see
their balance and what it is worth today — shipped in v1.
"""

# ruff: noqa: PLC0415
# Inline imports keep the manifest importable before the app registry is
# ready (this module is loaded at settings-import time).
from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock, events


class LoyaltyPointsPlugin(Plugin):
    name = 'loyalty_points'
    label = 'Loyalty points'
    version = '0.2.0'
    description = (
        'Earn 1 point per currency unit on paid orders. Balance shown on '
        'the customer account page. Points redeem for a store-currency '
        'discount at a configurable rate (default 100 pts = 1.00).'
    )
    has_models = True
    requires = ['orders', 'customers']

    def ready(self) -> None:
        # Answer the canonical cart-total filter so a chosen point spend
        # becomes an order discount, alongside coupons + gift cards.
        self.register_hook(events.CART_CALCULATE_BREAKDOWN, self.on_cart_breakdown, priority=15)
        # Own the customer-facing /account/points/ route (modular-os: the
        # route only exists while the plugin is enabled).
        self.register_urls(
            'plugins.installed.loyalty_points.urls',
            prefix='',
            namespace='loyalty_points',
        )
        # Contribute the points balance into the account-home summary so
        # the account_nav tile can show it. Only fires while enabled.
        self.register_hook(events.ACCOUNT_SUMMARY_FIELDS, self.on_account_summary, priority=50)
        # Contribute points-earned activity to the dashboard home feed.
        self.register_hook(events.ACTIVITY_FEED, self.on_activity_feed, priority=50)

    def on_account_summary(self, value, user=None, **kwargs):
        """Fold this customer's points balance into the account summary.

        Subscribes to ``ACCOUNT_SUMMARY_FIELDS`` (a filter): mutate the
        dict, return it. Fail-soft — never break the account page.
        """
        try:
            from plugins.installed.loyalty_points.services import get_balance

            value['loyalty_points'] = get_balance(user)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.loyalty').warning(
                'account_summary points fold failed: %s', exc, exc_info=True
            )
        return value

    def on_activity_feed(self, value, limit=20, **kwargs):
        """Fold recent points awards into the dashboard home feed
        (``ACTIVITY_FEED`` filter). Append own items, return the list.
        """
        from plugins.installed.loyalty_points.models import PointsTransaction  # noqa: PLC0415

        qs = (
            PointsTransaction.objects.select_related('customer')
            .filter(reason='earn_order')
            .order_by('-created_at')
        )
        for tx in qs[:limit]:
            who = tx.customer.email if tx.customer else 'a reader'
            value.append(
                {
                    'kind': 'loyalty',
                    'icon': 'award',
                    'label': f'+{tx.points} reader points to {who}',
                    'hint': tx.note or f'Order #{tx.order_number}',
                    'url': f'/dashboard/customers/?q={who}',
                    'when': tx.created_at,
                }
            )
        return value

    def contribute_storefront_blocks(self) -> list:
        # Account-home tile → /account/points/. Lives with the plugin so a
        # disabled plugin drops the tile (registry-gated contribution).
        return [
            StorefrontBlock(
                slot='account_nav',
                template='loyalty_points/blocks/account_nav.html',
                priority=50,
            ),
        ]

    @staticmethod
    def _requested_redeem(value, cart, customer) -> int:
        """Resolve the capped point spend for this cart, or 0 if none.

        Reads ``cart.metadata['loyalty_points_redeem']`` and caps it at
        the customer's balance + policy against the current total.
        """
        if cart is None or not isinstance(value, dict):
            return 0
        try:
            requested = int(
                (getattr(cart, 'metadata', None) or {}).get('loyalty_points_redeem') or 0
            )
        except (TypeError, ValueError):
            return 0
        if requested <= 0:
            return 0
        cust = customer if customer is not None else getattr(cart, 'customer', None)
        if cust is None or not getattr(cust, 'is_authenticated', False):
            return 0
        from plugins.installed.loyalty_points.services_redeem import max_redeemable

        return max(0, min(requested, max_redeemable(cust, order_total=value.get('total'))))

    def on_cart_breakdown(self, value, cart=None, customer=None, **kwargs):
        """Turn ``cart.metadata['loyalty_points_redeem']`` into a discount.

        Folds the points-value into ``discount`` + ``total`` and records
        the intended spend in ``meta['loyalty_points']`` so order-creation
        can debit the ledger. Fail-soft: any error leaves the cart
        unchanged.
        """
        try:
            points = self._requested_redeem(value, cart, customer)
            if points <= 0:
                return value

            from decimal import Decimal

            from djmoney.money import Money

            from plugins.installed.loyalty_points.services_redeem import points_to_amount

            currency = str(value.get('currency') or 'USD')
            credit = Decimal(str(points_to_amount(points, currency).amount))
            base_discount = Decimal(str(getattr(value.get('discount'), 'amount', 0) or 0))
            base_total = Decimal(str(getattr(value.get('total'), 'amount', 0) or 0))
            new_total = max(Decimal('0'), base_total - credit)

            value['discount'] = Money((base_discount + credit).quantize(Decimal('0.01')), currency)
            value['total'] = Money(new_total.quantize(Decimal('0.01')), currency)
            meta = value.get('meta') or {}
            meta['loyalty_points'] = {'points': points, 'amount': str(credit)}
            value['meta'] = meta
        except Exception:  # noqa: BLE001 — never break the cart over a loyalty discount
            return value
        return value

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'redemption_rate': {
                    'type': 'integer',
                    'title': 'Redemption rate (points per 1.00)',
                    'description': 'How many points equal one unit of store currency. '
                    '100 means 100 points = 1.00 off.',
                    'minimum': 1,
                    'default': 100,
                },
                'max_redeem_fraction': {
                    'type': 'number',
                    'title': 'Max share of an order points can cover',
                    'description': '1.0 = points may pay the whole order; 0.5 = up to half.',
                    'minimum': 0.01,
                    'maximum': 1.0,
                    'default': 1.0,
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Loyalty points',
            description='Set the point→currency redemption rate shoppers get at checkout.',
            schema=self.get_config_schema(),
            category='marketing',
        )
