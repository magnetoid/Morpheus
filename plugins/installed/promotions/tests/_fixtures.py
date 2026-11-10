"""Shared setup for the promotions tests: products, a cart, its breakdown."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Product
from plugins.installed.orders.models import Cart, CartItem
from plugins.installed.orders.services import OrderService
from plugins.installed.promotions.models import Promotion, PromotionRule

ADDRESS = {
    'first_name': 'A',
    'last_name': 'B',
    'address_line_1': '1 Street',
    'city': 'Berlin',
    'postal_code': '10115',
    'country': 'DE',
}


def eur(n) -> Money:
    return Money(Decimal(str(n)), 'EUR')


def product(slug, price, **kwargs) -> Product:
    return Product.objects.create(
        name=slug.replace('-', ' ').title(),
        slug=slug,
        sku=slug.upper(),
        price=eur(price),
        status='active',
        **kwargs,
    )


def category(slug, parent=None) -> Category:
    return Category.objects.create(name=slug.title(), slug=slug, parent=parent)


def customer(email='shopper@example.com'):
    return get_user_model().objects.create_user(username=email, email=email, password='x')


def cart(*lines, customer=None, coupon=None) -> Cart:
    """``lines`` = (product, unit_price, quantity) tuples."""
    c = Cart.objects.create(session_key=f'promo-{Cart.objects.count()}', customer=customer)
    for prod, price, qty in lines:
        CartItem.objects.create(cart=c, product=prod, quantity=qty, unit_price=eur(price))
    if coupon is not None:
        c.coupon = coupon
        c.save(update_fields=['coupon'])
    return c


def breakdown(c) -> dict:
    return OrderService.calculate_cart_breakdown(cart=c, address={'country': 'DE'})


def promotion(name, action, predicates=None, **kwargs) -> Promotion:
    from django.utils.text import slugify

    promo = Promotion.objects.create(name=name, slug=slugify(name), **kwargs)
    PromotionRule.objects.create(promotion=promo, action=action, predicates=predicates or {})
    return promo


def applied_names(result) -> list[str]:
    return [p['promotion_name'] for p in result['meta'].get('applied_promotions') or []]
