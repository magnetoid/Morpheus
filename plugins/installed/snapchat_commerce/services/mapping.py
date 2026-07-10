"""Resolve one Product into Snapchat catalog feed attributes.

Thin adapter over the shared channel resolver (`plugins.feed_mapping`):
Snapchat ingests the standard RSS g: feed (availability `in stock`/`out of
stock`, condition `new`, price `9.00 USD`, item_group_id for variants) with
per-product `snapchat.*` metafield overrides. `map_product` returns a flat dict,
or None when excluded / missing image+price.
"""

from __future__ import annotations

from plugins.feed_mapping import FeedMapper

_mapper = FeedMapper('snapchat', logger_name='morpheus.snapchat_commerce')

map_product = _mapper.map_product
expand_variants = _mapper.expand_variants
