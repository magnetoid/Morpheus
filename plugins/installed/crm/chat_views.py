"""Customer-support chat — public storefront endpoints + CRM inbox views."""

from __future__ import annotations

from django.contrib import messages as flash
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


def _msg_json(m):
    return {'id': str(m.id), 'sender': m.sender, 'body': m.body, 'at': m.created_at.isoformat()}


# ── Public (storefront widget) ──────────────────────────────────────────────


@csrf_exempt
@require_http_methods(['POST'])
def chat_send(request):
    """Customer sends a message. CSRF-exempt public capture (like the analytics
    beacon / newsletter): creates only a support thread, no privileged action."""
    from plugins.installed.crm.chat import post_customer_message, resolve_thread

    body = (request.POST.get('message') or '').strip()
    if not body:
        return JsonResponse({'ok': False, 'error': 'Empty message.'}, status=400)
    thread = resolve_thread(
        request,
        thread_id=(request.POST.get('thread') or '').strip(),
        email=(request.POST.get('email') or '').strip(),
    )
    msg = post_customer_message(thread, body)
    return JsonResponse({'ok': True, 'thread': str(thread.id), 'message': _msg_json(msg)})


@require_http_methods(['GET'])
def chat_poll(request):
    """Customer widget polls for replies. Knowing the thread UUID is the
    capability (unguessable); returns messages, optionally only after a time."""
    from plugins.installed.crm.chat import thread_by_id

    thread = thread_by_id(request.GET.get('thread') or '')
    if thread is None:
        return JsonResponse({'ok': True, 'messages': []})
    qs = thread.messages.all()
    after = (request.GET.get('after') or '').strip()
    if after:
        qs = qs.filter(created_at__gt=after)
    return JsonResponse(
        {'ok': True, 'thread': str(thread.id), 'messages': [_msg_json(m) for m in qs]}
    )


# ── Dashboard (CRM inbox) ───────────────────────────────────────────────────


@staff_member_required
def chat_inbox(request):
    from plugins.installed.crm.models import ChatThread

    status = request.GET.get('status') or 'open'
    qs = ChatThread.objects.select_related('customer', 'lead')
    if status in ('open', 'closed'):
        qs = qs.filter(status=status)
    threads = qs.annotate(n=Count('messages'))[:100]
    counts = {
        'open': ChatThread.objects.filter(status='open').count(),
        'unread': ChatThread.objects.filter(unread_staff__gt=0).count(),
    }
    return render(
        request,
        'crm/chat/inbox.html',
        {
            'threads': threads,
            'counts': counts,
            'status': status,
            'active_nav': 'customers',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'CRM', 'url': '/dashboard/crm/'},
                {'label': 'Support chat'},
            ],
        },
    )


@staff_member_required
def chat_thread(request, thread_id):
    from plugins.installed.crm.chat import post_staff_reply
    from plugins.installed.crm.models import ChatThread

    thread = get_object_or_404(ChatThread.objects.select_related('customer', 'lead'), id=thread_id)

    if request.method == 'POST':
        action = request.POST.get('action') or 'reply'
        if action == 'reply':
            body = (request.POST.get('body') or '').strip()
            if body:
                post_staff_reply(thread, body, staff_user=request.user)
        elif action == 'close':
            thread.status = 'closed'
            thread.save(update_fields=['status'])
            flash.success(request, 'Thread closed.')
        elif action == 'reopen':
            thread.status = 'open'
            thread.save(update_fields=['status'])
        return redirect(f'/dashboard/crm/chat/{thread.id}/')

    # Opening the thread clears the staff-unread flag.
    if thread.unread_staff:
        thread.unread_staff = 0
        thread.save(update_fields=['unread_staff'])

    return render(
        request,
        'crm/chat/thread.html',
        {
            'thread': thread,
            'messages': thread.messages.all(),
            'active_nav': 'customers',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'CRM', 'url': '/dashboard/crm/'},
                {'label': 'Support chat', 'url': '/dashboard/crm/chat/'},
                {'label': thread.display_name()},
            ],
        },
    )
