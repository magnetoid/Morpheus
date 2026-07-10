"""Shared RSS ``g:``-feed field resolver for the ad/commerce channel plugins.

Every catalog channel (Google, Meta, Pinterest, Snapchat, TikTok, Microsoft)
ingests the same product-feed vocabulary: availability, condition, price
``9.00 USD``, ``item_group_id`` for variants, GTIN/MPN identifiers, custom
labels. Before this module each channel plugin carried its own ~200-line
copy of the resolver (~96% identical — the six copies drifted only in the
metafield namespace, logger name, and a handful of channel fields), so every
feed fix had to be made six times.

Channels instantiate :class:`FeedMapper` with their metafield namespace and
bind ``map_product`` / ``expand_variants`` from it; a channel with extra
fields (google_shopping, meta_commerce) subclasses and overrides the
extension points (`availability_in/out`, :meth:`channel_fields`).

This lives at the ``plugins`` package root (like ``plugins/context_processors``)
because it is shared *plugin infrastructure*: putting it in one channel would
couple siblings to that channel; it is not core-worthy because it exists only
for feed channels.
"""

from __future__ import annotations

import contextlib
import logging

from django.utils.html import strip_tags

_GTIN_CODES = ('isbn', 'gtin13', 'gtin12', 'gtin14')
_CUSTOM_LABELS = tuple(f'custom_label_{i}' for i in range(5))


def _abs(url: str) -> str:
    from core.utils.site import site_base_url  # noqa: PLC0415

    if not url:
        return ''
    if url.startswith(('http://', 'https://')):
        return url
    return site_base_url().rstrip('/') + '/' + url.lstrip('/')


