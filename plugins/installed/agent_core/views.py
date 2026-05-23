"""
agent_core HTTP views.

* `/api/agents/<name>/invoke` — POST a user message, get a JSON RunResult.
* `/api/agents/<name>/stream` — POST + Server-Sent Events for live runs.
* `/dashboard/agents/` — list runs.
* `/dashboard/agents/<run_id>/` — single run trace.
"""
from __future__ import annotations

import json
import logging
from queue import Empty, Queue
from threading import Thread
from typing import Any

from morpheus.views import staff_member_required
from morpheus.views import HttpResponseBadRequest, JsonResponse, StreamingHttpResponse
from morpheus.views import get_object_or_404, render
from morpheus.views import csrf_exempt
from morpheus.views import require_http_methods

from core.agents import agent_registry
from plugins.installed.agent_core.services import (
    history_for_conversation,
    run_agent,
)

logger = logging.getLogger('morpheus.agents.views')


def _decode_body(request) -> dict[str, Any]:
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            return {}
    return dict(request.POST.items())


def _check_audience(request, agent_name: str):
    """Audience-policy gate. Returns a JsonResponse on denial, else None.

    - audience='system'      → never invokable via HTTP
    - audience='merchant'    → must be authenticated + is_staff
    - audience='storefront'  → public (rate-limited via DRF middleware)
    - audience='any'         → public
    """
    agent = agent_registry.get_agent(agent_name)
    if agent is None:
        return JsonResponse({'error': f'Unknown agent: {agent_name}'}, status=404)
    if agent.audience == 'system':
        return JsonResponse({'error': 'System agents cannot be invoked via HTTP.'}, status=403)
    if agent.audience == 'merchant':
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated or not getattr(user, 'is_staff', False):
            return JsonResponse({'error': 'Staff authentication required.'}, status=403)
    return None


def _agent_rate_key(request):
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return f'agent:user:{user.pk}'
    return f'agent:ip:{request.META.get("REMOTE_ADDR", "0.0.0.0")}'


@csrf_exempt
@require_http_methods(['POST'])
def invoke_agent_view(request, agent_name: str):
    from core.utils.rate_limit import RateLimitExceeded, check_and_consume
    from morpheus.views import HttpResponse
    try:
        check_and_consume(key=_agent_rate_key(request), max_per_window=20, window_seconds=60)
    except RateLimitExceeded as e:
        resp = HttpResponse('Agent rate limit exceeded.', status=429)
        resp['Retry-After'] = str(e.retry_after)
        return resp

    denied = _check_audience(request, agent_name)
    if denied is not None:
        return denied
    body = _decode_body(request)
    message = (body.get('message') or '').strip()
    if not message:
        return HttpResponseBadRequest('Missing `message`.')

    conversation_id = body.get('conversation_id')
    history = history_for_conversation(conversation_id) if conversation_id else None

    try:
        result = run_agent(
            agent_name=agent_name,
            user_message=message[:10_000],
            customer=getattr(request, 'user', None),
            session_key=getattr(getattr(request, 'session', None), 'session_key', '') or '',
            history=history,
            context={'request': request},
            conversation_id=conversation_id,
        )
    except LookupError as e:
        return JsonResponse({'error': str(e)}, status=404)

    return JsonResponse({
        'run_id': result.run_id,
        'state': result.state,
        'text': result.text,
        'tool_calls': result.tool_calls,
        'tokens': {
            'prompt': result.trace.prompt_tokens,
            'completion': result.trace.completion_tokens,
        },
        'error': result.error or '',
    })


