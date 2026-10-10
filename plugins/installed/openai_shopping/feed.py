"""Rows in OpenAI's product feed specification, from the shared channel resolver."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, fields
from typing import Any

logger = logging.getLogger('morpheus.openai_shopping')

_FEED_LIMIT = 5000


@dataclass(frozen=True)
class FeedConfig:
    """The settings panel's values. The three channel-resolver fields
    (``default_brand``, ``default_condition``, ``include_out_of_stock``) are
    read by :class:`plugins.feed_mapping.FeedMapper`."""

    enabled: bool = True
    seller_name: str = ''
    store_country: str = ''
    target_countries: str = ''
    seller_privacy_policy: str = ''
    seller_tos: str = ''
    checkout_eligible: bool = False
    accepts_returns: bool = True
    return_deadline_days: int = 30
    return_policy_url: str = ''
    default_brand: str = ''
    default_condition: str = 'new'
    include_out_of_stock: bool = True
    push_endpoint: str = ''
    push_token: str = ''


def config() -> FeedConfig:
    """The panel's values, read fresh (a plugin config cache is per-process)."""
    values: dict[str, Any] = {}
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('openai_shopping')
        if plugin is not None:
            for f in fields(FeedConfig):
                raw = plugin.get_config_value(f.name, None)
                if raw is not None and raw != '':
                    values[f.name] = raw
    except Exception:  # noqa: BLE001 — defaults are a valid feed
        logger.debug('openai_shopping: config read failed', exc_info=True)
    try:
        values['return_deadline_days'] = int(values.get('return_deadline_days', 30))
    except (TypeError, ValueError):
        values['return_deadline_days'] = 30
    return FeedConfig(**values)


def _seller(cfg: FeedConfig, base: str) -> dict[str, str]:
    from core.utils.countries import store_country
    from core.utils.site import store_name

    country = (cfg.store_country or store_country() or '').upper()
    targets = [c.strip().upper() for c in cfg.target_countries.split(',') if c.strip()] or (
        [country] if country else []
    )
    return {
        'seller_name': cfg.seller_name or store_name(),
        'seller_url': f'{base}/',
        'seller_privacy_policy': cfg.seller_privacy_policy or f'{base}/p/privacy/',
        'seller_tos': cfg.seller_tos or f'{base}/p/terms/',
        'store_country': country,
        'target_countries': ','.join(targets),
        'return_policy': cfg.return_policy_url or f'{base}/returns/',
    }


def _row(item: dict, *, cfg: FeedConfig, seller: dict, group: dict | None = None) -> dict[str, Any]:
    """One feed row from a shared-resolver feed-attr dict."""
    row: dict[str, Any] = {
        'item_id': item.get('id', ''),
        'title': item.get('title', ''),
        'description': item.get('description', '') or item.get('title', ''),
        'url': item.get('link', ''),
        'brand': item.get('brand', '') or seller['seller_name'],
        'image_url': item.get('image_link', ''),
        'availability': str(item.get('availability') or 'in_stock'),
        'price': item.get('price', ''),
        'seller_name': seller['seller_name'],
        'seller_url': seller['seller_url'],
        'store_country': seller['store_country'],
        'target_countries': seller['target_countries'],
        'is_eligible_search': True,
        'is_eligible_checkout': bool(cfg.checkout_eligible),
        'accepts_returns': bool(cfg.accepts_returns),
    }
    if item.get('sale_price'):
        row['sale_price'] = item['sale_price']
    if cfg.checkout_eligible:
        row['seller_privacy_policy'] = seller['seller_privacy_policy']
        row['seller_tos'] = seller['seller_tos']
    if cfg.accepts_returns:
        row['return_deadline_in_days'] = int(cfg.return_deadline_days)
        row['return_policy'] = seller['return_policy']
    for src, dst in (
        ('gtin', 'gtin'),
        ('mpn', 'mpn'),
        ('condition', 'condition'),
        ('google_product_category', 'product_category'),
    ):
        if item.get(src):
            row[dst] = str(item[src])
    if group is not None:
        row['group_id'] = group['id']
        row['listing_has_variations'] = True
        row['variant_dict'] = group['variant_dict']
    return row


def _variant_name(row: dict, base: dict) -> str:
    """The resolver titles a variant ``<product> — <variant>``; keep the tail."""
    title, base_title = row.get('title') or '', base.get('title') or ''
    if title.startswith(base_title) and ' — ' in title:
        return title.rsplit(' — ', 1)[-1].strip()
    return row.get('id', '')


def build_rows() -> list[dict[str, Any]]:
    """Every active product the shared resolver accepts, as feed rows."""
    cfg = config()
    if not cfg.enabled:
        return []
    from core.utils.site import site_base_url
    from plugins.installed.catalog.models import Product
    from plugins.installed.openai_shopping.mapping import expand_variants, map_product

    base = site_base_url().rstrip('/')
    seller = _seller(cfg, base)
    rows: list[dict[str, Any]] = []
    products = Product.objects.filter(status='active').order_by('-created_at')[:_FEED_LIMIT]
    for product in products:
        try:
            item = map_product(product, cfg)
        except Exception as e:  # noqa: BLE001 — one product never breaks the feed
            logger.warning('openai_shopping: map failed for %s: %s', product.slug, e)
            continue
        if item is None:
            continue
        variants = expand_variants(product, item, cfg)
        if variants:
            for v in variants:
                group = {'id': item['id'], 'variant_dict': {'variant': _variant_name(v, item)}}
                rows.append(_row(v, cfg=cfg, seller=seller, group=group))
        else:
            rows.append(_row(item, cfg=cfg, seller=seller))
    return rows


def render_jsonl(rows: list[dict[str, Any]]) -> str:
    return ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)


def coverage() -> dict[str, Any]:
    """Counts for the dashboard page and the Channels overview."""
    from plugins.installed.catalog.models import Product

    cfg = config()
    rows = build_rows()
    active = Product.objects.filter(status='active').count()
    products = {r.get('group_id') or r['item_id'] for r in rows}
    return {
        'active': active,
        'in_feed': len(products),
        'rows': len(rows),
        'checkout_eligible': sum(1 for r in rows if r.get('is_eligible_checkout')),
        'coverage_pct': round(100 * len(products) / active, 1) if active else 0.0,
        'push_configured': bool(cfg.push_endpoint and cfg.push_token),
    }
