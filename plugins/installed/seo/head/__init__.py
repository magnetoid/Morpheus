"""The SEO app's answer to `STOREFRONT_HEAD`.

Everything a search engine, a social scraper or an answer engine reads out of
`<head>` is assembled here, from the resolved page — not from tags sprinkled
through a theme. That is what makes the head identical on any storefront, and
what lets a headless client ask for the same document as JSON.
"""

from .builder import build_document, on_storefront_head

__all__ = ['build_document', 'on_storefront_head']