@csrf_exempt
@require_http_methods(['POST'])
def stream_agent_view(request, agent_name: str):
    """Server-Sent Events: live trace of a single run.

    The runtime executes on a worker thread; the view drains a queue and
    writes one event per `TraceStep` until the run finishes.
    """
    denied = _check_audience(request, agent_name)
    if denied is not None:
        return denied
    body = _decode_body(request)
    message = (body.get('message') or '').strip()
    if not message:
        return HttpResponseBadRequest('Missing `message`.')

    conversation_id = body.get('conversation_id')
    history = history_for_conversation(conversation_id) if conversation_id else None

    queue: Queue = Queue()
    final_box: dict[str, Any] = {}

    def _on_step(step):
        try:
            queue.put({
                'kind': step.kind,
                'name': step.name,
                'content': step.content,
                'arguments': step.arguments,
            })
        except Exception:  # noqa: BLE001
            pass

    def _runner():
        try:
            result = run_agent(
                agent_name=agent_name,
                user_message=message[:10_000],
                customer=getattr(request, 'user', None),
                session_key=getattr(getattr(request, 'session', None), 'session_key', '') or '',
                history=history,
                context={'request': request},
                conversation_id=conversation_id,
                on_step=_on_step,
            )
            final_box['result'] = result
        except Exception as e:  # noqa: BLE001
            final_box['error'] = str(e)
        finally:
            queue.put({'__done__': True})

    Thread(target=_runner, daemon=True).start()

    def _events():
        while True:
            try:
                event = queue.get(timeout=60)
            except Empty:
                yield ': keepalive\n\n'
                continue
            if event.get('__done__'):
                if 'result' in final_box:
                    payload = json.dumps({
                        'state': final_box['result'].state,
                        'text': final_box['result'].text,
                        'run_id': final_box['result'].run_id,
                    })
                    yield f'event: final\ndata: {payload}\n\n'
                else:
                    yield f'event: error\ndata: {json.dumps({"error": final_box.get("error", "")})}\n\n'
                return
            yield f'event: step\ndata: {json.dumps(event)}\n\n'

    response = StreamingHttpResponse(_events(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@require_http_methods(['GET'])
def list_agents_view(request):
    """Public catalog: which agents are registered, their audience + description."""
    out = []
    for a in agent_registry.all_agents():
        out.append({
            'name': a.name,
            'label': a.label,
            'description': a.description,
            'audience': a.audience,
            'icon': a.icon,
            'scopes': list(a.scopes),
        })
    return JsonResponse({'agents': out})


@staff_member_required
def runs_dashboard_view(request):
    from plugins.installed.agent_core.models import AgentRun

    runs = AgentRun.objects.all().order_by('-started_at')[:100]
    return render(request, 'agent_core/dashboard/runs.html', {
        'runs': runs,
        'agents': agent_registry.all_agents(),
        'active_nav': 'agents',
        'breadcrumb_trail': [
            {'label': 'Dashboard', 'url': '/dashboard/'},
            {'label': 'Linda',     'url': '/dashboard/assistant/'},
            {'label': 'Activity'},
        ],
    })


@staff_member_required
def run_detail_view(request, run_id: str):
    from plugins.installed.agent_core.models import AgentRun

    run = get_object_or_404(AgentRun, id=run_id)
    return render(request, 'agent_core/dashboard/run_detail.html', {
        'run': run,
        'steps': run.steps.all().order_by('seq'),
        'active_nav': 'agents',
    })


@staff_member_required
def merchant_ops_chat_view(request):
    """The Merchant Ops chat console (admin only)."""
    active_provider = ''
    active_model = ''
    try:
        from plugins.installed.ai_assistant.services.config import get_provider_config
        cfg = get_provider_config()
        active_provider = cfg.provider
        active_model = cfg.model
    except Exception:  # noqa: BLE001
        pass
    return render(request, 'agent_core/dashboard/console.html', {
        'agent_name': 'worker',
        'active_provider': active_provider,
        'active_model': active_model,
        'active_nav': 'agents',
    })


@staff_member_required
def observability_view(request):
    """Aggregate per-agent stats over the last N days."""
    from datetime import timedelta
    from django.db.models import Avg, Count, Sum
    from django.utils import timezone
    from plugins.installed.agent_core.models import AgentRun, AgentStep

    try:
        days = max(1, min(int(request.GET.get('days') or 7), 90))
    except (TypeError, ValueError):
        days = 7
    since = timezone.now() - timedelta(days=days)

    runs = AgentRun.objects.filter(started_at__gte=since)
    by_agent = list(
        runs.values('agent_name').annotate(
            n=Count('id'),
            avg_ms=Avg('duration_ms'),
            tokens=Sum('prompt_tokens') + Sum('completion_tokens'),
            tools=Sum('tool_call_count'),
        ).order_by('-n')[:50]
    )
    by_state = list(
        runs.values('state').annotate(n=Count('id')).order_by('-n')
    )
    top_tools = list(
        AgentStep.objects.filter(
            run__started_at__gte=since, kind='tool_call',
        ).values('name').annotate(n=Count('id')).order_by('-n')[:25]
    )
    failures = list(
        runs.filter(state='failed').order_by('-started_at')[:25]
    )
    totals = runs.aggregate(
        n=Count('id'),
        tokens=Sum('prompt_tokens') + Sum('completion_tokens'),
        tools=Sum('tool_call_count'),
        avg_ms=Avg('duration_ms'),
    )
    return render(request, 'agent_core/dashboard/observability.html', {
        'days': days,
        'totals': totals,
        'by_agent': by_agent,
        'by_state': by_state,
        'top_tools': top_tools,
        'failures': failures,
        'active_nav': 'agents',
        'breadcrumb_trail': [
            {'label': 'Dashboard', 'url': '/dashboard/'},
            {'label': 'Linda',     'url': '/dashboard/assistant/'},
            {'label': 'Insights'},
        ],
    })


@staff_member_required
def background_agents_view(request):
    from morpheus.views import redirect
    from django.utils import timezone
    from plugins.installed.agent_core.models import BackgroundAgent

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        agent_name = (request.POST.get('agent_name') or '').strip()
        prompt = (request.POST.get('prompt') or '').strip()
        try:
            interval = max(60, int(request.POST.get('interval_seconds') or 3600))
        except (TypeError, ValueError):
            interval = 3600
        if name and agent_name and prompt:
            BackgroundAgent.objects.create(
                name=name[:120], agent_name=agent_name[:100],
                prompt=prompt[:50_000], interval_seconds=interval,
                next_run_at=timezone.now(),
                created_by=request.user if request.user.is_authenticated else None,
            )
        return redirect('/dashboard/agents/background/')

    rows = BackgroundAgent.objects.all().order_by('-updated_at')[:200]
    return render(request, 'agent_core/dashboard/background.html', {
        'background_agents': rows,
        'agents': agent_registry.all_agents(),
        'active_nav': 'agents',
        'breadcrumb_trail': [
            {'label': 'Dashboard', 'url': '/dashboard/'},
            {'label': 'Linda',     'url': '/dashboard/assistant/'},
            {'label': 'Automations'},
        ],
    })


@staff_member_required
def background_agent_action_view(request, bg_id: str, action: str):
    from morpheus.views import redirect
    from django.utils import timezone
    from plugins.installed.agent_core.models import BackgroundAgent
    from plugins.installed.agent_core.scheduler import fire

    bg = get_object_or_404(BackgroundAgent, id=bg_id)
    if request.method != 'POST':
        return redirect('/dashboard/agents/background/')
    if action == 'pause':
        bg.state = BackgroundAgent.STATE_PAUSED
        bg.save(update_fields=['state', 'updated_at'])
    elif action == 'resume':
        bg.state = BackgroundAgent.STATE_ACTIVE
        bg.consecutive_failures = 0
        bg.next_run_at = timezone.now()
        bg.save(update_fields=['state', 'consecutive_failures', 'next_run_at', 'updated_at'])
    elif action == 'run-now':
        fire(bg)
    elif action == 'delete':
        bg.delete()
    return redirect('/dashboard/agents/background/')
