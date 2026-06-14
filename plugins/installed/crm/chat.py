"""Customer-support live chat — service layer.

Storefront widget → customer messages; CRM inbox → staff replies. Anonymous
visitors who leave an email are captured as CRM Leads, so the chat feeds the
pipeline (this is why it lives in the CRM app).
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.crm.chat')


def thread_by_id(thread_id: str):
    """Look up a thread by id, returning None for empty/malformed UUIDs (never
    raises ValidationError — the public endpoints accept untrusted input)."""
    tid = (thread_id or '').strip()
    if not tid:
        return None
    from django.core.exceptions import ValidationError

    from plugins.installed.crm.models import ChatThread

    try:
        return ChatThread.objects.filter(id=tid).first()
    except (ValueError, ValidationError):
        return None


def resolve_thread(request, thread_id: str = '', email: str = ''):
    """Find the customer's current thread (by id, then by logged-in customer),
    or create a new one. Returns the ChatThread."""
    from plugins.installed.crm.models import ChatThread

    user = request.user if getattr(request.user, 'is_authenticated', False) else None
    if thread_id:
        t = thread_by_id(thread_id)
        if t is not None:
            return t
    if user is not None:
        t = (
            ChatThread.objects.filter(customer=user, status='open')
            .order_by('-last_message_at')
            .first()
        )
        if t is not None:
            return t

    session_key = request.session.session_key or ''
    if not session_key:
        request.session.save()
        session_key = request.session.session_key or ''

    thread = ChatThread.objects.create(
        customer=user,
        email=(email or '').strip()[:254],
        session_key=session_key,
    )
    _link_lead(thread)
    return thread


def _link_lead(thread) -> None:
    """Capture an anonymous emailer as a CRM Lead (chat → pipeline)."""
    if thread.customer_id or not thread.email:
        return
    try:
        from plugins.installed.crm.models import Lead

        lead, _ = Lead.objects.get_or_create(
            email=thread.email, defaults={'source': 'other', 'status': 'new'}
        )
        thread.lead = lead
        thread.save(update_fields=['lead'])
    except Exception:  # noqa: BLE001, S110 — lead linkage is best-effort
        pass


def post_customer_message(thread, body: str):
    """Append a customer message; reopen + flag unread for staff. Notifies staff
    by email only on the 0→1 unread transition (a 'now needs attention' edge)."""
    from django.utils import timezone

    from plugins.installed.crm.models import ChatMessage

    was_unread = thread.unread_staff or 0
    msg = ChatMessage.objects.create(thread=thread, sender='customer', body=body[:5000])
    thread.unread_staff = was_unread + 1
    thread.status = 'open'
    thread.last_message_at = timezone.now()
    thread.save(update_fields=['unread_staff', 'status', 'last_message_at'])
    if was_unread == 0:
        _notify_staff(thread, msg)
    return msg


def _notify_staff(thread, msg) -> None:
    """Email active staff that a support thread needs a reply. Best-effort."""
    try:
        from django.contrib.auth import get_user_model

        from core.emails import send_templated_email
        from core.utils.site import site_base_url

        emails = list(
            dict.fromkeys(
                get_user_model()
                .objects.filter(is_staff=True, is_active=True)
                .exclude(email='')
                .values_list('email', flat=True)[:25]
            )
        )
        url = f'{site_base_url()}/dashboard/crm/chat/{thread.id}/'
        for email in emails:
            send_templated_email(
                'crm_support_new_message',
                to=email,
                subject=f'New support message from {thread.display_name()}',
                ctx={'thread': thread, 'preview': (msg.body or '')[:200], 'url': url},
            )
    except Exception as e:  # noqa: BLE001 — notification must never break the chat
        logger.warning('crm.chat: staff notify failed: %s', e)


def post_staff_reply(thread, body: str, staff_user=None):
    """Append a staff reply; clear the unread flag."""
    from django.utils import timezone

    from plugins.installed.crm.models import ChatMessage

    msg = ChatMessage.objects.create(
        thread=thread, sender='staff', staff_user=staff_user, body=body[:5000]
    )
    thread.unread_staff = 0
    thread.last_message_at = timezone.now()
    thread.save(update_fields=['unread_staff', 'last_message_at'])
    return msg
