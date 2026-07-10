"""Resolve one Product into TikTok catalog feed attributes.

Thin adapter over the shared channel resolver (`plugins.feed_mapping`):
TikTok ingests the standard RSS g: feed (availability `in stock`/`out of
stock`, condition `new`, price `9.00 USD`, item_group_id for variants) with
per-product `tiktok.*` metafield overrides. `map_product` returns a flat dict,
or None when excluded / missing image+price.
"""

from __future__ import annotations

from plugins.feed_mapping import FeedMapper

_mapper = FeedMapper('tiktok', logger_name='morpheus.tiktok_commerce')

map_product = _mapper.map_product
expand_variants = _mapper.expand_variants
