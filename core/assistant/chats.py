"""Linda's chats: every conversation a staff member had, to reopen and continue.

Each chat is its own ``AssistantConversation``: its own key, so its own Janus
session and its own consent context (an "ok" in one chat never approves a
change proposed in another), owned by one staff user and checked here on every
read and write — a chat id from the browser is never trusted on its own. The
floating widget keeps the one running thread it always had (key
``user:<pk>``), which is listed as a chat too.
"""

from __future__ import annotations

import uuid

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Max
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.assistant.models import AssistantConversation

TITLE_MAX = 80


def thread_key(user) -> str:
    """The widget's running thread — one per staff member."""
    return f'user:{user.pk}'


def running_thread(user) -> AssistantConversation:
    """The widget's thread, owned by its user (rows from before chats had no owner)."""
    conv, _ = AssistantConversation.objects.get_or_create(
        key=thread_key(user), defaults={'user': user}
    )
    if conv.user_id is None:
        conv.user = user
        conv.save(update_fields=['user', 'updated_at'])
    return conv


def start_chat(user, first_message: str) -> AssistantConversation:
    """A new chat, titled by its first message."""
    return AssistantConversation.objects.create(
        key=f'user:{user.pk}:chat:{uuid.uuid4().hex[:16]}',
        user=user,
        title=' '.join(first_message.split())[:TITLE_MAX],
    )


def owned_chat(user, chat_id) -> AssistantConversation:
    """The chat `chat_id` when it is `user`'s; 404 otherwise — never someone else's."""
    try:
        uuid.UUID(str(chat_id))
    except ValueError as e:
        raise Http404 from e
    conv = AssistantConversation.objects.filter(pk=chat_id, user=user).first()
    if conv is None:
        raise Http404
    return conv


def chats_for(user, *, archived: bool = False):
    """`user`'s chats with at least one message, most recent first."""
    if not archived:
        AssistantConversation.objects.filter(key=thread_key(user), user__isnull=True).update(
            user=user
        )
    return (
        AssistantConversation.objects.filter(user=user, archived=archived)
        .annotate(last_at=Max('messages__created_at'), message_count=Count('messages'))
        .filter(message_count__gt=0)
        .order_by('-last_at')
    )


def transcript(conv: AssistantConversation, limit: int = 100) -> list[dict]:
    """What the chat page shows when a chat is reopened: the words, not the tool rows."""
    rows = conv.messages.filter(role__in=('user', 'assistant')).order_by('-created_at')[:limit]
    return [{'role': m.role, 'content': m.content} for m in reversed(list(rows))]


@staff_member_required
def chats_page(request):
    archived = request.GET.get('archived') == '1'
    return render(
        request,
        'assistant/chats.html',
        {
            'chats': chats_for(request.user, archived=archived),
            'archived': archived,
            'thread_key': thread_key(request.user),
            'active_nav': 'assistant',
        },
    )


@staff_member_required
@require_POST
def chat_action(request, chat_id, action: str):
    conv = owned_chat(request.user, chat_id)
    back = '/dashboard/assistant/chats/'
    if action == 'rename':
        title = ' '.join((request.POST.get('title') or '').split())[:200]
        if title:
            conv.title = title
            conv.save(update_fields=['title', 'updated_at'])
    elif action == 'archive':
        conv.archived = True
        conv.save(update_fields=['archived', 'updated_at'])
    elif action == 'unarchive':
        conv.archived = False
        conv.save(update_fields=['archived', 'updated_at'])
        back += '?archived=1'
    else:
        raise Http404
    return redirect(back)
