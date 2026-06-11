"""
WooCommerce REST API importer.

Maps:
    products  -> catalog.Product
    customers -> customers.Customer
    orders    -> orders.Order
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from django.db import transaction
from djmoney.money import Money

from plugins.installed.importers.base import BaseImporter

logger = logging.getLogger('morpheus.importers.woocommerce')


class _HTTPClient:
    def __init__(self, *, base_url: str, consumer_key: str, consumer_secret: str) -> None:
        self._base = base_url.rstrip('/') + '/wp-json/wc/v3'
        self._auth = (consumer_key, consumer_secret)

    def get(self, path: str, params: dict | None = None) -> list[dict]:
        import requests

        url = f'{self._base}/{path.lstrip("/")}'
        resp = requests.get(url, auth=self._auth, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()


class WooImporter(BaseImporter):
    source = 'woocommerce'

    def __init__(
        self,
        *,
        base_url: str = '',
        consumer_key: str = '',
        consumer_secret: str = '',
        client: Any | None = None,
        records: dict[str, Iterable[dict]] | None = None,
    ) -> None:
        super().__init__()
        self._records = records
        if client is not None:
            self._client = client
        elif base_url and consumer_key and consumer_secret:
            self._client = _HTTPClient(
                base_url=base_url,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
            )
        else:
            self._client = None

    def iter_products(self) -> Iterable[dict]:
        if self._records is not None:
            yield from self._records.get('products', [])
            return
        if self._client is None:
            return
        page = 1
        while True:
            batch = self._client.get('products', params={'per_page': 100, 'page': page})
            if not batch:
                break
            yield from batch
            if len(batch) < 100:
                break
            page += 1

    def iter_customers(self) -> Iterable[dict]:
        if self._records is not None:
            yield from self._records.get('customers', [])
            return
        if self._client is None:
            return
        yield from self._client.get('customers', params={'per_page': 100})

    def iter_orders(self) -> Iterable[dict]:
        if self._records is not None:
            yield from self._records.get('orders', [])
            return
        if self._client is None:
            return
        yield from self._client.get('orders', params={'per_page': 100})

    def _run(self) -> None:
        for r in self.iter_products():
            self._import_product(r)
        for r in self.iter_customers():
            self._import_customer(r)
        for r in self.iter_orders():
            self._import_order(r)

    # ── Mappers ──────────────────────────────────────────────────────────────

    def _import_product(self, record: dict) -> None:
        from django.utils.text import slugify

        from plugins.installed.catalog.models import Product

        source_id = str(record['id'])
        existing_pk = self.find_existing(source_id=source_id, dest_model='Product')
        currency = record.get('currency') or 'USD'
        with transaction.atomic():
            product = None
            if existing_pk:
                product = Product.objects.filter(pk=existing_pk).first()
            seed = record.get('slug') or slugify(record.get('name', f'product-{source_id}'))
            if product is None:
                product = Product.objects.create(
                    name=record.get('name') or f'Product {source_id}',
                    slug=self._unique_slug(seed),
                    sku=record.get('sku') or '',
                    short_description=(record.get('short_description') or '')[:500],
                    description=record.get('description') or '',
                    status='active' if record.get('status') == 'publish' else 'draft',
                    price=Money(record.get('price') or '0.00', currency),
                )
            else:
                product.name = record.get('name') or product.name
                product.short_description = (record.get('short_description') or '')[:500]
                product.description = record.get('description') or ''
                product.price = Money(record.get('price') or '0.00', currency)
                product.status = 'active' if record.get('status') == 'publish' else 'draft'
                product.save()

            self.upsert(source_id=source_id, dest_obj=product)
            self.summary.increment('products')

    def _import_customer(self, record: dict) -> None:
        from plugins.installed.customers.models import Customer

        source_id = str(record['id'])
        email = (record.get('email') or '').lower()
        if not email:
            return
        with transaction.atomic():
            customer, _ = Customer.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': record.get('first_name') or '',
                    'last_name': record.get('last_name') or '',
                },
            )
            self.upsert(source_id=source_id, dest_obj=customer)
            self.summary.increment('customers')

    def _import_order(self, record: dict) -> None:
        from plugins.installed.orders.models import Order

        source_id = str(record['id'])
        if self.find_existing(source_id=source_id, dest_model='Order'):
            self.summary.increment('orders_skipped')
            return
        currency = record.get('currency') or 'USD'
        order = Order.objects.create(
            email=(record.get('billing', {}).get('email') or 'unknown@example.com').lower(),
            status='pending',
            payment_status=record.get('status') or 'unpaid',
            subtotal=Money(record.get('total') or '0.00', currency),
            total=Money(record.get('total') or '0.00', currency),
            shipping_address=record.get('shipping') or {},
            billing_address=record.get('billing') or {},
            source='import',
        )
        self.upsert(source_id=source_id, dest_obj=order)
        self.summary.increment('orders')

    @staticmethod
    def _unique_slug(seed: str) -> str:
        from plugins.installed.catalog.models import Product

        if not Product.objects.filter(slug=seed).exists():
            return seed
        for n in range(2, 1000):
            cand = f'{seed}-{n}'
            if not Product.objects.filter(slug=cand).exists():
                return cand
        raise RuntimeError('Could not allocate unique slug')
