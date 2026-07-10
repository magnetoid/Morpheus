"""Resolve one Product into Google Shopping feed attributes.

Adapter over the shared channel resolver (`plugins.feed_mapping`) carrying
Google's extra vocabulary: underscored availability (`in_stock`), the
unique-identifier flag (`identifier_exists`), a settings-level default
google_product_category, `product_type` (the store's own genre/category
path — helps Ads bidding by category), `content_language`, and empty
`shipping_weight` for digital goods. Per-product overrides live in the
``google.*`` metafield namespace. `map_product` returns a flat dict, or
None when excluded / missing image+price.
"""

from __future__ import annotations

from plugins.feed_mapping import FeedMapper


def _store_product_type(product, book) -> str:
    try:
        from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

        bp = BookProduct.objects.filter(product=product).first()
        if bp is not None:
            g = bp.genres.first()
            if g is not None:
                return f'Books > {g.name}'
    except Exception:  # noqa: BLE001, S110
        pass
    cat = getattr(product, 'category', None)
    return getattr(cat, 'name', '') or ''


class _GoogleMapper(FeedMapper):
    availability_in = 'in_stock'
    availability_out = 'out_of_stock'

    def channel_fields(self, item, *, product, over, book, gtin, mpn, settings):
        if not (gtin or mpn):
            # No manufacturer identifier (GTIN/MPN). Brand alone doesn't
            # satisfy Google's unique-identifier requirement, so flag it —
            # without this the item is disapproved. (Public-domain editions
            # have no ISBN/GTIN.)
            item['identifier_exists'] = 'no'
        gpc = over.get('google_product_category') or settings.default_google_product_category or ''
        if gpc:
            item['google_product_category'] = gpc

        ptype = over.get('product_type') or _store_product_type(product, book)
        if ptype:
            item['product_type'] = ptype[:750]

        if book.get('language') or settings.language:
            item['content_language'] = book.get('language') or settings.language
        if getattr(product, 'requires_shipping', True) is False:
            item['shipping_weight'] = ''  # digital — no weight


_mapper = _GoogleMapper('google', logger_name='morpheus.google_shopping')

map_product = _mapper.map_product
expand_variants = _mapper.expand_variants
