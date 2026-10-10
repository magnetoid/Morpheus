"""Resolve one Product into the shared channel feed attributes, OpenAI flavour.

Thin adapter over the shared channel resolver (`plugins.feed_mapping`), like
tiktok_commerce's: the same image/price/identifier/availability rules every
channel feed uses, per-product overrides in the ``openai.*`` metafield
namespace, and OpenAI's underscored availability vocabulary (``in_stock`` /
``out_of_stock``). ``feed.py`` reshapes the resulting ``g:``-style dict into
OpenAI's row names.
"""

from __future__ import annotations

from plugins.feed_mapping import FeedMapper


class _OpenAIMapper(FeedMapper):
    availability_in = 'in_stock'
    availability_out = 'out_of_stock'


_mapper = _OpenAIMapper('openai', logger_name='morpheus.openai_shopping')

map_product = _mapper.map_product
expand_variants = _mapper.expand_variants
