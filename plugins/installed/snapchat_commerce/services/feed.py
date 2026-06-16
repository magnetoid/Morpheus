"""Render the Snapchat catalog feed (RSS 2.0, g: namespace — Snapchat Catalog
Manager ingests this as a data-feed URL)."""

from __future__ import annotations

import logging
from xml.sax.saxutils import escape

from .mapping import expand_variants, map_product
from .settings import snapchat_settings

logger = logging.getLogger('morpheus.snapchat_commerce')

_G = 'http://base.google.com/ns/1.0'
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
    settings = snapchat_settings()
    items_xml: list[str] = []
    skipped = 0
    errors: list[str] = []

    for product in _active_products().iterator():
        try:
            item = map_product(product, settings)
        except Exception as e:  # noqa: BLE001 — one product never breaks the feed
            errors.append(f'{getattr(product, "slug", "?")}: {e}')
            continue
        if item is None:
            skipped += 1
            continue
        for it in expand_variants(product, item, settings) or [item]:
            items_xml.append(_item_xml(it))

    from core.utils.site import site_base_url  # noqa: PLC0415

    title = escape(settings.feed_title or 'Catalog')
    link = escape(site_base_url())
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<rss version="2.0" xmlns:g="{_G}">\n<channel>\n'
        f'  <title>{title}</title>\n  <link>{link}</link>\n'
        '  <description>Snapchat product catalog feed.</description>\n'
        + '\n'.join(items_xml)
        + '\n</channel>\n</rss>\n'
    )
    stats = {'items': len(items_xml), 'skipped': skipped, 'errors': errors}
    if log:
        _write_log(stats)
    return xml, stats


def _write_log(stats: dict) -> None:
    try:
        from plugins.installed.snapchat_commerce.models import SnapchatSyncLog  # noqa: PLC0415

        status = (
            SnapchatSyncLog.STATUS_ERROR
            if stats['errors'] and not stats['items']
            else (SnapchatSyncLog.STATUS_PARTIAL if stats['errors'] else SnapchatSyncLog.STATUS_OK)
        )
        SnapchatSyncLog.objects.create(
            kind=SnapchatSyncLog.KIND_FEED,
            status=status,
            item_count=stats['items'],
            skipped_count=stats['skipped'],
            errors=stats['errors'][:50],
            message=f'{stats["items"]} items, {stats["skipped"]} skipped',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('snapchat_commerce: feed log failed: %s', e)
