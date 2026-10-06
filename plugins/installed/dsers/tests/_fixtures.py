"""Shared fixtures: a physical product, a digital one, and orders in each state."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from djmoney.money import Money

ADDRESS = {
    'first_name': 'Jelena',
    'last_name': 'Petrović',
    'address_line1': 'Ul. Kralja Petra 12/3 — stan 5!',
    'address_line2': '',
    'city': 'Beograd',
    'state': 'Central Serbia',
    'postal_code': '11000',
    'country': 'RS',
    'phone': '+381 (64) 123-456',
}


def staff_user(username='owner'):
    return get_user_model().objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='x',
        is_staff=True,
        is_superuser=True,
    )


def physical_product(slug='candle', **kwargs):
    from plugins.installed.catalog.models import Product, ProductVariant

    product = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('19.00'), 'USD'),
        status='active',
        **kwargs,
    )
    variant = ProductVariant.objects.create(
        product=product, name='Default', sku=f'{slug.upper()}-V', requires_shipping=True
    )
    return product, variant


def digital_product(slug='ebook'):
    from plugins.installed.catalog.models import Product, ProductVariant

    product = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('9.00'), 'USD'),
        status='active',
        product_type='digital',
    )
    variant = ProductVariant.objects.create(
        product=product, name='PDF', sku=f'{slug.upper()}-PDF', requires_shipping=False
    )
    return product, variant


def paid_order(items, *, email='jelena@example.com', address=None, status='confirmed'):
    """A paid order holding ``items`` = [(product, variant, qty)], in ``status``."""
    from plugins.installed.orders.models import Order, OrderItem

    order = Order.objects.create(
        email=email,
        subtotal=Money(Decimal('19.00'), 'USD'),
        total=Money(Decimal('19.00'), 'USD'),
        payment_status='paid',
        shipping_address=dict(address or ADDRESS),
    )
    for product, variant, qty in items:
        OrderItem.objects.create(
            order=order,
            product=product,
            variant=variant,
            product_name=product.name,
            variant_name=variant.name if variant else '',
            sku=variant.sku if variant else product.sku,
            quantity=qty,
            unit_price=product.price,
            total_price=Money(product.price.amount * qty, 'USD'),
        )
    if status in ('confirmed', 'processing'):
        order.confirm()
    if status == 'processing':
        order.process()
    if status == 'cancelled':
        order.cancel()
    order.save()
    return order
