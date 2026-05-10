"""Asset library views — browse / upload / edit / delete.

Single page with tabs across every asset type the merchant might care
about: images, video, audio, PDFs, spreadsheets, Word docs, other
documents, plus a special tab for *digital products* (Product rows
with ``product_type='digital'`` and an attached ``digital_file``).
"""
from __future__ import annotations

import json  # noqa: F401 — re-exported for picker callers
import logging

from django.contrib import messages
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from morpheus.views import staff_member_required
from plugins.installed.media.models import MediaAsset

logger = logging.getLogger('morpheus.media.views')


# Mime → "view" classifier for fine-grained tabs within the document kind.
# Order is significant — first match wins.
_DOC_VIEWS = (
    ('pdf',         'PDFs',         'file-text', ('pdf',)),
    ('spreadsheet', 'Spreadsheets', 'sheet',     ('spreadsheet', 'excel', 'csv', '.xls', '.xlsx', '.numbers')),
    ('word',        'Word docs',    'file-text', ('word', 'wordprocessingml', '.doc', '.docx', '.rtf')),
)


def _filter_for_view(qs, view: str):
    """Narrow ``qs`` to a single tab. Returns the same queryset when view='all'."""
    if view == 'image':
        return qs.filter(kind=MediaAsset.KIND_IMAGE)
    if view == 'video':
        return qs.filter(kind=MediaAsset.KIND_VIDEO)
    if view == 'audio':
        return qs.filter(kind=MediaAsset.KIND_AUDIO)
    if view == 'document':
        narrowed = qs.filter(kind=MediaAsset.KIND_DOCUMENT)
        for _, _, _, needles in _DOC_VIEWS:
            for n in needles:
                narrowed = narrowed.exclude(
                    Q(mime_type__icontains=n) | Q(filename__icontains=n)
                )
        return narrowed
    if view == 'other':
        return qs.filter(kind=MediaAsset.KIND_OTHER)
    for key, _, _, needles in _DOC_VIEWS:
        if view == key:
            q = Q()
            for n in needles:
                q |= Q(mime_type__icontains=n) | Q(filename__icontains=n)
            return qs.filter(kind=MediaAsset.KIND_DOCUMENT).filter(q)
    return qs


def _build_tabs(view: str) -> list[dict]:
    """Pre-counted tab list rendered into the template."""
    base = MediaAsset.objects.all()
    tabs = [{
        'key': 'all', 'label': 'All', 'icon': 'layers',
        'count': base.count(),
        'active': view in ('all', ''),
    }]
    for key, label, icon in (
        ('image', 'Images', 'image'),
        ('video', 'Videos', 'film'),
        ('audio', 'Audio',  'music'),
    ):
        tabs.append({
            'key': key, 'label': label, 'icon': icon,
            'count': base.filter(kind=key).count(),
            'active': view == key,
        })
    for key, label, icon, _ in _DOC_VIEWS:
        tabs.append({
            'key': key, 'label': label, 'icon': icon,
            'count': _filter_for_view(base, key).count(),
            'active': view == key,
        })
    tabs.append({
        'key': 'document', 'label': 'Other docs', 'icon': 'file',
        'count': _filter_for_view(base, 'document').count(),
        'active': view == 'document',
    })
    tabs.append({
        'key': 'other', 'label': 'Other', 'icon': 'box',
        'count': base.filter(kind=MediaAsset.KIND_OTHER).count(),
        'active': view == 'other',
    })
    digital_count = 0
    try:
        from plugins.installed.catalog.models import Product
        digital_count = Product.objects.filter(product_type='digital').count()
    except Exception:  # noqa: BLE001
        pass
    tabs.append({
        'key': 'digital_products', 'label': 'Digital products', 'icon': 'download',
        'count': digital_count,
        'active': view == 'digital_products',
    })
    return tabs


