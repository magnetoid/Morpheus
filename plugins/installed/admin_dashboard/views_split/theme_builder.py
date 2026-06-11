"""Theme builder — drag-drop sections editor for CMS pages.

Each `Page` row's section composition is edited at
`/dashboard/pages/<id>/builder/`. The page renders the section list
(sortable via HTML5 drag-drop) on the left and a live-preview iframe
of the page on the right. JSON API endpoints handle add / remove /
reorder / settings updates without full reloads.

This is the v1: section-only (no nested blocks), settings edited as
raw JSON in a textarea per row. v2 will surface field-level controls
from the section's `schema`. Shipping the model + composer first so
merchants can already build pages today.
"""

from __future__ import annotations

import json
import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from morpheus.views import staff_member_required

logger = logging.getLogger('morpheus.admin.theme_builder')


def _serialize_section_def(section) -> dict:
    return {
        'id': section.id,
        'label': section.label,
        'description': section.description,
        'icon': section.icon,
        'schema': section.schema,
        'defaults': section.defaults,
    }


def _serialize_row(row) -> dict:
    return {
        'id': str(row.id),
        'section_id': row.section_id,
        'sort_order': row.sort_order,
        'settings': row.settings or {},
        'is_visible': row.is_visible,
    }


@staff_member_required
def builder(request: HttpRequest, page_id) -> HttpResponse:
    from plugins.installed.cms.models import Page
    from themes.sections import section_registry

    page = get_object_or_404(Page, pk=page_id)
    rows = list(page.sections.all().order_by('sort_order', 'created_at'))
    return render(
        request,
        'admin_dashboard/theme_builder.html',
        {
            'page': page,
            'rows': [_serialize_row(r) for r in rows],
            'available_sections': [_serialize_section_def(s) for s in section_registry.all()],
            'available_sections_json': json.dumps(
                [_serialize_section_def(s) for s in section_registry.all()]
            ),
            'rows_json': json.dumps([_serialize_row(r) for r in rows]),
            'preview_url': f'/p/{page.slug}/?preview=1',
            'active_nav': 'cms',
        },
    )


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def api_add(request: HttpRequest, page_id) -> JsonResponse:
    """Append a new section to a page. Returns the created row."""
    from plugins.installed.cms.models import Page, PageSection
    from themes.sections import section_registry

    page = get_object_or_404(Page, pk=page_id)
    section_id = (request.POST.get('section_id') or '').strip()
    if not section_id or section_id not in section_registry:
        return JsonResponse({'error': f'unknown section: {section_id}'}, status=400)
    section = section_registry.get(section_id)

    last = page.sections.order_by('-sort_order').first()
    sort_order = (last.sort_order + 1) if last else 0
    row = PageSection.objects.create(
        page=page,
        section_id=section_id,
        sort_order=sort_order,
        settings=dict(section.defaults or {}),
    )
    return JsonResponse({'row': _serialize_row(row)})


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def api_reorder(request: HttpRequest, page_id) -> JsonResponse:
    """Replace the sort order of every row on a page in one call.

    Body: ``ids[]=<row_id>&...`` in the new order. Anything missing
    from the list is left where it is. Anything passed that isn't on
    this page is silently ignored.
    """
    from plugins.installed.cms.models import Page, PageSection

    get_object_or_404(Page, pk=page_id)
    ids = request.POST.getlist('ids[]') or request.POST.getlist('ids')
    if not ids:
        return JsonResponse({'error': 'no ids'}, status=400)
    rows_by_id = {str(r.id): r for r in PageSection.objects.filter(page_id=page_id, id__in=ids)}
    for index, rid in enumerate(ids):
        row = rows_by_id.get(str(rid))
        if row is None:
            continue
        if row.sort_order != index:
            row.sort_order = index
            row.save(update_fields=['sort_order', 'updated_at'])
    return JsonResponse({'ok': True, 'count': len(rows_by_id)})


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def api_update(request: HttpRequest, page_id, row_id) -> JsonResponse:
    """Update a row's settings or visibility."""
    from plugins.installed.cms.models import PageSection

    row = get_object_or_404(PageSection, pk=row_id, page_id=page_id)

    settings_raw = request.POST.get('settings')
    if settings_raw is not None:
        try:
            row.settings = json.loads(settings_raw) if settings_raw.strip() else {}
        except json.JSONDecodeError as e:
            return JsonResponse({'error': f'invalid JSON: {e}'}, status=400)

    if 'is_visible' in request.POST:
        row.is_visible = request.POST.get('is_visible') in ('1', 'true', 'on', 'True')

    row.save()
    return JsonResponse({'row': _serialize_row(row)})


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def api_delete(request: HttpRequest, page_id, row_id) -> JsonResponse:
    from plugins.installed.cms.models import PageSection

    row = get_object_or_404(PageSection, pk=row_id, page_id=page_id)
    row.delete()
    return JsonResponse({'ok': True})
