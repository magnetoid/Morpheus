"""Render the Google Merchant Center RSS 2.0 product feed.

`build_feed()` walks every active product, maps it (services.mapping), and emits
the `g:`-namespaced XML Google expects. One bad product is skipped + logged,
never allowed to 500 the whole feed. Writes a GoogleSyncLog audit row.
"""

from __future__ import annotations

import logging
from xml.sax.saxutils import escape

from .mapping import expand_variants, map_product
from .settings import feed_settings

logger = logging.getLogger('morpheus.google_shopping')

_G = 'http://base.google.com/ns/1.0'
# Attributes that take the g: namespace (title/description/link are plain RSS).
_PLAIN = {'title', 'description', 'link'}


def _active_products():
    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    return (
        Product.objects.filter(status='active').select_related('category').order_by('-created_at')
    )


def _item_xml(item: dict) -> str:
    parts = ['  <item>']
    for key, value in item.items():
        if value in (None, ''):
            continue
        tag = key if key in _PLAIN else f'g:{key}'
        parts.append(f'    <{tag}>{escape(str(value))}</{tag}>')
    parts.append('  </item>')
    return '\n'.join(parts)


def build_feed(*, log: bool = True) -> tuple[str, dict]:
    """Return (xml_string, stats). stats = {items, skipped, errors}."""
    settings = feed_settings()
    items_xml: list[str] = []
    skipped = 0
    errors: list[str] = []

    for product in _active_products().iterator():
        try:
            item = map_product(product, settings)
        except Exception as e:  # noqa: BLE001 — one product never breaks the feed
            errors.append(f'{getattr(product, "slug", "?")}: {e}')
            logger.warning(
                'google_shopping: map failed for %s: %s', getattr(product, 'slug', '?'), e
            )
            continue
        if item is None:
            skipped += 1
            continue
        # Variable products → one item per active variant (item_group_id);
        # simple products → the single product-level item.
        variant_items = expand_variants(product, item, settings)
        for it in variant_items or [item]:
            items_xml.append(_item_xml(it))

    title = escape(settings.feed_title or 'Product feed')
    desc = escape(settings.feed_description or '')
    from morpheus.core import site_base_url  # noqa: PLC0415

    link = escape(site_base_url())
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<rss version="2.0" xmlns:g="{_G}">\n'
        '<channel>\n'
        f'  <title>{title}</title>\n'
        f'  <link>{link}</link>\n'
        f'  <description>{desc}</description>\n' + '\n'.join(items_xml) + '\n</channel>\n</rss>\n'
    )

    stats = {'items': len(items_xml), 'skipped': skipped, 'errors': errors}
    if log:
        _write_log(stats)
    return xml, stats


def _write_log(stats: dict) -> None:
    try:
        from plugins.installed.google_shopping.models import GoogleSyncLog  # noqa: PLC0415

        status = (
            GoogleSyncLog.STATUS_ERROR
            if stats['errors'] and not stats['items']
            else (GoogleSyncLog.STATUS_PARTIAL if stats['errors'] else GoogleSyncLog.STATUS_OK)
        )
        GoogleSyncLog.objects.create(
            kind=GoogleSyncLog.KIND_FEED,
            status=status,
            item_count=stats['items'],
            skipped_count=stats['skipped'],
            errors=stats['errors'][:50],
            message=f'{stats["items"]} items, {stats["skipped"]} skipped',
        )
    except Exception as e:  # noqa: BLE001 — logging must never break the feed
        logger.debug('google_shopping: sync-log write failed: %s', e)
