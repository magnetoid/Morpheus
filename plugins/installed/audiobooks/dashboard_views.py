"""audiobooks — dashboard actions (staff-only), used by the product card."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from core.authz import require_capability
from morpheus.app.views import staff_member_required


def _audiobook(audiobook_id):
    from plugins.installed.audiobooks.models import Audiobook

    return Audiobook.objects.filter(id=audiobook_id).select_related('variant__product').first()


@require_POST
@staff_member_required
@require_capability('catalog.write')
def generate_audiobook_view(request, audiobook_id):
    """Start a narration job: ``job`` is 'sample' or 'full'; ``provider`` and
    ``voice`` are the card's choices, saved on the edition. JSON either way."""
    from plugins.installed.audiobooks.services import start, status

    audiobook = _audiobook(audiobook_id)
    if audiobook is None:
        return JsonResponse({'ok': False, 'reason': 'not found'}, status=404)
    result = start(
        audiobook,
        job=request.POST.get('job', 'full'),
        provider=request.POST.get('provider'),
        voice=request.POST.get('voice'),
    )
    return JsonResponse({**result, 'state': status(audiobook)}, status=200 if result['ok'] else 400)


@require_GET
@staff_member_required
@require_capability('catalog.read')
def audiobook_status_view(request, audiobook_id):
    from plugins.installed.audiobooks.services import status

    audiobook = _audiobook(audiobook_id)
    if audiobook is None:
        return JsonResponse({'ok': False, 'reason': 'not found'}, status=404)
    return JsonResponse({'ok': True, 'state': status(audiobook)})
