"""One JSON-LD `@graph` per page.

Before this, a product page emitted five separate `<script type="application/
ld+json">` blocks (Product, Breadcrumb, Book, Video, speakable) plus two
site-wide ones from the theme's base template — with the WebSite node
duplicated, no `@id` anywhere, and no way for another app to add a property to
a node it owns the data for.

Now there is one document with stable `@id`s, and apps enrich it through
`SEO_JSONLD_GRAPH`: the reviews app adds `aggregateRating`, product_videos adds
a `VideoObject`, returns_portal adds the return policy. Google reads a graph
exactly as it reads separate blocks, but a graph can be reasoned about — which
is what the validator, the merchant-listing readiness score and the inspector
all need.
"""

from .graph import build_graph, graph_for_object

__all__ = ['build_graph', 'graph_for_object']
