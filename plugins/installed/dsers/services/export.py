"""The two files DSers reads: `import_products` (mapping) and `import_orders`.

Column names and order follow DSers' CSV templates as documented in its help
centre (help.dsers.com → "Place CSV orders", "Import product data via CSV").
The order file is strict: a full country name, no special characters in the
address lines, a phone of digits and `+` only, and the same *Product id* +
*SKU* pair that the mapping file used. The address and eligibility rules are
the shared supplier machinery in ``plugins.dropshipping``.
"""

from __future__ import annotations

import csv
import io
import uuid

from django.db import transaction
from django.utils import timezone

from plugins.dropshipping import (
    clean_phone,
    clean_text,
    country_name,
    normalised_address,
    shippable,
)
from plugins.dropshipping import (
    eligible_orders as _eligible_orders,
)

__all__ = [
    'ORDER_COLUMNS',
    'PRODUCT_COLUMNS',
    'clean_phone',
    'clean_text',
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


def _config() -> dict:
    from plugins.registry import app_registry

    plugin = app_registry.get('dsers')
    return plugin.get_config() if plugin is not None else {}


def eligible_orders() -> list:
    """Paid, confirmed/processing, never exported, with at least one shippable line."""
    return _eligible_orders('dsers_sync')


def order_rows(order, memo: str) -> list[list[str]]:
    addr = normalised_address(order)
    base = {
        'Order number': order.order_number,
        'Date': timezone.localtime(order.placed_at).strftime('%Y-%m-%d'),
        'Country': addr['country'],
        'Order memo': memo,
        'Contact person': addr['contact'],
        'Mobile no': addr['phone'],
        'Email': addr['email'],
        'Address': addr['line1'],
        'Address2': addr['line2'],
        'Province': addr['province'],
        'City': addr['city'],
        'Zip': addr['zip'],
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
