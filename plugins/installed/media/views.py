"""Media library views — browse / upload / edit / delete."""
from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from morpheus.views import staff_member_required
from plugins.installed.media.models import MediaAsset

logger = logging.getLogger('morpheus.media.views')


@staff_member_required
def library(request: HttpRequest) -> HttpResponse:
    """Browse the library — paginated grid with kind / tag / search filters."""
    qs = MediaAsset.objects.all()
    kind = (request.GET.get('kind') or '').strip()
    if kind:
        qs = qs.filter(kind=kind)
    search = (request.GET.get('q') or '').strip()
    if search:
        qs = qs.filter(filename__icontains=search) | qs.filter(alt_text__icontains=search)
    tag = (request.GET.get('tag') or '').strip()
    if tag:
        qs = qs.filter(tags__contains=[tag])

    # Pagination — reuse the dashboard helper from earlier today.
    try:
        from plugins.installed.admin_dashboard.views_split._shared import paginate_and_sort
        page_obj, paging_ctx = paginate_and_sort(
            request, qs,
            default_sort='-created_at',
            allowed_sorts=('created_at', 'filename', 'size_bytes', 'kind'),
            default_per_page=50,
        )
        assets = list(page_obj.object_list)
    except Exception:  # noqa: BLE001 — admin_dashboard may not be loaded
        paging_ctx = {}
        assets = list(qs[:200])

    # Build a pre-rendered tab list so the template doesn't need a
    # custom dict-getter filter. First entry is the "All" pseudo-tab.
    kind_tabs = [{
        'key': '',
        'label': 'All',
        'count': MediaAsset.objects.count(),
        'active': not kind,
    }]
    for kind_key, kind_label in MediaAsset.KIND_CHOICES:
        kind_tabs.append({
            'key': kind_key,
            'label': kind_label,
            'count': MediaAsset.objects.filter(kind=kind_key).count(),
            'active': kind == kind_key,
        })

    return render(request, 'media/library.html', {
        'assets': assets,
        'kind': kind,
        'search': search,
        'tag': tag,
        'kind_tabs': kind_tabs,
        'active_nav': 'media',
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