class FeedMapper:
    """Product → flat feed-item dict, parameterized by channel."""

    # Channel availability vocabulary (Google uses underscores).
    availability_in = 'in stock'
    availability_out = 'out of stock'

    def __init__(self, namespace: str, *, logger_name: str = ''):
        self.namespace = namespace
        self.logger = logging.getLogger(logger_name or f'morpheus.{namespace}')

    # ── Extension point ─────────────────────────────────────────────────
    def channel_fields(self, item: dict, *, product, over, book, gtin, mpn, settings) -> None:
        """Channel-specific attributes, added after identifiers and before
        custom labels. Default: the per-product google_product_category
        override every channel understands."""
        if over.get('google_product_category'):
            item['google_product_category'] = over['google_product_category']

    # ── Shared internals ────────────────────────────────────────────────
    def _overrides(self, product) -> dict:
        try:
            from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

            raw = Metafield.objects.for_obj(product, ns=self.namespace) or {}
        except Exception:  # noqa: BLE001
            return {}
        return {k.split('.', 1)[-1]: v for k, v in raw.items()}

    def _identifiers(self, product) -> tuple[str, str]:
        try:
            from plugins.installed.metafields.identifiers import (  # noqa: PLC0415
                product_identifiers,
            )

            codes = product_identifiers(product)
        except Exception:  # noqa: BLE001
            return '', ''
        by = {c.get('jsonld'): c.get('value') for c in codes if c.get('value')}
        gtin = ''
        for code in _GTIN_CODES:
            if by.get(code):
                gtin = str(by[code]).replace('-', '').strip()
                break
        return gtin, (str(by['mpn']).strip() if by.get('mpn') else '')

    def _availability_for(self, filter_kwargs: dict, *, include_oos: bool) -> str | None:
        avail = self.availability_in
        try:
            from django.db.models import F, Sum  # noqa: PLC0415

            from plugins.installed.inventory.models import StockLevel  # noqa: PLC0415

            qty = StockLevel.objects.filter(**filter_kwargs).aggregate(
                q=Sum(F('quantity') - F('reserved_quantity'))
            )['q']
            if qty is not None and qty <= 0:
                avail = self.availability_out
        except Exception:  # noqa: BLE001 — no inventory plugin → assume available
            avail = self.availability_in
        if avail == self.availability_out and not include_oos:
            return None
        return avail

    @staticmethod
    def _money(m) -> str:
        """Money → '9.00 USD' (the channels' shared price format)."""
        if m is None:
            return ''
        try:
            return f'{m.amount:.2f} {m.currency}'
        except Exception:  # noqa: BLE001
            return ''

    @staticmethod
    def _primary_image_link(product) -> str:
        img = getattr(product, 'primary_image', None)
        if img is not None and getattr(img, 'image', None):
            with contextlib.suppress(Exception):
                return _abs(img.image.url)
        return ''

    def _price_pair(self, product) -> tuple[str, str]:
        """(price, sale_price) strings; on-sale shows compare_at as regular."""
        base_price = getattr(product, 'display_price', None) or getattr(product, 'price', None)
        if getattr(product, 'is_on_sale', False):
            return self._money(getattr(product, 'compare_at_price', None)), self._money(base_price)
        return self._money(base_price), ''

    # ── Public API ──────────────────────────────────────────────────────
    def map_product(self, product, settings) -> dict | None:
        """Flat ``{attr: value}`` feed item, or None when the product is
        excluded / missing a hard-required attribute (image, price)."""
        over = self._overrides(product)
        if str(over.get('excluded', '')).lower() in ('1', 'true', 'yes'):
            return None

        image_link = self._primary_image_link(product)
        if not image_link:
            return None

        price, sale_price = self._price_pair(product)
        if not price:
            return None

        availability = self._availability_for(
            {'variant__product': product}, include_oos=settings.include_out_of_stock
        )
        if availability is None:
            return None

        book = {}
        try:
            from plugins.installed.book_product.compat import book_attrs  # noqa: PLC0415

            book = book_attrs(product) or {}
        except Exception:  # noqa: BLE001
            book = {}

        gtin, mpn = self._identifiers(product)
        brand = over.get('brand') or settings.default_brand or book.get('publisher') or ''
        condition = over.get('condition') or settings.default_condition or 'new'

        item: dict = {
            'id': (getattr(product, 'sku', '') or str(product.pk)).strip(),
            'title': (product.name or '')[:150],
            'description': strip_tags(getattr(product, 'description', '') or '')[:5000].strip()
            or (product.name or ''),
            'link': _abs(f'/products/{product.slug}/'),
            'image_link': image_link,
            'availability': availability,
            'price': price,
            'condition': condition,
        }
        if sale_price:
            item['sale_price'] = sale_price
        if brand:
            item['brand'] = brand
        if gtin:
            item['gtin'] = gtin
        if mpn:
            item['mpn'] = mpn
        self.channel_fields(
            item, product=product, over=over, book=book, gtin=gtin, mpn=mpn, settings=settings
        )
        for label in _CUSTOM_LABELS:
            if over.get(label):
                item[label] = str(over[label])[:100]
        return item

    def expand_variants(self, product, base_item: dict, settings) -> list[dict] | None:
        """Variable product with ≥2 active variants → one item per variant
        sharing ``item_group_id`` = the product id. None otherwise."""
        if getattr(product, 'product_type', '') != 'variable':
            return None
        try:
            variants = list(product.variants.filter(is_active=True))
        except Exception:  # noqa: BLE001
            return None
        if len(variants) < 2:
            return None

        items: list[dict] = []
        for v in variants:
            vi = dict(base_item)
            vi['item_group_id'] = base_item['id']
            vi['id'] = (getattr(v, 'sku', '') or '').strip() or f'{base_item["id"]}-{v.pk}'

            vprice = getattr(v, 'price', None)
            vcompare = getattr(v, 'compare_at_price', None)
            if vcompare and vprice and vcompare > vprice:
                vi['price'] = self._money(vcompare)
                vi['sale_price'] = self._money(vprice)
            else:
                p = self._money(vprice)
                if p:
                    vi['price'] = p
                vi.pop('sale_price', None)
            if not vi.get('price'):
                continue

            suffix = (getattr(v, 'name', '') or getattr(v, 'size', '') or '').strip()
            if suffix and suffix.lower() not in (base_item.get('title') or '').lower():
                vi['title'] = f'{base_item["title"]} — {suffix}'[:150]

            barcode = (getattr(v, 'barcode', '') or '').replace('-', '').strip()
            if barcode:
                vi['gtin'] = barcode
                # The variant now has a manufacturer identifier — clear any
                # channel flag inherited from an identifier-less base item.
                vi.pop('identifier_exists', None)

            vimg = getattr(v, 'image', None)
            if vimg is not None and getattr(vimg, 'image', None):
                with contextlib.suppress(Exception):
                    vi['image_link'] = _abs(vimg.image.url)

            av = self._availability_for({'variant': v}, include_oos=settings.include_out_of_stock)
            if av is None:
                continue
            vi['availability'] = av
            items.append(vi)

        return items or None
