"""AI-written text, said in the page's structured data.

When the text a page shows is marked as written with AI, the node the page is
about points through ``subjectOf`` at a CreativeWork per field, carrying that text
and ``digitalSourceType`` = schema.org's ``TrainedAlgorithmicMediaDigitalSource``
(IPTC's term for content a trained model generated). Two marks count: a product's
description or short description an AI wrote (``marks.py``), and any field a page
shows in a translation that began as an AI draft
(``core.i18n.services.ai_translated``), on a product page or any other page about
one object. ``digitalSourceType`` belongs to CreativeWork, so it is never put on
the Product itself. Unmarked text adds nothing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.ai_content')

GENERATED = 'https://schema.org/TrainedAlgorithmicMediaDigitalSource'

# What a product page shows of the product's own text, in the order the Product
# node reads it: the fields the product's own marks cover.
_VISIBLE = (('short_description', 'Short description'), ('description', 'Description'))

# Enough to tie the mark to the text without repeating a long page in the head.
_MAX_TEXT = 5000


def on_seo_jsonld_graph(value, page=None, request=None, **kwargs):
    """``SEO_JSONLD_GRAPH`` subscriber: mark the page's AI-written text."""
    try:
        if not isinstance(value, dict) or not isinstance(value.get('@graph'), list):
            return value
        obj = _page_object(page)
        if obj is None:
            return value
        fields = _marked_fields(obj)
        if not fields:
            return value
        is_product = getattr(obj, '_meta', None) and obj._meta.label_lower == 'catalog.product'
        anchor = _product_node(value) if is_product else _main_node(value)
        if anchor is None or not anchor.get('@id'):
            return value
        from plugins.installed.ai_content.marks import plain_text

        url = anchor['@id'].split('#')[0]
        refs = []
        for field, name in fields:
            text = plain_text(getattr(obj, field, '') or '')
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
                    'about': {'@id': anchor['@id']},
                }
            )
            refs.append({'@id': node_id})
        if refs:
            _add_subject_of(anchor, refs)
    except Exception as e:  # noqa: BLE001 — an enricher must never lose the graph
        logger.warning('ai_content: JSON-LD marking failed: %s', e, exc_info=True)
    return value


def _page_object(page):
    """The object the page is about, as the page shows it (the head's own choice)."""
    context = getattr(page, 'context', None) or {}
    obj = context.get('seo_content_object') if isinstance(context, dict) else None
    obj = obj or getattr(page, 'obj', None)
    return obj if getattr(obj, '_meta', None) is not None else None


def _marked_fields(obj) -> list[tuple[str, str]]:
    """``[(field, name)]`` of the shown text an AI wrote: its own marks, then translations.

    An own mark covers the object's own text only: a field shown in a translation
    is marked when that translation began as an AI draft, never because of it.
    """
    from core.i18n.services import ai_translated, shown_in_translation
    from plugins.installed.ai_content.marks import marks_for

    own = marks_for(obj)
    translated = shown_in_translation(obj)
    names = dict(_VISIBLE)
    fields = [field for field, _name in _VISIBLE if field in own and field not in translated]
    fields += [f for f in ai_translated(obj) if f not in fields]
    return [(f, names.get(f) or f.replace('_', ' ').capitalize()) for f in fields]


def _add_subject_of(node: dict, refs: list[dict]) -> None:
    """Point ``node`` at ``refs`` through ``subjectOf``, keeping what it pointed at."""
    existing = node.get('subjectOf')
    kept = [existing] if isinstance(existing, dict) else list(existing or [])
    kept += [r for r in refs if r not in kept]
    node['subjectOf'] = kept if len(kept) > 1 else kept[0]


def _product_node(graph) -> dict | None:
    for node in graph['@graph']:
        if isinstance(node, dict) and 'Product' in str(node.get('@type', '')):
            return node
    return None


def _main_node(graph) -> dict | None:
    """The node the page is about: the WebPage's main entity when the graph holds it, else the WebPage."""
    nodes = [n for n in graph['@graph'] if isinstance(n, dict)]
    webpage = next((n for n in nodes if str(n.get('@id', '')).endswith('#webpage')), None)
    if webpage is None:
        return None
    main = webpage.get('mainEntity')
    main_id = main.get('@id') if isinstance(main, dict) else ''
    if main_id:
        found = next((n for n in nodes if n.get('@id') == main_id), None)
        if found is not None:
            return found
    return webpage
