"""Shared machinery for the dropshipping supplier apps (dsers, zendrop, …).

Every supplier integration does the same four things with the platform's own
models: pick the paid, shippable orders that have not gone to the supplier
yet; present a shipping address the supplier will accept; read a tracking file
back by meaning rather than by header spelling; and ship the order the
platform way — ``Order.ship()`` plus an ``orders.Fulfillment`` row, so the
shopper's "on its way" email and every subscriber fire exactly once.

This lives at the ``plugins`` package root (like ``plugins/feed_mapping.py`` for
the channel apps) because it is shared *plugin infrastructure*: putting it in
one supplier app would couple its siblings to that app, and it is not
core-worthy because it exists only for supplier apps. Each app keeps its own
models and its supplier-specific file formats.
"""

from __future__ import annotations

from plugins.dropshipping.addresses import clean_phone, clean_text, normalised_address
from plugins.dropshipping.countries import COUNTRIES, country_name
from plugins.dropshipping.orders import (
    DEFAULT_TRACKING_URL,
    EXPORTABLE_STATUSES,
    eligible_orders,
    ship_with_tracking,
    shippable,
    tracking_url,
)
from plugins.dropshipping.tracking_csv import TrackingCsvError, parse_tracking_rows

__all__ = [
    'COUNTRIES',
    'DEFAULT_TRACKING_URL',
    'EXPORTABLE_STATUSES',
    'TrackingCsvError',
    'clean_phone',
    'clean_text',
    'country_name',
    'eligible_orders',
    'normalised_address',
    'parse_tracking_rows',
    'ship_with_tracking',
    'shippable',
    'tracking_url',
]
