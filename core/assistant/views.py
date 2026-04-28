"""Assistant HTTP surface.

Mounted in the project URLconf at `/dashboard/assistant/` so it's reachable
even if the entire plugin layer fails to load.
"""
from __future__ import annotations

import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from core.assistant.persistence import get_default_store
from core.assistant.runtime import Assistant

logger = logging.getLogger('morpheus.assistant.views')


def _conversation_key(request) -> str:
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return f'user:{user.pk}'
    if hasattr(request, 'session'):
        if not request.session.session_key:
            request.session.save()
        return f'session:{request.session.session_key}'
    return 'anon'


@staff_member_required
def assistant_page(request):
    """Standalone Assistant page (full-screen chat)."""
    store = get_default_store()
    history = store.history(conversation_key=_conversation_key(request), limit=50)
    return render(request, 'assistant/page.html', {
        'history': history,
        'active_nav': 'assistant',
    })


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def assistant_invoke(request):
    """POST {message: str} → JSON RunResult. Always responds — never 500s."""
    try:
        body = json.loads(request.body or b'{}') if request.content_type == 'application/json' \
            else dict(request.POST.items())
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON.')
    message = (body.get('message') or '').strip()
    if not message:
        return HttpResponseBadRequest('Missing `message`.')

    try:
        result = Assistant().run(
            message=message[:10_000],
            conversation_key=_conversation_key(request),
            context={'request': request, 'user': getattr(request, 'user', None)},
        )
    except Exception as e:  # noqa: BLE001 — last-resort safety net
        logger.error('assistant: run crashed: %s', e, exc_info=True)
        return JsonResponse({
            'state': 'failed', 'text': '', 'error': str(e), 'tool_calls': 0,
        }, status=200)

    return JsonResponse({
        'state': result.state,
        'text': result.text,
        'error': result.error,
        'tool_calls': result.tool_call_count,
        'duration_ms': result.duration_ms,
        'tokens': {
            'prompt': result.prompt_tokens, 'completion': result.completion_tokens,
        },
    })


@staff_member_required
def assistant_history(request):
    """JSON history of the current conversation — used by the floating widget."""
    store = get_default_store()
    history = store.history(conversation_key=_conversation_key(request), limit=30)
    return JsonResponse({
        'messages': [
            {'role': m.role, 'content': m.content,
             'tool_name': m.tool_name, 'at': m.at}
            for m in history
        ],
    })
