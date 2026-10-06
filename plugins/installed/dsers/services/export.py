"""The two files DSers reads: `import_products` (mapping) and `import_orders`.

Column names and order follow DSers' CSV templates as documented in its help
centre (help.dsers.com → "Place CSV orders", "Import product data via CSV").
The order file is strict: a full country name, no special characters in the
address lines, a phone of digits and `+` only, and the same *Product id* +
*SKU* pair that the mapping file used.
"""

from __future__ import annotations

import csv
import io
import re
import uuid

from django.db import transaction
from django.utils import timezone

from plugins.installed.dsers.services.countries import country_name

__all__ = [
    'ORDER_COLUMNS',
    'PRODUCT_COLUMNS',
    'country_name',
    'eligible_orders',
    'export_orders',
    'export_products',
    'shippable',
]

ORDER_COLUMNS = (
    'Order number',
    'Date',
    'Country',
    'Product id',
    'SKU',
    'Product count',
    'Order memo',
    'Contact person',
    'Mobile no',
    'Email',
    'Address',
    'Address2',
    'Province',
    'City',
    'Zip',
    'RUT',
    'Personal Clearance ID',
    'Passport/Alien registration Card Number',
    'cpf',
    'Turkish ID Number',
    'Passport Number',
)
PRODUCT_COLUMNS = ('Product id', 'SKU', 'Supplier url', 'Supplier SKU')

# Paid orders that have not gone out yet. 'processing' is included because a
# merchant may have moved an order there by hand before exporting.
EXPORTABLE_STATUSES = ('confirmed', 'processing')

_UNSAFE = re.compile(r'[^\w\s,./#-]', re.UNICODE)
_SPACES = re.compile(r'\s+')


def _config() -> dict:
    from plugins.registry import app_registry

    plugin = app_registry.get('dsers')
    return plugin.get_config() if plugin is not None else {}


def shippable(item) -> bool:
    """Does this order line need a parcel? Digital and virtual lines never go to DSers."""
    variant = item.variant
    if variant is not None:
        return bool(variant.requires_shipping)
    product = item.product
    if product is not None:
        return product.product_type != 'digital'
    return True


def eligible_orders() -> list:
    """Paid, confirmed/processing, never exported, with at least one shippable line."""
    from plugins.installed.orders.models import Order

    qs = (
        Order.objects.filter(
            payment_status='paid', status__in=EXPORTABLE_STATUSES, dsers_sync__isnull=True
        )
        .order_by('placed_at')
        .prefetch_related('items__variant', 'items__product')
    )
    return [order for order in qs if any(shippable(i) for i in order.items.all())]


def clean_text(value) -> str:
    """Address text the way DSers wants it: letters, digits, space and ,./#- only."""
    text = _UNSAFE.sub('', str(value or ''))
    return _SPACES.sub(' ', text).strip()


def clean_phone(value) -> str:
    text = str(value or '').strip()
    digits = re.sub(r'\D', '', text)
    return ('+' if text.startswith('+') else '') + digits


def _first(addr: dict, *keys: str) -> str:
    for key in keys:
        if addr.get(key):
            return str(addr[key])
    return ''


def order_rows(order, memo: str) -> list[list[str]]:
    addr = order.shipping_address if isinstance(order.shipping_address, dict) else {}
    contact = f'{addr.get("first_name", "")} {addr.get("last_name", "")}'.strip() or _first(
        addr, 'name', 'full_name'
    )
    base = {
        'Order number': order.order_number,
        'Date': timezone.localtime(order.placed_at).strftime('%Y-%m-%d'),
        'Country': country_name(_first(addr, 'country', 'country_code')),
        'Order memo': memo,
        'Contact person': contact,
        'Mobile no': clean_phone(_first(addr, 'phone', 'mobile')),
        'Email': order.email or '',
        'Address': clean_text(_first(addr, 'address_line1', 'line1', 'address1', 'street')),
        'Address2': clean_text(_first(addr, 'address_line2', 'line2', 'address2')),
        'Province': clean_text(_first(addr, 'state', 'province', 'region')),
        'City': clean_text(_first(addr, 'city')),
        'Zip': _first(addr, 'postal_code', 'zip', 'postcode').strip(),
    }
    rows = []
    for item in order.items.all():
        if not shippable(item):
            continue
        sku = (
            item.sku
            or (item.variant.sku if item.variant_id else '')
            or (item.product.sku if item.product_id else '')
        )
        row = dict(base)
        row['Product id'] = str(item.product_id or '')
        row['SKU'] = sku
        row['Product count'] = str(item.quantity)
        rows.append([row.get(col, '') for col in ORDER_COLUMNS])
    return rows


def export_orders(orders) -> str:
    """Build the `import_orders` CSV for ``orders`` and mark each as exported.

    Marking is what makes the next export skip them; a *confirmed* order also
    moves to *processing* when the merchant's setting says so.
    """
    from plugins.installed.dsers.models import OrderSync

    cfg = _config()
    memo = str(cfg.get('order_memo') or '')
    move = cfg.get('mark_processing_on_export', True)

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\n')
    writer.writerow(ORDER_COLUMNS)
    batch = uuid.uuid4()
    now = timezone.now()
    with transaction.atomic():
        for order in orders:
            rows = order_rows(order, memo)
            if not rows:
                continue
            writer.writerows(rows)
            OrderSync.objects.update_or_create(
                order=order,
                defaults={'status': 'exported', 'batch_id': batch, 'exported_at': now},
            )
            if move and order.status == 'confirmed':
                order.process()
                order.save()
    return buf.getvalue()


def export_products() -> str:
    """The `import_products` mapping file: every supplier link, one row each."""
    from plugins.installed.dsers.models import SupplierLink

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\n')
    writer.writerow(PRODUCT_COLUMNS)
    for link in SupplierLink.objects.select_related('product', 'variant'):
        writer.writerow(
            [str(link.product_id), link.store_sku, link.supplier_url, link.supplier_sku]
        )
    return buf.getvalue()
