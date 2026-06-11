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
    page itself opens fresh every time, like a new browser tab.

    Suggested follow-up prompts ("starters") render as chips ABOVE the
    chat form. They prefill the textarea on click; the same set updates
    contextually after Linda's first response (handled in the JS).
    """
    memories: list = []
    try:
        from core.assistant.models import LindaMemory

        memories = list(LindaMemory.objects.all()[:20])
    except Exception:  # noqa: BLE001, S110
        pass

    # Suggested first prompts — same set used by the floating widget. After
    # the first turn, the JS swaps in context-aware follow-ups.
    starters = [
        'Show me a snapshot of the store right now',
        'Which products are low on stock?',
        'Top 5 customers by lifetime spend',
        'Pending returns I need to look at',
        'Summarise this week vs last week',
    ]

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
            'starters': starters,
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
def assistant_invoke(request):
    """POST {message: str} → JSON RunResult. Always responds — never 500s."""
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

    try:
        result = Assistant().run(
            message=message[:10_000],
            conversation_key=_conversation_key(request),
            context={
                'request': request,
                'user': getattr(request, 'user', None),
                # Page-scoped affordance: the floating widget on each
                # dashboard page sends the URL + title it was opened
                # from so Linda can answer about "this page" without
                # needing the merchant to re-paste a slug or order
                # number. The Assistant runtime threads these into
                # the system prompt prefix.
                'page_url': (body.get('page_url') or '')[:512],
                'page_title': (body.get('page_title') or '')[:200],
                # Mode picker — selects which subset of tools Linda
                # is allowed to dispatch this turn (core/assistant/
                # modes.py). Falls back to "general" (wildcard).
                'mode': (body.get('mode') or '')[:32],
            },
        )
    except Exception as e:  # noqa: BLE001 — last-resort safety net
        logger.error('assistant: run crashed: %s', e, exc_info=True)
        return JsonResponse(
            {
                'state': 'failed',
                'text': '',
                'error': str(e),
                'tool_calls': 0,
            },
            status=200,
        )

    return JsonResponse(
        {
            'state': result.state,
            'text': result.text,
            'error': result.error,
            'tool_calls': result.tool_call_count,
            'duration_ms': result.duration_ms,
            'tokens': {
                'prompt': result.prompt_tokens,
                'completion': result.completion_tokens,
            },
        }
    )


@staff_member_required
@csrf_protect
@require_http_methods(['POST'])
def assistant_stream(request):
    """POST {message: str} → text/event-stream of run events.

    Yields newline-terminated SSE blocks. Each event:

      data: {"type": "tool_call_started", "name": "...", "arguments": {...}}\\n\\n
      data: {"type": "tool_call_finished", "name": "...", "output": ..., "error": "..."}\\n\\n
      data: {"type": "assistant_text", "text": "..."}\\n\\n
      data: {"type": "final", "text": "...", "state": "completed", ...}\\n\\n

    Falls through to the JSON variant when the client doesn't request
    SSE — same Linda runtime under the hood.
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
                    # Same page-scoped affordance as the JSON invoke
                    # path: the widget sends the URL + title of the
                    # page it was opened from so Linda can answer
                    # about "this product / this order / this page".
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
    store = get_default_store()
    history = store.history(conversation_key=_conversation_key(request), limit=30)
    return JsonResponse(
        {
            'messages': [
                {'role': m.role, 'content': m.content, 'tool_name': m.tool_name, 'at': m.at}
                for m in history
            ],
        }
    )
