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
import re
from queue import Empty, Queue
from threading import Thread
from typing import Any

from core.auth.csrf import csrf_exempt_for_bearer
from core.authz import require_capability
from morpheus.app.views import (
    HttpResponseBadRequest,
    JsonResponse,
    StreamingHttpResponse,
    get_object_or_404,
    render,
    require_http_methods,
    staff_member_required,
)
from morpheus.core import agent_registry
from plugins.installed.agent_core.services import (
    history_for_conversation,
    run_agent,
)

logger = logging.getLogger('morpheus.agents.views')

# One journal line as tools/memory_tool.py:append_daily_snapshot writes it:
# "- `HH:MM` **MEMORY** added: <text>".
JANUS_JOURNAL_LINE_RE = re.compile(
    r'^- `([^`]*)` \*\*(MEMORY|USER)\*\* (added|updated|removed): (.*)$'
)
# How many journal days to read when building the activity feed.
JANUS_ACTIVITY_DAYS = 90


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
    - audience='any'         → staff too: see services.invocation_denial
    """
    from plugins.installed.agent_core.services import invocation_denial

    agent = agent_registry.get_agent(agent_name)
    if agent is None:
        return JsonResponse({'error': f'Unknown agent: {agent_name}'}, status=404)
    reason = invocation_denial(agent, request)
    if reason:
        return JsonResponse({'error': reason}, status=403)
    return None


def _agent_rate_key(request):
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return f'agent:user:{user.pk}'
    return f'agent:ip:{request.META.get("REMOTE_ADDR", "0.0.0.0")}'  # noqa: S104  # nosec B104


@csrf_exempt_for_bearer
@require_http_methods(['POST'])
def invoke_agent_view(request, agent_name: str):
    from core.utils.rate_limit import RateLimitExceeded, check_and_consume
    from morpheus.app.views import HttpResponse

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

    return JsonResponse(
        {
            'run_id': result.run_id,
            'state': result.state,
            'text': result.text,
            'tool_calls': result.tool_calls,
            'tokens': {
                'prompt': result.trace.prompt_tokens,
                'completion': result.trace.completion_tokens,
            },
            'error': result.error or '',
        }
    )


@csrf_exempt_for_bearer
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
        try:  # noqa: SIM105
            queue.put(
                {
                    'kind': step.kind,
                    'name': step.name,
                    'content': step.content,
                    'arguments': step.arguments,
                }
            )
        except Exception:  # noqa: BLE001, S110
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
                    payload = json.dumps(
                        {
                            'state': final_box['result'].state,
                            'text': final_box['result'].text,
                            'run_id': final_box['result'].run_id,
                        }
                    )
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
        out.append(
            {
                'name': a.name,
                'label': a.label,
                'description': a.description,
                'audience': a.audience,
                'icon': a.icon,
                'scopes': list(a.scopes),
            }
        )
    return JsonResponse({'agents': out})


@staff_member_required
@require_capability('system.read')
def runs_dashboard_view(request):
    from django.core.paginator import Paginator

    from plugins.installed.agent_core.models import AgentRun

    qs = AgentRun.objects.select_related('customer').order_by('-started_at')

    state = (request.GET.get('state') or '').strip()
    filter_agent = (request.GET.get('agent') or '').strip()
    query = (request.GET.get('q') or '').strip()
    if state:
        qs = qs.filter(state=state)
    if filter_agent:
        qs = qs.filter(agent_name=filter_agent)
    if query:
        qs = qs.filter(user_message__icontains=query)

    paginator = Paginator(qs, 50)
    try:
        page_number = max(1, int(request.GET.get('page') or 1))
    except (TypeError, ValueError):
        page_number = 1
    runs = paginator.get_page(page_number)

    # Distinct names + states for the filter controls (cheap, indexed).
    agent_names = list(
        AgentRun.objects.order_by('agent_name').values_list('agent_name', flat=True).distinct()
    )
    states = [s for s, _ in AgentRun.STATE_CHOICES]

    return render(
        request,
        'agent_core/dashboard/runs.html',
        {
            'runs': runs,
            'agents': agent_registry.all_agents(),
            'agent_names': agent_names,
            'states': states,
            'state': state,
            'filter_agent': filter_agent,
            'q': query,
            'janus_learned': _janus_learning_summary(),
            'janus_activity': _janus_activity_log(),
            'learned_skills': _learned_skills_summary(),
            'active_nav': 'agents',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Linda', 'url': '/dashboard/assistant/'},
                {'label': 'Activity'},
            ],
        },
    )


def _janus_learning_summary() -> dict:
    """Read-only snapshot of what Janus has learned (the real Janus activity).

    Mirrors the review card on Settings → AI → Janus, but surfaced here as a
    compact activity summary. Never raises — a sync glitch must not break the
    activity page.
    """
    from core.assistant import janus_learning

    try:
        return {
            'notes': janus_learning.notes(),
            'skills': janus_learning.skills(),
            'lessons': janus_learning.lesson_count(),
        }
    except Exception:  # noqa: BLE001
        logger.warning('runs dashboard: janus learning summary failed', exc_info=True)
        return {'notes': {'store': [], 'user': []}, 'skills': [], 'lessons': 0}


def _learned_skills_summary() -> list:
    """LearnedSkill rows (Linda-authored skills) with use/outcome feedback."""
    from core.assistant.models import LearnedSkill

    try:
        return list(LearnedSkill.objects.order_by('-uses', '-updated_at')[:20])
    except Exception:  # noqa: BLE001
        logger.warning('runs dashboard: learned skills summary failed', exc_info=True)
        return []


def _janus_activity_log(limit: int = 60) -> dict:
    """What the engine has been doing, as one chronological feed.

    Three sources, none of which the activity page showed as a timeline before:

    * **Journal entries** — ``JanusLearning`` rows at ``memories/daily/<date>.md``,
      one line per memory change, exactly as the ``memory_tool`` appends them:
      ``- `HH:MM` **MEMORY** added: <text>``. This is the real "what Janus
      learned, when" log, and it survives redeploys because it lives in the DB.
    * **Learning audit** — the dotted-slug rows ``janus_learning`` writes whenever
      a chat turn stores or forgets learning (``janus.learned``,
      ``janus.learning_forgotten``). These carry the actor and the paths.
    * **Tool calls** — ``agents.decision`` audit rows: every tool invocation with
      its arguments, output and errors (written by ``core.audit.agent_decision``).

    Note the tool-call rows are **not Janus-only**. The ``metadata.agent`` field
    names the caller, and in practice most come from ``worker`` runs, which reach
    the store through the agent runtime and never touch
    :mod:`core.assistant.janus_learning`. So the journal and learning rows read as
    Janus's own record, while the tool rows read as the wider agent's — the event
    carries its agent name so the distinction stays visible.

    Merged and sorted newest-first so the page reads as a single feed. Never
    raises: a missing table or one malformed line must not break the dashboard.
    Errors are flagged, because a failed call is the most useful line on the page.
    """
    from core.assistant.models import JanusLearning

    events: list[dict] = []

    try:
        rows = (
            JanusLearning.objects.filter(scope='', kind='journal')
            .order_by('-path')
            .values_list('path', 'content', 'updated_at')[:JANUS_ACTIVITY_DAYS]
        )
        for path, content, updated_at in rows:
            day = path.rsplit('/', 1)[-1].removesuffix('.md')
            for raw_line in (content or '').splitlines():
                line = raw_line.strip()
                if not line.startswith('- `'):
                    continue
                match = JANUS_JOURNAL_LINE_RE.match(line)
                if not match:
                    continue
                clock, kind, verb, text = match.groups()
                events.append(
                    {
                        'at': updated_at,
                        'day': day,
                        'clock': clock,
                        'kind': kind.lower(),
                        'verb': verb,
                        'text': text.strip()[:400],
                        'source': 'journal',
                    }
                )
    except Exception:  # noqa: BLE001
        logger.warning('runs dashboard: janus journal read failed', exc_info=True)

    try:
        from core.audit.models import AuditEvent

        for ev in AuditEvent.objects.filter(event_type__startswith='janus.').select_related(
            'actor'
        )[:limit]:
            events.append(
                {
                    'at': ev.created_at,
                    'day': ev.created_at.strftime('%Y-%m-%d'),
                    'clock': ev.created_at.strftime('%H:%M'),
                    'kind': 'audit',
                    'verb': ev.event_type,
                    'text': _describe_janus_audit(ev),
                    'source': 'audit',
                }
            )
    except Exception:  # noqa: BLE001
        logger.warning('runs dashboard: janus audit read failed', exc_info=True)

    try:
        from core.audit.models import AuditEvent

        for ev in AuditEvent.objects.filter(event_type='agents.decision').order_by('-created_at')[
            : limit * 2
        ]:
            meta = ev.metadata if isinstance(ev.metadata, dict) else {}
            tool = str(meta.get('tool') or '')
            output = meta.get('output')
            failed = _call_failed(output)
            events.append(
                {
                    'at': ev.created_at,
                    'day': ev.created_at.strftime('%Y-%m-%d'),
                    'clock': ev.created_at.strftime('%H:%M'),
                    'kind': 'tool',
                    'verb': tool.rsplit('__', maxsplit=1)[-1] if tool else 'tool',
                    'text': _describe_tool_call(meta, output, failed),
                    'source': 'tool',
                    'failed': failed,
                }
            )
    except Exception:  # noqa: BLE001
        logger.warning('runs dashboard: tool-call read failed', exc_info=True)

    try:
        # Refused writes: the MCP edge records every call the gate turned down
        # (consent not given, scope, mode). They never reached the tool-call
        # rows above, so a store with 83 refusals in a week showed none.
        from core.audit.models import AuditEvent

        for ev in AuditEvent.objects.filter(event_type='mcp.tool_denied').order_by('-created_at')[
            :limit
        ]:
            meta = ev.metadata if isinstance(ev.metadata, dict) else {}
            tool = (ev.target or '').removeprefix('tool/')
            reason = str(meta.get('reason') or '').strip().replace('\n', ' ')
            events.append(
                {
                    'at': ev.created_at,
                    'day': ev.created_at.strftime('%Y-%m-%d'),
                    'clock': ev.created_at.strftime('%H:%M'),
                    'kind': 'refused',
                    'verb': 'refused',
                    'text': f'{ev.actor_label or "mcp"} → {tool}: {reason}'[:400],
                    'source': 'audit',
                    'failed': False,
                    'refused': True,
                }
            )
    except Exception:  # noqa: BLE001
        logger.warning('runs dashboard: refusal read failed', exc_info=True)

    events.sort(key=lambda e: (e['day'], e['clock']), reverse=True)

    days = sorted({e['day'] for e in events}, reverse=True)
    shown = events[:limit]
    return {
        'events': shown,
        'total': len(events),
        'failed': sum(1 for e in events if e.get('failed')),
        'refused': sum(1 for e in events if e.get('refused')),
        'days': days,
        'active_days': len(days),
        'last_at': events[0]['at'] if events else None,
    }


def _call_failed(output) -> bool:
    """Both shapes a decision row's ``output`` has carried: the Worker's
    ``{'error': …}`` dict, and the string ``'error: …'`` the MCP edge wrote
    before v0.87.2 (Linda's calls)."""
    if isinstance(output, dict):
        return 'error' in output
    return isinstance(output, str) and output.startswith('error:')


def _call_error(output) -> str:
    if isinstance(output, dict):
        return str(output.get('error', ''))
    return str(output)[len('error:') :] if isinstance(output, str) else ''


def _refusals_since(since) -> int:
    """Writes the MCP edge turned down in the window (consent, scope, mode) —
    Linda's refusals, which no run row carries."""
    try:
        from core.audit.models import AuditEvent

        return AuditEvent.objects.filter(
            event_type='mcp.tool_denied', created_at__gte=since
        ).count()
    except Exception:  # noqa: BLE001
        return 0


def _describe_tool_call(meta: dict, output, failed: bool) -> str:
    """A one-line reading of an ``agents.decision`` tool call.

    Prefers the error when the call failed — that is the line worth reading —
    otherwise summarises the agent, arguments and result size.
    """
    agent = str(meta.get('agent') or '')
    parts = [f'{agent} →'] if agent else []
    if failed:
        err = _call_error(output).strip().replace('\n', ' ')
        parts.append(f'failed: {err[:220]}')
        return ' '.join(parts)
    args = meta.get('args') if isinstance(meta.get('args'), dict) else {}
    if args:
        shown = ', '.join(f'{k}={_short(v)}' for k, v in list(args.items())[:3])
        parts.append(shown)
    if isinstance(output, dict):
        for key in ('count', 'path', 'size', 'total'):
            if key in output:
                parts.append(f'{key}={_short(output[key])}')
                break
    return ' '.join(parts) or 'tool call'


def _short(value) -> str:
    text = str(value).replace('\n', ' ')
    return text if len(text) <= 60 else text[:57] + '…'


def _describe_janus_audit(ev) -> str:
    """A one-line, human reading of a ``janus.*`` audit row."""
    meta = ev.metadata if isinstance(ev.metadata, dict) else {}
    what = meta.get('what') or meta.get('skill') or ''
    if ev.event_type == 'janus.learned':
        paths = meta.get('paths') or []
        shown = ', '.join(str(p) for p in paths[:3])
        more = f' (+{len(paths) - 3} more)' if len(paths) > 3 else ''
        return f'stored learning: {shown}{more}' if shown else 'stored learning'
    if ev.event_type == 'janus.learning_forgotten':
        return f'forgot {what}' if what else 'forgot learning'
    return what or ev.target or ev.event_type


@staff_member_required
@require_capability('system.read')
def run_detail_view(request, run_id: str):
    from plugins.installed.agent_core.models import AgentRun

    run = get_object_or_404(AgentRun, id=run_id)
    return render(
        request,
        'agent_core/dashboard/run_detail.html',
        {
            'run': run,
            'steps': run.steps.all().order_by('seq'),
            'active_nav': 'agents',
        },
    )


@staff_member_required
@require_capability('system.read')
def merchant_ops_chat_view(request):
    """The Merchant Ops chat console (admin only)."""
    active_provider = ''
    active_model = ''
    try:
        from plugins.installed.ai_assistant.services.config import get_provider_config

        cfg = get_provider_config()
        active_provider = cfg.provider
        active_model = cfg.model
    except Exception:  # noqa: BLE001, S110
        pass
    return render(
        request,
        'agent_core/dashboard/console.html',
        {
            'agent_name': 'worker',
            'active_provider': active_provider,
            'active_model': active_model,
            'active_nav': 'agents',
        },
    )


@staff_member_required
@require_capability('system.read')
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
        runs.values('agent_name')
        .annotate(
            n=Count('id'),
            avg_ms=Avg('duration_ms'),
            tokens=Sum('prompt_tokens') + Sum('completion_tokens'),
            tools=Sum('tool_call_count'),
        )
        .order_by('-n')[:50]
    )
    # Cost — estimated per (agent, model) so each row uses the right price,
    # then folded into per-agent + grand totals. One query, few rows.
    from core.agents.pricing import estimate_cost

    cost_by_agent: dict[str, float] = {}
    total_cost = 0.0
    for r in runs.values('agent_name', 'model').annotate(
        p=Sum('prompt_tokens'), c=Sum('completion_tokens')
    ):
        c = estimate_cost(r['model'], r['p'] or 0, r['c'] or 0)
        cost_by_agent[r['agent_name']] = cost_by_agent.get(r['agent_name'], 0.0) + c
        total_cost += c
    for row in by_agent:
        row['cost'] = cost_by_agent.get(row['agent_name'], 0.0)

    by_state = list(runs.values('state').annotate(n=Count('id')).order_by('-n'))
    top_tools = list(
        AgentStep.objects.filter(
            run__started_at__gte=since,
            kind='tool_call',
        )
        .values('name')
        .annotate(n=Count('id'))
        .order_by('-n')[:25]
    )
    failures = list(runs.filter(state='failed').order_by('-started_at')[:25])

    # Tool reliability — failed tool_result steps carry metadata={'failed': True}
    # (runtime _tool_back). Success rate = (calls - fails) / calls.
    tool_steps = AgentStep.objects.filter(run__started_at__gte=since)
    tool_calls = tool_steps.filter(kind='tool_call').count()
    tool_fails = tool_steps.filter(kind='tool_result', metadata__failed=True).count()
    tool_success_rate = (
        round(100 * (tool_calls - tool_fails) / tool_calls, 1) if tool_calls else None
    )
    failing_tools = list(
        tool_steps.filter(kind='tool_result', metadata__failed=True)
        .values('name')
        .annotate(n=Count('id'))
        .order_by('-n')[:10]
    )

    # p95 run latency (no percentile in sqlite → compute in Python over the window).
    durations = sorted(
        runs.filter(state='completed').exclude(duration_ms=0).values_list('duration_ms', flat=True)
    )
    p95_ms = (
        durations[min(len(durations) - 1, round(0.95 * (len(durations) - 1)))] if durations else 0
    )

    totals = runs.aggregate(
        n=Count('id'),
        tokens=Sum('prompt_tokens') + Sum('completion_tokens'),
        tools=Sum('tool_call_count'),
        avg_ms=Avg('duration_ms'),
    )
    return render(
        request,
        'agent_core/dashboard/observability.html',
        {
            'days': days,
            'totals': totals,
            'total_cost': total_cost,
            'tool_success_rate': tool_success_rate,
            'tool_calls': tool_calls,
            'p95_ms': p95_ms,
            'failing_tools': failing_tools,
            'by_agent': by_agent,
            'by_state': by_state,
            'top_tools': top_tools,
            'failures': failures,
            'refusals': _refusals_since(since),
            'active_nav': 'agents',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Linda', 'url': '/dashboard/assistant/'},
                {'label': 'Observability'},
            ],
        },
    )


