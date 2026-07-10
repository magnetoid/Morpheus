"""Resolve one Product into Meta catalog feed attributes.

Thin adapter over the shared channel resolver (`plugins.feed_mapping`) with
Meta's one extra attribute: a per-product `meta.fb_product_category`
override. `map_product` returns a flat dict, or None when excluded /
missing image+price.
"""

from __future__ import annotations

from plugins.feed_mapping import FeedMapper


class _MetaMapper(FeedMapper):
    def channel_fields(self, item, *, over, **kwargs):
        super().channel_fields(item, over=over, **kwargs)
        if over.get('fb_product_category'):
            item['fb_product_category'] = over['fb_product_category']


_mapper = _MetaMapper('meta', logger_name='morpheus.meta_commerce')

map_product = _mapper.map_product
expand_variants = _mapper.expand_variants
