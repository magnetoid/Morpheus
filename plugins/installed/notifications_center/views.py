"""Notification list + JSON API for the topbar bell."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from morpheus.views import staff_member_required
from plugins.installed.notifications_center.models import Notification

logger = logging.getLogger('morpheus.notifications_center.views')


@staff_member_required
def notifications_list(request: HttpRequest) -> HttpResponse:
    qs = Notification.objects.filter(user=request.user)
    show = (request.GET.get('show') or 'all').strip()
    if show == 'unread':
        qs = qs.filter(read_at__isnull=True)
    try:
        from plugins.installed.admin_dashboard.views_split._shared import paginate_and_sort

        page_obj, paging_ctx = paginate_and_sort(
            request,
            qs,
            default_sort='-created_at',
            allowed_sorts=('created_at', 'kind'),
            default_per_page=50,
        )
        rows = list(page_obj.object_list)
    except Exception:  # noqa: BLE001
        paging_ctx = {}
        rows = list(qs[:200])

    unread_total = Notification.objects.filter(
        user=request.user,
        read_at__isnull=True,
    ).count()
    return render(
        request,
        'notifications_center/list.html',
        {
            'notifications': rows,
            'unread_total': unread_total,
            'show': show,
            'active_nav': 'notifications',
            **paging_ctx,
        },
    )


@staff_member_required
@require_http_methods(['POST'])
def mark_read(request: HttpRequest, notification_id) -> HttpResponse:
    n = get_object_or_404(Notification, pk=notification_id, user=request.user)
    if n.read_at is None:
        n.read_at = timezone.now()
        n.save(update_fields=['read_at'])
    target = (n.action_url or '').strip()
    if target.startswith('/'):
        return redirect(target)
    return redirect('notifications_center:list')


@staff_member_required
@require_http_methods(['POST'])
def mark_all_read(request: HttpRequest) -> HttpResponse:
    Notification.objects.filter(
        user=request.user,
        read_at__isnull=True,
    ).update(read_at=timezone.now())
    messages.success(request, 'All notifications marked read.')
    return redirect('notifications_center:list')


@staff_member_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
def api_latest(request: HttpRequest) -> JsonResponse:
    """JSON endpoint feeding the topbar bell dropdown.

    GET  → latest 10 notifications for the current user + unread count
    POST → mark a single notification read by id (`?id=...`).
    """
    if request.method == 'POST':
        nid = (request.POST.get('id') or '').strip()
        if nid:
            Notification.objects.filter(
                pk=nid,
                user=request.user,
                read_at__isnull=True,
            ).update(read_at=timezone.now())
        return JsonResponse({'ok': True})
    rows = list(Notification.objects.filter(user=request.user).order_by('-created_at')[:10])
    unread = Notification.objects.filter(
        user=request.user,
        read_at__isnull=True,
    ).count()
    return JsonResponse(
        {
            'unread': unread,
            'notifications': [
                {
                    'id': str(n.id),
                    'kind': n.kind,
                    'title': n.title,
                    'body': n.body[:240],
                    'action_url': n.action_url,
                    'icon': n.icon or 'bell',
                    'read': n.read_at is not None,
                    'created_at': n.created_at.isoformat(),
                }
                for n in rows
            ],
        }
    )