@staff_member_required
@require_capability('system.write')
def background_agents_view(request):
    from django.utils import timezone

    from morpheus.app.views import redirect
    from plugins.installed.agent_core.models import BackgroundAgent

    if request.method == 'POST':
        from datetime import time as _time

        from plugins.installed.agent_core.scheduler import min_interval_s, next_daily

        name = (request.POST.get('name') or '').strip()
        engine = request.POST.get('engine') or BackgroundAgent.ENGINE_LINDA
        if engine not in dict(BackgroundAgent.ENGINE_CHOICES):
            engine = BackgroundAgent.ENGINE_LINDA
        agent_name = (request.POST.get('agent_name') or '').strip() or 'worker'
        prompt = (request.POST.get('prompt') or '').strip()
        try:
            interval = max(
                min_interval_s(engine), int(request.POST.get('interval_seconds') or 3600)
            )
        except (TypeError, ValueError):
            interval = 3600
        daily_at = None
        hh, _, mm = (request.POST.get('daily_at') or '').strip().partition(':')
        if hh.isdigit() and mm.isdigit() and int(hh) < 24 and int(mm) < 60:
            daily_at = _time(int(hh), int(mm))
        if name and prompt:
            BackgroundAgent.objects.create(
                name=name[:120],
                agent_name=agent_name[:100],
                engine=engine,
                prompt=prompt[:50_000],
                interval_seconds=interval,
                daily_at=daily_at,
                next_run_at=next_daily(daily_at) if daily_at else timezone.now(),
                # A Linda automation runs as the person who created it.
                created_by=request.user if request.user.is_authenticated else None,
            )
        return redirect('/dashboard/agents/background/')

    rows = list(BackgroundAgent.objects.all().order_by('-updated_at')[:200])
    # Each Linda automation's chat — linked for its owner, the only one who may open it.
    from core.assistant.gates import automation_key
    from core.assistant.models import AssistantConversation

    mine = {
        automation_key(request.user.pk, bg.pk): bg
        for bg in rows
        if bg.engine == BackgroundAgent.ENGINE_LINDA and bg.created_by_id == request.user.pk
    }
    for key, chat_id in AssistantConversation.objects.filter(key__in=list(mine)).values_list(
        'key', 'pk'
    ):
        mine[key].chat_id = chat_id
    from core.agents.events import AgentEvents
    from morpheus.core import hook_registry

    return render(
        request,
        'agent_core/dashboard/background.html',
        {
            'background_agents': rows,
            'agents': agent_registry.all_agents(),
            # Scheduled runs need the autonomy switch; "Run now" works without it.
            'autonomy_on': bool(hook_registry.filter(AgentEvents.AUTONOMY_ENABLED, value=False)),
            'active_nav': 'agents',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Linda', 'url': '/dashboard/assistant/'},
                {'label': 'Automations'},
            ],
        },
    )


