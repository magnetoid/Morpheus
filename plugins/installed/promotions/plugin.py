"""Promotions plugin manifest."""

from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin

logger = logging.getLogger('morpheus.promotions')


class PromotionsPlugin(Plugin):
    name = 'promotions'
    label = 'Promotions'
    version = '1.0.0'
    description = (
        'Rule-based promotion engine: stack predicates (cart total, channel, '
        'country, customer group, product) with actions (% off, fixed off, '
        'free shipping, gift). Channel-scoped, time-bounded, audit-logged.'
    )
    has_models = True
    requires = ['orders']

    def ready(self) -> None:
        from morpheus import events

        # CART_CALCULATE_TOTAL is deprecated — the canonical event is
        # CART_CALCULATE_BREAKDOWN, fired from OrderService since 2026-04.
        self.register_hook(events.CART_CALCULATE_BREAKDOWN, self.on_cart_breakdown, priority=10)
        self.register_urls(
            'plugins.installed.promotions.urls',
            prefix='dashboard/promotions/',
            namespace='promotions',
        )

    def on_cart_breakdown(  # noqa: PLR0912, PLR0915
        self,
        value,
        cart=None,
        channel=None,
        customer=None,  # noqa: PLR0912, PLR0915
        address=None,
        coupon=None,
        **kwargs,
    ):
        if cart is None or not isinstance(value, dict):
            return value

        currency = str(value.get('currency') or 'USD')
        subtotal = value.get('subtotal')
        if subtotal is None:
            return value

        from decimal import Decimal

        from djmoney.money import Money

        meta = value.get('meta') or {}
        meta.setdefault('applied_promotions', [])

        free_shipping = bool(meta.get('free_shipping'))
        discount_total = Decimal(str(getattr(value.get('discount'), 'amount', 0) or 0))

        try:
            from plugins.installed.promotions.services import evaluate

            country = (address or {}).get('country', '') if address else ''
            applied = evaluate(
                cart, channel=channel, customer=customer, country=country, coupon=coupon
            )
            for a in applied:
                if a.free_shipping:
                    free_shipping = True
                if a.discount_amount:
                    discount_total += Decimal(str(a.discount_amount))
                meta['applied_promotions'].append(
                    {
                        'promotion_id': a.promotion_id,
                        'promotion_name': a.promotion_name,
                        'rule_id': a.rule_id,
                        'discount_amount': str(a.discount_amount),
                        'free_shipping': bool(a.free_shipping),
                        'gift_product_id': a.gift_product_id,
                        'note': a.note,
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.warning('promotions: evaluate failed: %s', e, exc_info=True)

        coupon_discount = Decimal('0')
        try:
            if cart.coupon_id:
                c = cart.coupon
                if c and c.is_valid:
                    min_ok = True
                    if c.minimum_order_amount:
                        min_ok = Decimal(str(subtotal.amount)) >= Decimal(
                            str(c.minimum_order_amount.amount)
                        )
                    if min_ok:
                        if c.discount_type == 'percentage':
                            coupon_discount = (
                                Decimal(str(subtotal.amount))
                                * Decimal(str(c.discount_value))
                                / Decimal('100')
                            ).quantize(Decimal('0.01'))
                        elif c.discount_type == 'fixed_amount':
                            coupon_discount = Decimal(str(c.discount_value)).quantize(
                                Decimal('0.01')
                            )
                        elif c.discount_type == 'free_shipping':
                            free_shipping = True
                        if c.maximum_discount_amount and coupon_discount:
                            coupon_discount = min(
                                coupon_discount, Decimal(str(c.maximum_discount_amount.amount))
                            )

                        if c.usage_limit_per_customer and customer is not None:
                            from plugins.installed.marketing.models import CouponUsage

                            used_count = CouponUsage.objects.filter(
                                coupon=c, customer=customer
                            ).count()
                            if used_count >= int(c.usage_limit_per_customer):
                                coupon_discount = Decimal('0')

                        if coupon_discount > 0:
                            meta['coupon'] = {
                                'code': c.code,
                                'discount_amount': str(coupon_discount),
                            }
        except Exception as e:  # noqa: BLE001
            logger.warning('promotions: coupon evaluation failed: %s', e, exc_info=True)

        if free_shipping:
            meta['free_shipping'] = True

        discount_total += coupon_discount

        # Gift card stacks AFTER coupon — first coupon discounts the
        # subtotal, then the gift card pays down whatever remains
        # (capped at the card's available balance and the order total).
        # Currency mismatch is silently skipped so a 500 doesn't surface
        # at checkout; merchants see the unapplied state on the cart.
        gift_card_applied = Decimal('0')
        try:
            if getattr(cart, 'gift_card_id', None):
                gc = cart.gift_card
                if (
                    gc
                    and gc.state == 'active'
                    and str(gc.balance.currency) == currency
                    and gc.balance.amount > 0
                ):
                    total_amount = Decimal(str(subtotal.amount))
                    shipping_amount = Decimal(str(getattr(value.get('shipping'), 'amount', 0) or 0))
                    tax_amount = Decimal(str(getattr(value.get('tax'), 'amount', 0) or 0))
                    remaining = total_amount + shipping_amount + tax_amount - discount_total
                    if remaining > 0:
                        gift_card_applied = min(
                            Decimal(str(gc.balance.amount)),
                            remaining,
                        ).quantize(Decimal('0.01'))
                        meta['gift_card'] = {
                            'code': gc.code,
                            'amount': str(gift_card_applied),
                        }
        except Exception as e:  # noqa: BLE001
            logger.warning('promotions: gift card evaluation failed: %s', e, exc_info=True)

        discount_total += gift_card_applied

        value['discount'] = Money(discount_total.quantize(Decimal('0.01')), currency)
        value['meta'] = meta

        try:
            total_amount = Decimal(str(subtotal.amount))
            shipping_amount = Decimal(str(getattr(value.get('shipping'), 'amount', 0) or 0))
            tax_amount = Decimal(str(getattr(value.get('tax'), 'amount', 0) or 0))
            new_total = total_amount + shipping_amount + tax_amount - discount_total
            if new_total < 0:
                new_total = Decimal('0')
            value['total'] = Money(new_total.quantize(Decimal('0.01')), currency)
        except Exception:
            import logging

            logging.getLogger(__name__).warning('Suppressed exception', exc_info=True)

        return value

    def on_cart_total(
        self, value, cart=None, channel=None, customer=None, address=None, coupon=None, **kwargs
    ):
        if cart is None or value is None:
            return value
        try:
            from plugins.installed.promotions.services import evaluate

            country = (address or {}).get('country', '') if address else ''
            applied = evaluate(
                cart, channel=channel, customer=customer, country=country, coupon=coupon
            )
            if not applied:
                return value
            from decimal import Decimal

            discount = sum((a.discount_amount for a in applied), Decimal('0'))
            if not discount:
                return value
            try:
                amount_attr = getattr(value, 'amount', None)
                if amount_attr is not None:
                    new_amount = max(Decimal('0'), Decimal(str(amount_attr)) - discount)
                    return type(value)(new_amount, value.currency)
            except Exception:  # noqa: BLE001
                import logging

            logging.getLogger(__name__).warning('Suppressed exception', exc_info=True)
            return value
        except Exception as e:  # noqa: BLE001
            logger.warning('promotions: on_cart_total failed: %s', e, exc_info=True)
            return value

    def contribute_agent_tools(self) -> list:
        from plugins.installed.promotions.agent_tools import (
            create_percent_off_tool,
            list_promotions_tool,
        )

        return [list_promotions_tool, create_percent_off_tool]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='index',
                label='Promotions',
                section='marketing',
                icon='ticket',
                view='plugins.installed.promotions.views.promotions_index',
                order=20,
            ),
        ]

    # No settings panel — promotions are operational data, not config.
    # All knobs (priority, channel scope, coupon gate) live on each Promotion row.
