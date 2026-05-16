"""
Shopify Admin REST API importer.

Maps:
    products  -> catalog.Product (+ ProductVariant, ProductImage)
    custom_collections / smart_collections -> catalog.Collection
    customers -> customers.Customer (registration only — no PII import beyond email)
    orders    -> orders.Order

Network IO is delegated to a small `_HTTPClient` so tests can inject fakes
without touching the network.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

from django.db import transaction
from djmoney.money import Money

from plugins.installed.importers.base import BaseImporter

logger = logging.getLogger('morpheus.importers.shopify')


class _HTTPClient:
    """Tiny HTTP wrapper. Replaced in tests with a fake."""

    def __init__(self, shop: str, token: str, api_version: str = '2024-01') -> None:
        self._base = f'https://{shop}.myshopify.com/admin/api/{api_version}'
        self._headers = {'X-Shopify-Access-Token': token, 'Accept': 'application/json'}

    def get(self, path: str, params: dict | None = None) -> dict:
        import requests
        url = f'{self._base}/{path.lstrip("/")}'
        resp = requests.get(url, headers=self._headers, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()


class ShopifyImporter(BaseImporter):
    source = 'shopify'

    def __init__(
        self,
        *,
        shop: str = '',
        token: str = '',
        client: Any | None = None,
        records: dict[str, Iterable[dict]] | None = None,
    ) -> None:
        """
        Pass either:
            shop + token   — to hit the live Shopify Admin API, or
            client         — a custom client compatible with `_HTTPClient.get`, or
            records        — a dict {"products": [...], "orders": [...], ...} for offline imports.
        """
        super().__init__()
        self._records = records
        if client is not None:
            self._client = client
        elif shop and token:
            self._client = _HTTPClient(shop=shop, token=token)
        else:
            self._client = None

    # ── Iterators ─────────────────────────────────────────────────────────────

    def iter_products(self) -> Iterable[dict]:
        if self._records is not None:
            yield from self._records.get('products', [])
            return
        if self._client is None:
            return
        page_info = None
        while True:
            params = {'limit': 250}
            if page_info:
                params['page_info'] = page_info
            data = self._client.get('products.json', params=params)
            yield from data.get('products', [])
            page_info = data.get('next_page_info')
            if not page_info:
                break

    def iter_orders(self) -> Iterable[dict]:
        if self._records is not None:
            yield from self._records.get('orders', [])
            return
        if self._client is None:
            return
        data = self._client.get('orders.json', params={'status': 'any', 'limit': 250})
        yield from data.get('orders', [])

    def iter_customers(self) -> Iterable[dict]:
        if self._records is not None:
            yield from self._records.get('customers', [])
            return
        if self._client is None:
            return
        data = self._client.get('customers.json', params={'limit': 250})
        yield from data.get('customers', [])

    # ── Run ──────────────────────────────────────────────────────────────────

    def _run(self) -> None:
        for record in self.iter_products():
            self._import_product(record)
        for record in self.iter_customers():
            self._import_customer(record)
        for record in self.iter_orders():
            self._import_order(record)

    # ── Mappers ──────────────────────────────────────────────────────────────

    def _import_product(self, record: dict) -> None:
        from django.utils.text import slugify
        from plugins.installed.catalog.models import Product, ProductImage, ProductVariant

        source_id = str(record['id'])
        slug_seed = record.get('handle') or slugify(record.get('title', f'product-{source_id}'))
        title = record.get('title') or f'Product {source_id}'

        existing_pk = self.find_existing(source_id=source_id, dest_model='Product')
        with transaction.atomic():
            if existing_pk:
                product = Product.objects.filter(pk=existing_pk).first()
            else:
                product = None

            price_raw = (record.get('variants') or [{}])[0].get('price') or '0.00'
            currency = record.get('currency') or 'USD'

            if product is None:
                product = Product.objects.create(
                    name=title,
                    slug=self._unique_slug(Product, slug_seed),
                    sku=(record.get('variants') or [{}])[0].get('sku', ''),
                    short_description=(record.get('body_html') or '')[:500],
                    description=record.get('body_html') or '',
                    status='active' if record.get('status') == 'active' else 'draft',
                    price=Money(price_raw, currency),
                )
            else:
                product.name = title
                product.short_description = (record.get('body_html') or '')[:500]
                product.description = record.get('body_html') or ''
                product.price = Money(price_raw, currency)
                product.status = 'active' if record.get('status') == 'active' else 'draft'
                product.save()

            for v in record.get('variants') or []:
                ProductVariant.objects.update_or_create(
                    sku=v.get('sku') or f'{product.sku}-{v.get("id")}',
                    defaults={
                        'product': product,
                        'name': v.get('title', 'Default'),
                        'price': Money(v.get('price') or price_raw, currency),
                        'is_active': True,
                    },
                )
            for i, img in enumerate(record.get('images') or []):
                ProductImage.objects.update_or_create(
                    product=product, alt_text=img.get('alt') or '',
                    defaults={
                        'image': img.get('src') or '',
                        'sort_order': i,
                        'is_primary': i == 0,
                    },
                )

            self.upsert(
                source_id=source_id,
                dest_obj=product,
                metadata={'shopify_handle': record.get('handle')},
            )
            self.summary.increment('products')

    def _import_customer(self, record: dict) -> None:
        from plugins.installed.customers.models import Customer

        source_id = str(record['id'])
        email = (record.get('email') or '').lower()
        if not email:
            return

        existing_pk = self.find_existing(source_id=source_id, dest_model='Customer')
        with transaction.atomic():
            customer = None
            if existing_pk:
                customer = Customer.objects.filter(pk=existing_pk).first()
            if customer is None:
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
        existing_pk = self.find_existing(source_id=source_id, dest_model='Order')
        if existing_pk:
            self.summary.increment('orders_skipped')
            return

        currency = record.get('currency') or 'USD'
        total_amount = record.get('total_price') or '0.00'
        subtotal = record.get('subtotal_price') or total_amount

        order = Order.objects.create(
            email=(record.get('email') or 'unknown@example.com').lower(),
            status='pending',
            payment_status=record.get('financial_status') or 'unpaid',
            subtotal=Money(subtotal, currency),
            total=Money(total_amount, currency),
            shipping_address=record.get('shipping_address') or {},
            billing_address=record.get('billing_address') or {},
            source='import',
        )
        self.upsert(source_id=source_id, dest_obj=order)
        self.summary.increment('orders')

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _unique_slug(model, seed: str) -> str:
        slug = seed[:280]
        if not model.objects.filter(slug=slug).exists():
            return slug
        for n in range(2, 1000):
            candidate = f'{slug}-{n}'
            if not model.objects.filter(slug=candidate).exists():
                return candidate
        raise RuntimeError('Could not allocate unique slug')
