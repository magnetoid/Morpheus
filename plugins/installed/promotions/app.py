"""Promotions plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import DashboardCard, DashboardPage, Plugin

logger = logging.getLogger('morpheus.promotions')


def _units_of(lines, variant_id) -> int:
    """How many units of ``variant_id`` the cart's own lines hold."""
    total = 0
    for it in lines:
        get = it.get if isinstance(it, dict) else lambda k, it=it: getattr(it, k, None)
        if str(get('variant_id') or '') == str(variant_id):
            total += int(get('quantity') or 0)
    return total


class PromotionsPlugin(Plugin):
    name = 'promotions'
    label = 'Promotions'
    version = '1.0.0'
    description = (
        'Rule-based promotion engine: stack predicates (cart total, channel, '
        'country, customer group, product, category, first order) with actions '
        '(% off, fixed off, free shipping, free gift, buy X get Y, tiered). '
        'Channel-scoped, time-bounded, combinable or exclusive, audit-logged.'
    )
    has_models = True
    requires = ['orders', 'catalog']

    def ready(self) -> None:
        from morpheus.core import events

        self.register_hook(events.DASHBOARD_SEARCH, self.on_dashboard_search)

        # CART_CALCULATE_TOTAL is deprecated — the canonical event is
        # CART_CALCULATE_BREAKDOWN, fired from OrderService since 2026-04.
        self.register_hook(events.CART_CALCULATE_BREAKDOWN, self.on_cart_breakdown, priority=10)
        self.register_urls(
            'plugins.installed.promotions.urls',
            prefix='dashboard/promotions/',
            namespace='promotions',
        )

    def on_dashboard_search(self, value, query='', words=None, **kwargs):
        """Promotions (by name, slug or description) in the dashboard's search box."""
        from plugins import dashboard_search as ds
        from plugins.installed.promotions.models import Promotion

        return ds.add(
            value,
            Promotion,
            query,
            words,
            fields=('name', 'slug', 'description'),
            section='Promotions',
            kind='promotion',
            icon='percent',
            capability='marketing.write',
            label=lambda p: p.name,
            hint=lambda p: 'Promotion' if p.is_active else 'Promotion · off',
            url=lambda p: f'/dashboard/promotions/{p.pk}/',
        )

    def on_cart_breakdown(  # noqa: PLR0912, PLR0915
        self,
        value,
        cart=None,
        channel=None,
        customer=None,
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

        # The shopper's code first: a promotion that doesn't combine steps
        # aside when a code applies.
        coupon_discount, coupon_free_shipping = Decimal('0'), False
        try:
            coupon_discount, coupon_free_shipping = self._coupon(cart, subtotal, customer, meta)
        except Exception as e:  # noqa: BLE001
            logger.warning('promotions: coupon evaluation failed: %s', e, exc_info=True)
        free_shipping = free_shipping or coupon_free_shipping

        try:
            from plugins.installed.promotions.services import _cart_lines, evaluate

            country = (address or {}).get('country', '') if address else ''
            applied = evaluate(
                cart,
                channel=channel,
                customer=customer,
                country=country,
                coupon=coupon,
                coupon_applied=bool(coupon_discount > 0 or coupon_free_shipping),
            )
            for a in applied:
                if a.free_shipping:
                    free_shipping = True
                if a.discount_amount:
                    discount_total += Decimal(str(a.discount_amount))
                gift = self._gift_line(a, _cart_lines(cart)) if a.gift_product_id else None
                if gift:
                    meta.setdefault('gift_lines', []).append(gift)
                meta['applied_promotions'].append(
                    {
                        'promotion_id': a.promotion_id,
                        'promotion_name': a.promotion_name,
                        'rule_id': a.rule_id,
                        'discount_amount': str(a.discount_amount),
                        'free_shipping': bool(a.free_shipping),
                        'gift_product_id': a.gift_product_id if gift else None,
                        'note': a.note,
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.warning('promotions: evaluate failed: %s', e, exc_info=True)

        if free_shipping:
            meta['free_shipping'] = True

        discount_total += coupon_discount
        discount_total = min(discount_total, Decimal(str(subtotal.amount)))

        # NB: gift-card tender is NOT applied here. It's a tender, not a
        # discount, and must cap against the FINAL total — so it rides its own
        # gift_cards.on_cart_breakdown handler at priority 50, after tax and
        # shipping. (It used to live here at priority 10 and under-applied
        # by tax+shipping; deep-debug #7.)
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
            logger.warning('Suppressed exception', exc_info=True)

        return value

    @staticmethod
    def _coupon(cart, subtotal, customer, meta):
        """The cart's coupon: ``(discount, free_shipping)``, recorded in
        ``meta['coupon']`` when it applies. Percent and fixed amounts apply to
        the lines inside the coupon's scope only (``marketing/scope.py``)."""
        from decimal import Decimal

        if not getattr(cart, 'coupon_id', None):
            return Decimal('0'), False
        c = cart.coupon
        if c is None or not c.is_valid:
            return Decimal('0'), False
        if c.minimum_order_amount and Decimal(str(subtotal.amount)) < Decimal(
            str(c.minimum_order_amount.amount)
        ):
            return Decimal('0'), False
        if c.usage_limit_per_customer and customer is not None:
            from plugins.installed.marketing.models import CouponUsage

            used = CouponUsage.objects.filter(coupon=c, customer=customer).count()
            if used >= int(c.usage_limit_per_customer):
                return Decimal('0'), False

        from plugins.installed.marketing.scope import eligible_items, line_total
        from plugins.installed.promotions.services import buy_x_get_y_discount

        lines = eligible_items(c, cart.items.select_related('product', 'variant').all())
        if not lines:
            return Decimal('0'), False
        base = line_total(lines)
        discount, free_shipping = Decimal('0'), False
        if c.discount_type == 'percentage':
            discount = base * Decimal(str(c.discount_value)) / Decimal('100')
        elif c.discount_type == 'fixed_amount':
            discount = min(Decimal(str(c.discount_value)), base)
        elif c.discount_type == 'buy_x_get_y':
            discount = buy_x_get_y_discount(
                lines, buy_qty=c.buy_quantity, free_qty=c.get_quantity, percent=c.discount_value
            )
        elif c.discount_type == 'free_shipping':
            free_shipping = True
        discount = discount.quantize(Decimal('0.01'))
        if c.maximum_discount_amount and discount:
            discount = min(discount, Decimal(str(c.maximum_discount_amount.amount)))
        if discount > 0 or free_shipping:
            meta['coupon'] = {
                'code': c.code,
                'discount_amount': str(discount),
                'free_shipping': free_shipping,
            }
        return discount, free_shipping

    @staticmethod
    def _gift_line(applied, lines):
        """The free line a gift rule adds, or None when it cannot be given.

        A gift must never stop a checkout: the order's stock reservation would
        refuse the whole order. So there is no gift when the product is not on
        sale; when it has several active variants and the rule names none (a
        line without a variant reserves no stock and tells nobody what to ship);
        or when the stock app says the variant cannot cover the cart's own
        units of it plus the gift."""
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.catalog.models import Product

        product = Product.objects.shoppable().filter(pk=applied.gift_product_id).first()
        if product is None:
            return None
        variants = list(product.variants.filter(is_active=True))
        if applied.gift_variant_id:
            variant = next((v for v in variants if str(v.pk) == str(applied.gift_variant_id)), None)
            if variant is None:
                return None
        elif len(variants) > 1:
            return None
        else:
            variant = variants[0] if variants else None
        if variant is None:
            stock = hook_registry.filter(
                MorpheusEvents.PRODUCT_STOCK_SUMMARY, value={}, product_ids=[product.pk]
            )
            if ((stock or {}).get(str(product.pk)) or {}).get('out'):
                return None
        else:
            stock = hook_registry.filter(
                MorpheusEvents.VARIANT_STOCK_SUMMARY, value={}, variant_ids=[variant.pk]
            )
            available = (stock or {}).get(str(variant.pk))
            if available is not None and int(available) < _units_of(lines, variant.pk) + 1:
                return None
        return {
            'product_id': str(product.pk),
            'variant_id': str(variant.pk) if variant else '',
            'name': product.name,
            'quantity': 1,
            'promotion_id': applied.promotion_id,
            'promotion_name': applied.promotion_name,
        }

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

            logging.getLogger('morpheus.promotions').warning('Suppressed exception', exc_info=True)
            return value
        except Exception as e:  # noqa: BLE001
            logger.warning('promotions: on_cart_total failed: %s', e, exc_info=True)
            return value

    def contribute_agent_tools(self) -> list:
        from plugins.installed.promotions.agent_tools import (
            create_percent_off_tool,
            create_promotion_tool,
            list_promotions_tool,
            update_promotion_tool,
        )

        return [
            list_promotions_tool,
            create_percent_off_tool,
            create_promotion_tool,
            update_promotion_tool,
        ]

    def contribute_dashboard_cards(self) -> list:
        # A card on the Marketing landing, beside other apps' cards.
        return [
            DashboardCard(
                section='marketing',
                title='Promotions',
                data='plugins.installed.promotions.cards.promotions_card',
                url='/dashboard/apps/promotions/index/',
                cta='Manage promotions',
                icon='percent',
                order=20,
                capability='marketing.read',
            )
        ]

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