@staff_member_required
@require_capability('system.write')
def background_agent_action_view(request, bg_id: str, action: str):
    from django.utils import timezone

    from morpheus.app.views import redirect
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


# ── Linda memory editor ──────────────────────────────────────────────────────
# LindaMemory is written by the memory.remember tool and read at the top of every
# turn. This gives the owner a dashboard to see + curate those facts. Reading is
# staff (informational); mutating is superuser-only (it shapes Linda's behaviour).

_MEMORY_SCOPES = ['merchant', 'customer-segment', 'seasonal']


@staff_member_required
@require_capability('system.read')
def memory_list_view(request):
    from core.assistant.models import LindaMemory

    rows = list(LindaMemory.objects.all().order_by('scope', '-updated_at'))
    groups: dict[str, list] = {s: [] for s in _MEMORY_SCOPES}
    for m in rows:
        groups.setdefault(m.scope, []).append(m)
    grouped = [{'scope': s, 'rows': groups[s]} for s in _MEMORY_SCOPES if groups.get(s)]
    return render(
        request,
        'agent_core/dashboard/memory.html',
        {
            'grouped': grouped,
            'scopes': _MEMORY_SCOPES,
            'total': len(rows),
            'can_edit': request.user.is_superuser,
            'active_nav': 'agents',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Linda', 'url': '/dashboard/assistant/'},
                {'label': 'Memory'},
            ],
        },
    )


