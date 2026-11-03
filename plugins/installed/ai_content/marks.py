"""Which of a product's text an AI wrote (EU AI Act Art. 50).

A tool that writes text calls ``core.agents.provenance.mark_ai_written``; this app
stores each mark as a metafield in the ``ai`` namespace (key: the field, value:
who wrote it) and publishes it on the product page, in the structured data and in
the AI Act report. The merchant clears a mark in the product editor; no agent tool
can, because the mark exists precisely because an agent wrote the text.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('morpheus.ai_content.marks')

NAMESPACE = 'ai'

# The product text the editor card lists, in the order it lists them.
PRODUCT_FIELDS = (
    ('description', _('Description')),
    ('short_description', _('Short description')),
    ('meta_title', _('Meta title')),
    ('meta_description', _('Meta description')),
)

# Who wrote it: the value stored on the mark.
SOURCES = {
    'linda': 'Linda',
    'worker': 'An AI worker',
    'editor': "The product editor's AI writer",
    'bulk': 'A bulk AI rewrite',
}


def on_ai_content_written(instance=None, fields=None, source='', **kwargs) -> None:
    """``AI_CONTENT_WRITTEN`` subscriber: store one mark per field."""
    if instance is None or not source:
        return
    from plugins.installed.metafields.models import Metafield

    try:
        # Its own savepoint: a failed write must not abort the caller's transaction.
        with transaction.atomic():
            for field in fields or ():
                Metafield.objects.set(
                    instance, namespace=NAMESPACE, key=str(field)[:120], value=str(source)
                )
    except Exception as e:  # noqa: BLE001 — the text is written; losing its mark is logged
        logger.error('ai_content: could not mark %s as written with AI: %s', fields, e)


def marks_for(instance) -> dict[str, str]:
    """``{field: source}`` for every field of ``instance`` marked as written with AI."""
    if instance is None or getattr(instance, 'pk', None) is None:
        return {}
    from django.contrib.contenttypes.models import ContentType

    from plugins.installed.metafields.models import Metafield

    rows = Metafield.objects.filter(
        content_type=ContentType.objects.get_for_model(type(instance)),
        object_id=str(instance.pk),
        namespace=NAMESPACE,
    ).values_list('key', 'value')
    return dict(rows)


def save_from_form(product, post) -> None:
    """Set or clear the marks from the editor card's checkboxes.

    Acts only when the card was on the page (``ai_text_submitted``): an unticked box
    is absent from the POST, so without the marker a save from anywhere else would
    clear every mark.
    """
    if product is None or post is None or not post.get('ai_text_submitted'):
        return
    from plugins.installed.metafields.models import Metafield

    marked = marks_for(product)
    with transaction.atomic():
        for field, _label in PRODUCT_FIELDS:
            ticked = bool(post.get(f'ai_written_{field}'))
            if ticked and field not in marked:
                Metafield.objects.set(product, namespace=NAMESPACE, key=field, value='editor')
            elif not ticked and field in marked:
                Metafield.objects.delete_for(product, namespace=NAMESPACE, key=field)


def report_rows(*, since=None, until=None) -> list[dict]:
    """The marks set or changed in [since, until), oldest first."""
    from plugins.installed.metafields.models import Metafield

    qs = Metafield.objects.filter(namespace=NAMESPACE).select_related('content_type')
    if since is not None:
        qs = qs.filter(updated_at__gte=since)
    if until is not None:
        qs = qs.filter(updated_at__lt=until)
    return [
        {
            'timestamp': m.updated_at.isoformat() if m.updated_at else '',
            'object': f'{m.content_type.app_label}.{m.content_type.model}:{m.object_id}',
            'field': m.key,
            'source': m.value,
        }
        for m in qs.order_by('updated_at').iterator()
    ]
