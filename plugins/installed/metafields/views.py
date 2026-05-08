"""Metafields dashboard — browse + edit raw triples.

This is intentionally generic: any model with a primary key can have
metafields. The dashboard surfaces every record with at least one
metafield, lets staff search by namespace/key, and edit/delete each
triple individually.

Per-resource pickers (e.g. "edit metafields on this product") are
expected to live alongside the record's main edit form and use this
plugin's `MetafieldManager` API directly. Adding those is a follow-up;
this dashboard is the universal escape hatch.
"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from morpheus.views import staff_member_required
from plugins.installed.metafields.models import Metafield

logger = logging.getLogger('morpheus.metafields.views')


@staff_member_required
def index(request: HttpRequest) -> HttpResponse:
    qs = Metafield.objects.select_related('content_type').all()

    namespace = (request.GET.get('namespace') or '').strip()
    if namespace:
        qs = qs.filter(namespace=namespace)
    key = (request.GET.get('key') or '').strip()
    if key:
        qs = qs.filter(key__icontains=key)
    model_label = (request.GET.get('model') or '').strip()
    if model_label and '.' in model_label:
        try:
            app, mname = model_label.split('.', 1)
            ct = ContentType.objects.get(app_label=app, model=mname.lower())
            qs = qs.filter(content_type=ct)
        except ContentType.DoesNotExist:
            pass

    try:
        from plugins.installed.admin_dashboard.views_split._shared import paginate_and_sort
        page_obj, paging_ctx = paginate_and_sort(
            request, qs,
            default_sort='-updated_at',
            allowed_sorts=('namespace', 'key', 'updated_at'),
            default_per_page=50,
        )
        rows = list(page_obj.object_list)
    except Exception:  # noqa: BLE001
        paging_ctx = {}
        rows = list(qs[:200])

    namespaces = list(
        Metafield.objects.values_list('namespace', flat=True)
        .distinct().order_by('namespace')
    )
    return render(request, 'metafields/index.html', {
        'metafields': rows,
        'namespace': namespace,
        'key': key,
        'model_label': model_label,
        'namespaces': [n for n in namespaces if n],
        'active_nav': 'metafields',
        **paging_ctx,
    })


@staff_member_required
def create_form(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        return _save_from_form(request, metafield=None)
    return render(request, 'metafields/edit.html', {
        'metafield': None,
        'value_types': Metafield.VALUE_TYPES,
        'content_types': _content_type_choices(),
        'active_nav': 'metafields',
    })


@staff_member_required
def edit_form(request: HttpRequest, metafield_id) -> HttpResponse:
    m = get_object_or_404(Metafield, pk=metafield_id)
    if request.method == 'POST':
        return _save_from_form(request, metafield=m)
    return render(request, 'metafields/edit.html', {
        'metafield': m,
        'value_types': Metafield.VALUE_TYPES,
        'content_types': _content_type_choices(),
        'active_nav': 'metafields',
    })


@staff_member_required
def delete(request: HttpRequest, metafield_id) -> HttpResponse:
    m = get_object_or_404(Metafield, pk=metafield_id)
    if request.method == 'POST':
        m.delete()
        messages.success(request, f'Deleted metafield "{m.full_key}".')
    return redirect('metafields:index')


def _save_from_form(request: HttpRequest, *, metafield) -> HttpResponse:
    namespace = (request.POST.get('namespace') or '').strip()[:80]
    key = (request.POST.get('key') or '').strip()[:120]
    value = (request.POST.get('value') or '').strip()
    value_type = (request.POST.get('value_type') or 'string').strip()
    description = (request.POST.get('description') or '').strip()[:300]
    ct_id = request.POST.get('content_type', '').strip()
    object_id = (request.POST.get('object_id') or '').strip()[:64]

    if not key:
        messages.error(request, 'Key is required.')
        return redirect('metafields:index')
    if not (ct_id and object_id):
        messages.error(request, 'Pick a target content type + object id.')
        return redirect('metafields:index')
    try:
        ct = ContentType.objects.get(pk=ct_id)
    except ContentType.DoesNotExist:
        messages.error(request, 'Unknown content type.')
        return redirect('metafields:index')

    try:
        if metafield is None:
            metafield = Metafield(content_type=ct, object_id=object_id)
        metafield.namespace = namespace
        metafield.key = key
        metafield.value = value
        metafield.value_type = value_type
        metafield.description = description
        metafield.save()
        messages.success(request, f'Saved metafield "{metafield.full_key}".')
    except Exception as e:  # noqa: BLE001 — surface uniqueness etc.
        logger.warning('metafields: save failed: %s', e, exc_info=True)
        messages.error(request, f'Save failed: {e}')
    return redirect('metafields:index')


def _content_type_choices():
    """Curated content-type list — only the high-value targets.

    Showing every model in the project would surface internals
    (Migration, LogEntry, Token, …) that nobody attaches metafields
    to. Hand-pick the surfaces that make sense.
    """
    targets = [
        ('catalog', 'product'), ('catalog', 'productvariant'),
        ('catalog', 'category'), ('catalog', 'collection'),
        ('orders', 'order'), ('orders', 'orderitem'),
        ('customers', 'customer'),
        ('cms', 'page'), ('cms', 'block'),
    ]
    choices = []
    for app, model in targets:
        try:
            ct = ContentType.objects.get(app_label=app, model=model)
            choices.append({'id': ct.pk, 'label': f'{app}.{model}'})
        except ContentType.DoesNotExist:
            continue
    return choices