@staff_member_required
@require_capability('system.read')
def memory_action_view(request):
    """POST-only create/edit/delete of LindaMemory rows. Superuser-only — editing
    Linda's remembered facts changes how she behaves."""
    from django.contrib import messages
    from django.http import HttpResponseForbidden

    from core.assistant.models import LindaMemory
    from morpheus.app.views import redirect

    here = '/dashboard/agents/memory/'
    if request.method != 'POST':
        return redirect(here)
    if not request.user.is_superuser:
        return HttpResponseForbidden('Only the owner (a superuser) may edit Linda’s memory.')

    action = (request.POST.get('action') or '').strip()
    if action == 'delete':
        LindaMemory.objects.filter(id=request.POST.get('memory_id') or '').delete()
        messages.success(request, 'Memory deleted.')
        return redirect(here)

    if action in ('create', 'edit'):
        scope = (request.POST.get('scope') or 'merchant').strip()
        key = (request.POST.get('key') or '').strip()[:160]
        value = (request.POST.get('value') or '').strip()
        if scope not in _MEMORY_SCOPES or not key or not value:
            messages.error(request, 'Scope, key and value are all required.')
            return redirect(here)
        # unique_together (scope, key): update_or_create keeps create + edit idempotent.
        LindaMemory.objects.update_or_create(
            scope=scope,
            key=key,
            defaults={
                'value': value,
                'source': (request.POST.get('source') or 'owner-edited')[:40],
            },
        )
        messages.success(request, f'Memory “{key}” saved.')
        return redirect(here)

    return redirect(here)
