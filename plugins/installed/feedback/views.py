"""Feedback ticket submit + the Settings → Feedback queue."""

from __future__ import annotations

import base64
import binascii
import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.authz import enforce, require_capability

from .models import FeedbackTicket

logger = logging.getLogger(__name__)

# A screenshot arrives base64 in the JSON body. DATA_UPLOAD_MAX_MEMORY_SIZE is
# 2.5MB by default, so the client already downscales + JPEG-encodes; this is the
# server-side backstop for anything that slips past it.
MAX_SCREENSHOT_BYTES = 2 * 1024 * 1024
MAX_MESSAGE_CHARS = 5000
MAX_CLIENT_ERRORS = 25


def _decode_screenshot(data_url: str) -> tuple[ContentFile | None, str]:
    """base64 data URL → ContentFile. Returns (file, skipped_reason)."""
    if not data_url or not isinstance(data_url, str):
        return None, ''
    if not data_url.startswith('data:image/'):
        return None, 'failed'
    try:
        header, _, payload = data_url.partition(',')
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None, 'failed'
    if not raw:
        return None, 'failed'
    if len(raw) > MAX_SCREENSHOT_BYTES:
        return None, 'too_large'
    ext = 'png' if 'image/png' in header else 'jpg'
    return ContentFile(raw, name=f'feedback.{ext}'), ''


def _recent_server_errors(limit: int = 10) -> list[dict]:
    """Snapshot recent server-side errors so the ticket carries them forever.

    Referencing rows by id would be cheaper, but they are pruned — a ticket that
    points at deleted evidence is worse than one that copied it.
    """
    try:
        from core.errors.models import ErrorEvent  # noqa: PLC0415

        rows = ErrorEvent.objects.order_by('-id')[:limit]
        return [
            {
                'kind': r.kind,
                'level': r.level,
                'exception_class': r.exception_class,
                'message': (r.message or '')[:500],
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001 — evidence is a bonus, never a blocker
        return []


@staff_member_required
@require_POST
def submit(request):
    """Create a ticket. Any signed-in staff member may report.

    Deliberately NOT gated on `system.write`: needing permission to read the
    queue in order to report a bug would silence exactly the people who hit them.
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'errors': {'__all__': 'Malformed request.'}}, status=400)

    message = (payload.get('message') or '').strip()
    if not message:
        return JsonResponse(
            {'ok': False, 'errors': {'message': 'Tell us what happened.'}}, status=400
        )

    shot, decode_reason = _decode_screenshot(payload.get('screenshot') or '')
    reason = decode_reason or (payload.get('screenshot_skipped_reason') or '')[:200]

    errors = payload.get('client_errors')
    errors = errors[:MAX_CLIENT_ERRORS] if isinstance(errors, list) else []

    user = request.user
    ticket = FeedbackTicket(
        user=user,
        reporter_label=(user.get_full_name() or getattr(user, 'email', '') or '')[:200],
        message=message[:MAX_MESSAGE_CHARS],
        screenshot_skipped_reason='' if shot else reason,
        page_url=(payload.get('page_url') or '')[:1000],
        page_title=(payload.get('page_title') or '')[:300],
        viewport=(payload.get('viewport') or '')[:40],
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:500],
        client_errors=errors,
        context={
            'version': _version(),
            'request_id': getattr(request, 'request_id', '') or '',
            'server_errors': _recent_server_errors(),
        },
    )
    if shot:
        ticket.screenshot.save(shot.name, shot, save=False)
    ticket.save()
    logger.info('feedback: ticket %s opened by %s', ticket.pk, ticket.reporter_label)
    return JsonResponse({'ok': True, 'id': str(ticket.pk)})


def _version() -> str:
    try:
        from django.conf import settings  # noqa: PLC0415

        return getattr(settings, 'MORPHEUS_VERSION', '') or ''
    except Exception:  # noqa: BLE001
        return ''


@staff_member_required
@require_capability('system.read')
def ticket_list(request):
    qs = FeedbackTicket.objects.select_related('user')
    status = request.GET.get('status') or ''
    if status in dict(FeedbackTicket.STATUS_CHOICES):
        qs = qs.filter(status=status)
    page = Paginator(qs, 25).get_page(request.GET.get('page'))
    return render(
        request,
        'feedback/tickets.html',
        {
            'page_obj': page,
            'tickets': page.object_list,
            'status': status,
            'status_choices': FeedbackTicket.STATUS_CHOICES,
            'open_count': FeedbackTicket.objects.filter(status=FeedbackTicket.STATUS_OPEN).count(),
            'breadcrumb_trail': [
                {'label': 'Settings', 'url': '/dashboard/settings/'},
                {'label': 'Feedback', 'url': ''},
            ],
        },
    )


@staff_member_required
@require_capability('system.read')
def ticket_detail(request, pk):
    ticket = get_object_or_404(FeedbackTicket.objects.select_related('user'), pk=pk)
    if request.method == 'POST':
        enforce(request, 'system.write')
        new_status = request.POST.get('status') or ''
        if new_status not in dict(FeedbackTicket.STATUS_CHOICES):
            raise Http404('Unknown status.')
        ticket.status = new_status
        ticket.save(update_fields=['status', 'updated_at'])
        return redirect(request.path)
    return render(
        request,
        'feedback/ticket_detail.html',
        {
            'ticket': ticket,
            'status_choices': FeedbackTicket.STATUS_CHOICES,
            'breadcrumb_trail': [
                {'label': 'Settings', 'url': '/dashboard/settings/'},
                {'label': 'Feedback', 'url': '/dashboard/settings/feedback/'},
                {'label': ticket.summary[:40], 'url': ''},
            ],
        },
    )
