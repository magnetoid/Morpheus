"""audiobooks — dashboard actions (staff-only)."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from morpheus.plugin.views import staff_member_required


@require_POST
@staff_member_required
def generate_audiobook_view(request, audiobook_id):
    """Enqueue ElevenLabs narration generation for an audiobook edition.
    Returns JSON so the product-form button can update without a reload."""
    from plugins.installed.audiobooks.models import Audiobook
    from plugins.installed.audiobooks.tasks import generate_audiobook

    audiobook = Audiobook.objects.filter(id=audiobook_id).first()
    if audiobook is None:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)
    audiobook.status = 'generating'
    audiobook.save(update_fields=['status', 'updated_at'])
    generate_audiobook.delay(str(audiobook.id))
    return JsonResponse({'ok': True, 'status': 'generating'})
