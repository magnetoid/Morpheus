"""AI-written product text, said in the page's structured data.

When a product's description or short description is marked as written with AI
(``marks.py``), the Product node points through ``subjectOf`` at a CreativeWork
carrying that text and ``digitalSourceType`` = schema.org's
``TrainedAlgorithmicMediaDigitalSource`` (IPTC's term for content a trained model
generated). ``digitalSourceType`` belongs to CreativeWork, so it is never put on
the Product itself. Unmarked text adds nothing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.ai_content')

GENERATED = 'https://schema.org/TrainedAlgorithmicMediaDigitalSource'

# What the page shows of the product's text, in the order the Product node reads it.
_VISIBLE = (('short_description', 'Short description'), ('description', 'Description'))

# Enough to tie the mark to the text without repeating a long page in the head.
_MAX_TEXT = 5000


def on_seo_jsonld_graph(value, page=None, request=None, **kwargs):
    """``SEO_JSONLD_GRAPH`` subscriber: mark the product's AI-written text."""
    try:
        product = _product_node(value)
        obj = getattr(page, 'obj', None)
        if product is None or obj is None or not product.get('@id'):
            return value
        from plugins.installed.ai_content.marks import marks_for

        marked = marks_for(obj)
        if not marked:
            return value
        url = product['@id'].split('#')[0]
        refs = []
        for field, name in _VISIBLE:
            text = _plain(getattr(obj, field, '') or '') if field in marked else ''
            if not text:
                continue
            node_id = f'{url}#ai-{field.replace("_", "-")}'
            value['@graph'].append(
                {
                    '@type': 'CreativeWork',
                    '@id': node_id,
                    'name': name,
                    'text': text[:_MAX_TEXT],
                    'digitalSourceType': GENERATED,
                    'about': {'@id': product['@id']},
                }
            )
            refs.append({'@id': node_id})
        if refs:
            product['subjectOf'] = refs if len(refs) > 1 else refs[0]
    except Exception as e:  # noqa: BLE001 — an enricher must never lose the graph
        logger.warning('ai_content: JSON-LD marking failed: %s', e, exc_info=True)
    return value


def _product_node(graph) -> dict | None:
    if not isinstance(graph, dict) or not isinstance(graph.get('@graph'), list):
        return None
    for node in graph['@graph']:
        if isinstance(node, dict) and 'Product' in str(node.get('@type', '')):
            return node
    return None


def _plain(markup: str) -> str:
    from html import unescape

    from django.utils.html import strip_tags

    return ' '.join(unescape(strip_tags(markup)).split())