@staff_member_required
def library(request: HttpRequest) -> HttpResponse:
    """Browse the asset library — single page with tabs across every type."""
    view = (request.GET.get('view') or 'all').strip().lower() or 'all'

    # Special branch — digital products live in the catalog Product table.
    if view == 'digital_products':
        digital_products: list = []
        try:
            from plugins.installed.catalog.models import Product
            digital_products = list(
                Product.objects.filter(product_type='digital')
                .order_by('-updated_at')[:200]
            )
        except Exception as e:  # noqa: BLE001
            logger.debug('media.library: digital products query failed: %s', e)
        return render(request, 'media/library.html', {
            'view': view,
            'kind_tabs': _build_tabs(view),
            'digital_products': digital_products,
            'active_nav': 'assets',
        })

    qs = _filter_for_view(MediaAsset.objects.all(), view)
    search = (request.GET.get('q') or '').strip()
    if search:
        qs = qs.filter(
            Q(filename__icontains=search) | Q(alt_text__icontains=search)
        )
    tag = (request.GET.get('tag') or '').strip()
    if tag:
        qs = qs.filter(tags__contains=[tag])

    try:
        from plugins.installed.admin_dashboard.views_split._shared import paginate_and_sort
        page_obj, paging_ctx = paginate_and_sort(
            request, qs,
            default_sort='-created_at',
            allowed_sorts=('created_at', 'filename', 'size_bytes', 'kind'),
            default_per_page=60,
        )
        assets = list(page_obj.object_list)
    except Exception:  # noqa: BLE001
        paging_ctx = {}
        assets = list(qs[:200])

    return render(request, 'media/library.html', {
        'assets': assets,
        'view': view,
        'search': search,
        'tag': tag,
        'kind_tabs': _build_tabs(view),
        'active_nav': 'assets',
        **paging_ctx,
    })


@staff_member_required
@require_http_methods(['POST'])
def upload(request: HttpRequest) -> HttpResponse:
    """Multipart upload — single or multi-file."""
    files = request.FILES.getlist('file') or request.FILES.getlist('files')
    if not files:
        messages.error(request, 'No files in upload.')
        return redirect('media:library')

    user = request.user if request.user.is_authenticated else None
    created = 0
    for f in files:
        try:
            MediaAsset.from_upload(uploaded_file=f, uploaded_by=user)
            created += 1
        except Exception as e:  # noqa: BLE001 — log + keep going
            logger.warning('media: upload failed for %s: %s', f.name, e, exc_info=True)
            messages.error(request, f'Failed to upload {f.name}: {e}')
    if created:
        messages.success(request, f'Uploaded {created} file(s).')
    return redirect('media:library')


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def api_upload(request: HttpRequest) -> JsonResponse:
    """JSON-returning upload endpoint — used by the picker modal so the
    image lands without a full page reload. Accepts a single `file`
    field. Returns the new asset's id + url + dimensions.
    """
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'no file'}, status=400)
    user = request.user if request.user.is_authenticated else None
    try:
        asset = MediaAsset.from_upload(uploaded_file=f, uploaded_by=user)
    except Exception as e:  # noqa: BLE001
        logger.warning('media: api upload failed: %s', e, exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({
        'id': str(asset.id),
        'url': asset.url,
        'filename': asset.filename,
        'kind': asset.kind,
        'mime_type': asset.mime_type,
        'width': asset.width,
        'height': asset.height,
        'size_bytes': asset.size_bytes,
        'alt_text': asset.alt_text,
    })


@staff_member_required
@require_http_methods(['POST'])
def delete(request: HttpRequest, asset_id) -> HttpResponse:
    asset = get_object_or_404(MediaAsset, pk=asset_id)
    asset.file.delete(save=False)  # remove from storage too
    name = asset.filename
    asset.delete()
    messages.success(request, f'Deleted "{name}".')
    return redirect('media:library')


@staff_member_required
def edit_meta(request: HttpRequest, asset_id) -> HttpResponse:
    """Edit alt text + tags. The file itself is replaced via re-upload."""
    asset = get_object_or_404(MediaAsset, pk=asset_id)
    if request.method == 'POST':
        asset.alt_text = (request.POST.get('alt_text') or '')[:300]
        raw_tags = (request.POST.get('tags') or '').strip()
        asset.tags = [t.strip() for t in raw_tags.split(',') if t.strip()]
        asset.save(update_fields=['alt_text', 'tags', 'updated_at'])
        messages.success(request, 'Asset updated.')
        return redirect('media:library')
    return render(request, 'media/edit_meta.html', {
        'asset': asset,
        'tags_str': ', '.join(asset.tags or []),
        'active_nav': 'media',
    })


@staff_member_required
def picker_modal(request: HttpRequest) -> HttpResponse:
    """Embeddable picker — used in iframes / dialogs in other forms.

    Returns a stripped-down library view with click-to-select rows.
    The host page wires up `window.postMessage({type: 'media:picked',
    asset: {…}})` from a small script in the modal.
    """
    qs = MediaAsset.objects.all()
    kind = (request.GET.get('kind') or '').strip()
    if kind:
        qs = qs.filter(kind=kind)
    search = (request.GET.get('q') or '').strip()
    if search:
        qs = qs.filter(filename__icontains=search) | qs.filter(alt_text__icontains=search)
    return render(request, 'media/picker.html', {
        'assets': list(qs[:60]),
        'kind': kind,
        'search': search,
    })
