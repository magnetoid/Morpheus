"""Assistant HTTP surface.

Mounted in the project URLconf at `/dashboard/assistant/` so it's reachable
even if the entire plugin layer fails to load.
"""

from __future__ import annotations

import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseBadRequest, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from core.assistant.page_help import build_page_help
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
    """Standalone Linda page — full-screen chat.

    Always starts with a clean conversation — prior session messages are NOT
    pre-loaded into the chat area. The merchant can reach previous turns via
    the conversation history API (``/dashboard/assistant/history/``); the
    page itself opens fresh every time, like a new browser tab. No suggested
    prompts: the owner had them removed (2026-10-09).
    """
    memories: list = []
    try:
        from core.assistant.models import LindaMemory

        memories = list(LindaMemory.objects.all()[:20])
    except Exception:  # noqa: BLE001, S110
        pass

    # Tool-palette modes shown as chips at the top of the page. The
    # JS picks one (default 'general'), threads it into every stream
    # POST, and Linda's tool catalogue is filtered server-side.
    from core.assistant.modes import DEFAULT_MODE, MODES

    return render(
        request,
        'assistant/page.html',
        {
            # Intentionally empty — the redesigned page starts clean.
            'history': [],
            'memories': memories,
            'assistant_modes': [
                {'slug': m.slug, 'label': m.label, 'description': m.description, 'icon': m.icon}
                for m in MODES
            ],
            'default_mode': DEFAULT_MODE,
            'active_nav': 'assistant',
        },
    )


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def assistant_stream(request):
    """POST {message: str} → text/event-stream of run events.

    Yields newline-terminated SSE blocks. Each event:

      data: {"type": "progress", "elapsed_s": 5}\\n\\n          (every few seconds)
      data: {"type": "tool_call_started", "name": "...", "arguments": {...}}\\n\\n
      data: {"type": "tool_call_finished", "name": "...", "output": ..., "error": ""}\\n\\n
      data: {"type": "assistant_text", "text": "..."}\\n\\n
      data: {"type": "final", "text": "...", "state": "completed", ...}\\n\\n
    """
    try:
        body = (
            json.loads(request.body or b'{}')
            if request.content_type == 'application/json'
            else dict(request.POST.items())
        )
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON.')
    message = (body.get('message') or '').strip()
    if not message:
        return HttpResponseBadRequest('Missing `message`.')

    user = getattr(request, 'user', None)
    conv_key = _conversation_key(request)

    page_url = (body.get('page_url') or '')[:512]
    page_title = (body.get('page_title') or '')[:200]
    mode = (body.get('mode') or '')[:32]

    def _event_stream():
        # Outer try: a crash anywhere should still close the stream cleanly.
        try:
            for ev in Assistant().stream(
                message=message[:10_000],
                conversation_key=conv_key,
                context={
                    'user': user,
                    # The Janus engine derives its MCP callback URL from the
                    # request when no LINDA_MCP_URL is configured; without this
                    # it falls back to a hardcoded loopback host.
                    'request': request,
                    # The widget sends the URL + title of the page it was
                    # opened from so Linda can answer about "this product /
                    # this order / this page".
                    'page_url': page_url,
                    'page_title': page_title,
                    'mode': mode,
                },
            ):
                # Final/error events carry an AssistantRunResult which isn't
                # JSON-serialisable — flatten to dict before sending.
                if ev.get('type') in ('final', 'error') and ev.get('result') is not None:
                    r = ev['result']
                    payload = {
                        'type': ev['type'],
                        'text': r.text,
                        'state': r.state,
                        'error': r.error,
                        'tool_calls': r.tool_call_count,
                        'duration_ms': r.duration_ms,
                    }
                else:
                    payload = ev
                yield f'data: {json.dumps(payload, default=str)}\n\n'
        except Exception as e:  # noqa: BLE001
            logger.error('assistant: stream crashed: %s', e, exc_info=True)
            yield f'data: {json.dumps({"type": "error", "error": str(e), "state": "failed", "text": ""})}\n\n'

    response = StreamingHttpResponse(_event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # nginx: don't buffer SSE
    return response


@staff_member_required
def assistant_history(request):
    """JSON history of the current conversation — used by the floating widget."""
    key = _conversation_key(request)
    store = get_default_store()
    history = store.history(conversation_key=key, limit=30)
    return JsonResponse(
        {
            'messages': [
                {'role': m.role, 'content': m.content, 'tool_name': m.tool_name, 'at': m.at}
                for m in history
            ],
            'summary': _conversation_cost_summary(key),
        }
    )


def _conversation_cost_summary(key: str) -> dict:
    """Tokens + estimated USD for the conversation. Empty when DB-less."""
    try:
        from core.assistant.models import AssistantConversation

        conv = AssistantConversation.objects.filter(key=key).first()
        return conv.cost_summary() if conv else {}
    except Exception:  # noqa: BLE001, S110 — cost display must never break history
        return {}


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def assistant_page_help(request):
    """POST page context → JSON {ok, summary, numbers, actions, message}.
    Always responds 200 with JSON (dashboard AJAX contract)."""
    try:
        body = (
            json.loads(request.body or b'{}')
            if request.content_type == 'application/json'
            else dict(request.POST.items())
        )
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON.')

    context = {
        'page_title': (body.get('page_title') or '')[:200],
        'page_url': (body.get('page_url') or '')[:512],
        'page_text': (body.get('page_text') or '')[:8000],
        'structured': body.get('structured') if isinstance(body.get('structured'), dict) else None,
    }
    try:
        result = build_page_help(context)
    except Exception as e:  # noqa: BLE001 — last-resort safety net
        logger.error('assistant: page_help crashed: %s', e, exc_info=True)
        return JsonResponse(
            {
                'ok': False,
                'summary': '',
                'numbers': [],
                'actions': [],
                'message': 'Linda is unavailable right now.',
            },
            status=200,
        )
    return JsonResponse(result, status=200)
