"""The product's manufacturer, said in the page's structured data.

schema.org's Product has a ``manufacturer`` (an Organization); the page names the one
it shows shoppers (``safety.effective``). Nothing is added when the page shows none,
and a manufacturer another app already set is kept. The EU responsible person and the
warnings have no schema.org property, so only the page shows them.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.product_safety')


def on_seo_jsonld_graph(value, page=None, request=None, **kwargs):
    """``SEO_JSONLD_GRAPH`` subscriber: the Product node's ``manufacturer``."""
    try:
        product = _product_node(value)
        obj = getattr(page, 'obj', None)
        if product is None or obj is None or 'manufacturer' in product:
            return value
        from plugins.installed.catalog.models import Product
        from plugins.installed.product_safety.safety import effective

        if not isinstance(obj, Product):
            return value
        maker = effective(obj)['manufacturer']
        if not maker or not maker['name']:
            return value
        node = {'@type': 'Organization', 'name': maker['name']}
        if maker['address']:
            node['address'] = ', '.join(
                line.strip() for line in maker['address'].splitlines() if line.strip()
            )
        if maker['href'].startswith('mailto:'):
            node['email'] = maker['contact']
        elif maker['href']:
            node['url'] = maker['href']
        product['manufacturer'] = node
    except Exception as e:  # noqa: BLE001 — an enricher must never lose the graph
        logger.warning('product_safety: JSON-LD manufacturer failed: %s', e, exc_info=True)
    return value


def _product_node(graph) -> dict | None:
    if not isinstance(graph, dict) or not isinstance(graph.get('@graph'), list):
        return None
    for node in graph['@graph']:
        if isinstance(node, dict) and 'Product' in str(node.get('@type', '')):
            return node
    return None
