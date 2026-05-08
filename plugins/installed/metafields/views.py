"""Metafields dashboard — browse + edit raw triples.

This is intentionally generic: any model with a primary key can have
metafields. The dashboard surfaces every record with at least one
metafield, lets staff search by namespace/key, and edit/delete each
triple individually.

The inline editor partial (templates/metafields/_inline_editor.html)
is the per-record UX dropped into product/customer/order edit pages;
it talks to the JSON API at the bottom of this file.
"""
from __future__ import annotations

import json
import logging

from django.apps import apps
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

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


# ── JSON API used by the inline editor partial ──────────────────────────


def _resolve_target(request: HttpRequest):
    """Helper: pull `(model, object_id)` from request and validate.

    Returns (instance, content_type) or raises a JSON-shaped ValueError.
    """
    if request.method == 'GET':
        model = (request.GET.get('model') or '').strip()
        object_id = (request.GET.get('object_id') or '').strip()
    else:
        model = (request.POST.get('model') or '').strip()
        object_id = (request.POST.get('object_id') or '').strip()
    if not model or not object_id or '.' not in model:
        raise ValueError('model + object_id required')
    try:
        app_label, model_name = model.split('.', 1)
        m = apps.get_model(app_label, model_name)
    except (ValueError, LookupError):
        raise ValueError(f'unknown model: {model}')
    instance = m.objects.filter(pk=object_id).first()
    if instance is None:
        raise ValueError(f'{model} not found: {object_id}')
    ct = ContentType.objects.get_for_model(m)
    return instance, ct


@staff_member_required
@require_http_methods(['GET'])
def api_list(request: HttpRequest) -> JsonResponse:
    try:
        instance, ct = _resolve_target(request)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    rows = list(Metafield.objects.filter(content_type=ct, object_id=str(instance.pk)))
    return JsonResponse({'metafields': [
        {
            'id': str(m.id),
            'namespace': m.namespace,
            'key': m.key,
            'full_key': m.full_key,
            'value': m.value,
            'value_type': m.value_type,
            'description': m.description,
        }
        for m in rows
    ]})


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def api_set(request: HttpRequest) -> JsonResponse:
    try:
        instance, ct = _resolve_target(request)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    namespace = (request.POST.get('namespace') or '').strip()[:80]
    key = (request.POST.get('key') or '').strip()[:120]
    value = request.POST.get('value', '').strip()
    value_type = (request.POST.get('value_type') or 'string').strip()
    description = (request.POST.get('description') or '').strip()[:300]
    if not key:
        return JsonResponse({'error': 'key required'}, status=400)
    obj = Metafield.objects.set(
        instance, namespace=namespace, key=key,
        value=value, value_type=value_type,
    )
    if description and obj.description != description:
        obj.description = description
        obj.save(update_fields=['description', 'updated_at'])
    return JsonResponse({
        'id': str(obj.id),
        'namespace': obj.namespace,
        'key': obj.key,
        'full_key': obj.full_key,
        'value': obj.value,
        'value_type': obj.value_type,
        'description': obj.description,
    })


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def api_delete(request: HttpRequest) -> JsonResponse:
    metafield_id = (request.POST.get('id') or '').strip()
    if not metafield_id:
        return JsonResponse({'error': 'id required'}, status=400)
    deleted, _ = Metafield.objects.filter(pk=metafield_id).delete()
    return JsonResponse({'deleted': deleted})


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
