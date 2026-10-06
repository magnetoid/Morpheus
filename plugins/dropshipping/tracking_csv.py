"""Read a supplier's tracking export by meaning, not by header spelling.

Only an account holder sees a supplier's exact column names, and they rename
them. So the parser normalises every header (lowercase, alphanumerics only)
and looks for an order-number column and a tracking-number column, plus the
supplier's own order number and the carrier when present.
"""

from __future__ import annotations

import csv
import io
import re

ORDER_KEYS = {
    'ordernumber',
    'orderno',
    'orderid',
    'order',
    'ordername',
    'storeordernumber',
    'storeorderno',
    'storeorderid',
    'shoporderno',
    'shopordernumber',
    'customerordernumber',
    'referencenumber',
    'reference',
}
TRACKING_KEYS = {
    'trackingnumber',
    'trackingno',
    'tracking',
    'trackingcode',
    'trackingid',
    'logisticstrackingnumber',
    'waybillnumber',
}
SUPPLIER_KEYS = {
    'aliexpressordernumber',
    'aliexpressorderno',
    'aliexpressorderid',
    'aliordernumber',
    'aliorderno',
    'aeorderno',
    'supplierordernumber',
    'supplierorderno',
    'supplierorderid',
    'zendroporderid',
    'zendroporderno',
    'zendropordernumber',
    'fulfillmentid',
}
CARRIER_KEYS = {
    'carrier',
    'logistics',
    'logisticscompany',
    'logisticsname',
    'shippingmethod',
    'shippingcarrier',
    'shippingline',
    'courier',
}


class TrackingCsvError(ValueError):
    """The file is not a tracking export we can read."""


def _norm(header: str) -> str:
    return re.sub(r'[^a-z0-9]', '', (header or '').lower())


def parse_tracking_rows(text: str) -> list[dict]:
    """Rows as ``{order_number, tracking, supplier_order_number, carrier}``.

    Raises :class:`TrackingCsvError` when the two mandatory columns are absent.
    Rows without an order number are dropped; everything else is returned as
    read (an empty tracking cell is the caller's decision to report).
    """
    reader = csv.DictReader(io.StringIO(text.lstrip('﻿')))
    headers = reader.fieldnames or []

    def find(keys: set[str]) -> str | None:
        for header in headers:
            if _norm(header) in keys:
                return header
        return None

    order_col, tracking_col = find(ORDER_KEYS), find(TRACKING_KEYS)
    if not order_col or not tracking_col:
        raise TrackingCsvError(
            'Need an order-number column and a tracking-number column; '
            f'found: {", ".join(headers) or "no header row"}.'
        )
    supplier_col, carrier_col = find(SUPPLIER_KEYS), find(CARRIER_KEYS)
    rows = []
    for row in reader:
        number = (row.get(order_col) or '').strip().lstrip('#')
        if not number:
            continue
        rows.append(
            {
                'order_number': number,
                'tracking': (row.get(tracking_col) or '').strip(),
                'supplier_order_number': (row.get(supplier_col) or '').strip()
                if supplier_col
                else '',
                'carrier': (row.get(carrier_col) or '').strip() if carrier_col else '',
            }
        )
    return rows
