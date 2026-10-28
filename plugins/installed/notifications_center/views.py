"""Notification list, settings and the JSON API for the topbar bell.

Every view here acts on the signed-in staff member's own notifications, so
each needs a staff session and no capability: rbac grants `system.read` to
admins only, and gating on it would take an inventory manager's own low-stock
alerts away once roles are enforced (same as the Your account page).
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from morpheus.app.views import staff_member_required
from plugins.installed.notifications_center import services
from plugins.installed.notifications_center.models import LEVEL_CHOICES, LEVELS, Notification

logger = logging.getLogger('morpheus.notifications_center.views')

TABS = (('inbox', 'Inbox'), ('unread', 'Unread'), ('snoozed', 'Snoozed'), ('archived', 'Archived'))


def _tab_links(request: HttpRequest, current: str, counts: dict) -> list[dict]:
    """The `admin_dashboard/_tabs.html` shape; a tab keeps the filters, not the page."""
    links = []
    for key, label in TABS:
        params = request.GET.copy()
        params.pop('page', None)
        params['show'] = key
        links.append(
            {
                'label': label,
                'value': key,
                'count': counts.get(key, 0),
                'active': key == current,
                'href': f'{request.path}?{params.urlencode()}',
            }
        )
    return links


@staff_member_required
def notifications_list(request: HttpRequest) -> HttpResponse:
    user = request.user
    tab = (request.GET.get('show') or 'inbox').strip()
    if tab not in dict(TABS):
        tab = 'inbox'
    level = (request.GET.get('level') or '').strip()
    kind = (request.GET.get('kind') or '').strip()
    qs = services.listing(user, tab)
    if level in LEVELS:
        qs = qs.filter(level=level)
    if kind:
        qs = qs.filter(kind=kind)
    try:
        from plugins.installed.admin_dashboard.views_split._shared import paginate_and_sort

        page_obj, paging_ctx = paginate_and_sort(
            request,
            qs,
            default_sort=services.TAB_ORDER.get(tab, '-_activity'),
            default_per_page=50,
        )
        rows = list(page_obj.object_list)
    except Exception:  # noqa: BLE001
        paging_ctx = {}
        rows = list(qs[:200])

    for n in rows:
        n.kind_label = services.kind_label(n.kind)
    now = timezone.now()
    tab_counts = {
        'inbox': services.inbox(user, now=now).count(),
        'unread': services.unread_counts(user)['unread'],
        'snoozed': Notification.objects.filter(
            user=user, archived_at__isnull=True, snoozed_until__gt=now
        ).count(),
        'archived': Notification.objects.filter(user=user, archived_at__isnull=False).count(),
    }
    return render(
        request,
        'notifications_center/list.html',
        {
            'notifications': rows,
            'unread_total': tab_counts['unread'],
            'tabs': _tab_links(request, tab, tab_counts),
            'show': tab,
            'level': level,
            'kind': kind,
            'level_choices': LEVEL_CHOICES,
            'kind_choices': services.known_kinds(user),
            'snooze_choices': services.SNOOZE_CHOICES.items(),
            'muted': services.muted_kinds(user),
            'active_nav': 'notifications',
            **paging_ctx,
        },
    )


@staff_member_required
@require_http_methods(['POST'])
def mark_read(request: HttpRequest, notification_id) -> HttpResponse:
    """Open a notification: mark it read and go where it points."""
    n = get_object_or_404(Notification, pk=notification_id, user=request.user)
    services.apply(n, 'read')
    target = (n.action_url or '').strip()
    if target.startswith('/') and url_has_allowed_host_and_scheme(target, allowed_hosts=None):
        return redirect(target)
    return redirect('notifications_center:list')


@staff_member_required
@require_http_methods(['POST'])
def mark_all_read(request: HttpRequest) -> HttpResponse:
    services.inbox(request.user).filter(read_at__isnull=True).update(read_at=timezone.now())
    messages.success(request, 'All notifications marked read.')
    return redirect('notifications_center:list')


def _wants_json(request: HttpRequest) -> bool:
    return 'application/json' in request.headers.get('Accept', '') or request.headers.get(
        'X-Requested-With'
    ) == ('XMLHttpRequest')


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def act(request: HttpRequest, notification_id) -> HttpResponse:
    """Read / unread / archive / unarchive / snooze / wake / mute one notification.

    The bell posts with `Accept: application/json` and gets JSON back (success
    and failure alike); the list page's forms are redirected to `next`.
    """
    n = Notification.objects.filter(pk=notification_id, user=request.user).first()
    action = (request.POST.get('action') or '').strip()
    until = (request.POST.get('until') or '').strip()
    if n is None:
        line, ok = 'That notification is gone.', False
    else:
        try:
            line, ok = services.apply(n, action, until=until), True
        except ValueError as e:
            line, ok = str(e), False
    if _wants_json(request):
        return JsonResponse(
            {'ok': ok, 'message': line, **services.unread_counts(request.user)},
            status=200 if ok else 400,
        )
    (messages.success if ok else messages.error)(request, line)
    nxt = request.POST.get('next') or ''
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) and nxt.startswith(
        '/dashboard/'
    ):
        return redirect(nxt)
    return redirect('notifications_center:list')


@staff_member_required
@require_http_methods(['GET', 'POST'])
def preferences(request: HttpRequest) -> HttpResponse:
    """Which kinds of notification this staff member gets."""
    user = request.user
    kinds = services.known_kinds(user)
    if request.method == 'POST':
        wanted = set(request.POST.getlist('kind'))
        for key, _label in kinds:
            services.set_muted(user, key, key not in wanted)
        messages.success(request, 'Notification settings saved.')
        return redirect('notifications_center:preferences')
    muted = services.muted_kinds(user)
    rows = [
        {
            'key': key,
            'label': label,
            'level': services.KINDS.get(key, ('', 'info'))[1],
            'on': key not in muted,
        }
        for key, label in kinds
    ]
    return render(
        request,
        'notifications_center/preferences.html',
        {'kinds': rows, 'active_nav': 'notifications'},
    )


@staff_member_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
def api_latest(request: HttpRequest) -> JsonResponse:
    """JSON endpoint feeding the topbar bell dropdown.

    GET            → latest 10 inbox notifications + the unread counts
    GET ?counts=1  → the unread counts only (the bell polls this)
    POST id=…      → mark one notification read
    """
    if request.method == 'POST':
        nid = (request.POST.get('id') or '').strip()
        n = services.own(request.user, nid)
        if n is not None:
            services.apply(n, 'read')
        return JsonResponse({'ok': True, **services.unread_counts(request.user)})
    counts = services.unread_counts(request.user)
    if request.GET.get('counts'):
        return JsonResponse(counts)
    rows = services.latest_for(request.user, limit=10)
    return JsonResponse({**counts, 'notifications': [services.as_dict(n) for n in rows]})
