"""What the seo app contributes into other apps' dashboard screens.

Two contributions, both delivered through filters so that disabling this app
removes them and no shell ever imports it:

* the per-entity SEO panel, as a card on the product / category / collection /
  page edit forms;
* the SEO score, as a column in the product list.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.seo')

# Which of the host form's inputs the panel's live preview should mirror while
# the merchant types, per shell. Without this the Google preview sits empty on a
# brand-new product until they open the SEO card and fill it in by hand.
_HOST_FIELDS = {
    # The product's short description is a rich-text editor, not an input, so
    # there is nothing to mirror there; the name alone still gets the preview
    # populated on a brand-new product.
    'product': {'title': 'product-name', 'desc': '', 'image': ''},
    # Category/collection forms render Django-generated widgets, hence `id_*`.
    'category': {'title': 'id_name', 'desc': 'id_description', 'image': ''},
    'collection': {'title': 'id_name', 'desc': 'id_description', 'image': ''},
    'page': {'title': 'page-title', 'desc': 'page-excerpt', 'image': 'page-cover'},
}


def seo_form_card(kind: str, obj, request=None) -> dict | None:
    """The `{'template', 'context', 'order'}` card for one entity form.

    `request` matters: on a validation re-render the panel re-fills itself from
    POST so a merchant does not lose SEO edits to an unrelated failure (a slug
    clash). The shells pass it into the filter for exactly that.
    """
    from plugins.installed.seo.services.panel import panel_context

    try:
        context = panel_context(obj, request)
    except Exception as e:  # noqa: BLE001 — a broken card must not break the form
        logger.warning('seo: could not build the SEO card for %s: %s', kind, e, exc_info=True)
        return None
    hosts = _HOST_FIELDS.get(kind, {})
    context.update(
        {
            'seo_host_title_id': hosts.get('title', ''),
            'seo_host_desc_id': hosts.get('desc', ''),
            'seo_host_image_id': hosts.get('image', ''),
        }
    )
    return {
        'template': 'seo/cards/_seo_form_card.html',
        'context': context,
        'order': 60,
    }


def annotate_seo_scores(products) -> None:
    """Attach `seo_score` to each product in ONE query.

    The column is pre-rendered per product for the whole page, so reading the
    score per row would N+1 the product list — the exact trap `PRODUCT_LIST_
    COLUMNS` documents.
    """
    from django.contrib.contenttypes.models import ContentType

    from plugins.installed.seo.models import SeoAuditResult

    try:
        ids = [str(p.pk) for p in products]
        ct = ContentType.objects.get_for_model(type(products[0]))
        scores = dict(
            SeoAuditResult.objects.filter(content_type=ct, object_id__in=ids).values_list(
                'object_id', 'score'
            )
        )
    except Exception as e:  # noqa: BLE001 — an unmigrated DB or an empty list
        logger.debug('seo: could not load product SEO scores: %s', e)
        scores = {}
    for product in products:
        # A non-underscore name: Django templates refuse leading underscores.
        product.seo_score = scores.get(str(product.pk))
