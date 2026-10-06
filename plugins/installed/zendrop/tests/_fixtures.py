"""Shared fixtures: a physical product with a variant, and paid orders."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from djmoney.money import Money

ADDRESS = {
    'first_name': 'Mara',
    'last_name': 'Jovanović',
    'address_line1': 'Bulevar Oslobođenja 100 — stan 7!',
    'address_line2': '',
    'city': 'Novi Sad',
    'state': 'Vojvodina',
    'postal_code': '21000',
    'country': 'RS',
    'phone': '+381 (21) 555-123',
}


def staff_user(username='owner'):
    return get_user_model().objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='x',
        is_staff=True,
        is_superuser=True,
    )


def physical_product(slug='lamp'):
    from plugins.installed.catalog.models import Product, ProductVariant

    product = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('29.00'), 'USD'),
        status='active',
    )
    variant = ProductVariant.objects.create(
        product=product, name='Default', sku=f'{slug.upper()}-V', requires_shipping=True
    )
    return product, variant


def paid_order(items, *, status='confirmed', email='mara@example.com'):
    from plugins.installed.orders.models import Order, OrderItem

    order = Order.objects.create(
        email=email,
        subtotal=Money(Decimal('29.00'), 'USD'),
        total=Money(Decimal('29.00'), 'USD'),
        payment_status='paid',
        shipping_address=dict(ADDRESS),
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
    order.save()
    return order


def refetch(order):
    """Order.status is a protected FSM field — refresh_from_db() raises; re-read instead."""
    return type(order).objects.get(pk=order.pk)
