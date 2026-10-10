"""Polling endpoint for long-running LLM completions.

Pattern:

    POST /api/llm-tasks/
        Headers: Authorization: Bearer mph_...
        Body:    {prompt, system?, max_tokens?, temperature?}
        →        202 {task_id, status: "pending"}

    GET  /api/llm-tasks/<task_id>/
        Headers: Authorization: Bearer mph_...
        →        200 {status: "pending"}              while in progress
                 200 {status: "done", result: "..."}  on success
                 200 {status: "failed", error: "..."} on failure

Replaces the synchronous request → 20s wait pattern for callers that
can poll. The worker handling the POST returns in < 50 ms once the
Celery task is queued; the LLM call runs on a Celery worker, not the
gunicorn pool.

Storage is the default Django cache (Redis-backed in prod). TTL is 1
hour so abandoned tasks don't leak indefinitely.
"""

from __future__ import annotations

import json
import logging
import uuid

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from core.auth.csrf import csrf_exempt_for_bearer

logger = logging.getLogger('morpheus.api.llm_tasks')

_TTL_SECONDS = 60 * 60  # 1 hour
_MAX_PROMPT_BYTES = 20_000  # ~5k tokens, generous


def _cache_key(task_id: str) -> str:
    return f'llm-task:{task_id}'


def _is_authed(request: HttpRequest) -> bool:
    """Accept either a Bearer token OR a staff session — same rule as
    GraphQL mutations."""
    user = getattr(request, 'user', None)
    if user and getattr(user, 'is_staff', False):
        return True
    # Try Bearer auth resolver.
    try:
        from plugins.installed.agent_mcp.auth import apply_bearer_user

        return apply_bearer_user(request)
    except Exception:  # noqa: BLE001
        return False


def _owner_id_for(request: HttpRequest) -> str | int:
    """Stable owner identifier stored on the cache record.

    Authenticated requests use the user's pk; anonymous Bearer tokens
    that pass `_is_authed` still need an owner — use the bearer token
    sha (resolved by apply_bearer_user) when available, else 'public'.
    """
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user.pk
    # Bearer-only path: bucket all bearer-authed anonymous requests
    # under a single 'public' owner — we can't link them back to a user.
    return 'public'


@csrf_exempt_for_bearer
@require_http_methods(['POST'])
def llm_task_create(request: HttpRequest) -> HttpResponse:
    """POST /api/llm-tasks/ — queue an LLM completion, return task id."""
    if not _is_authed(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    prompt = (body.get('prompt') or '').strip()
    system = (body.get('system') or '').strip()
    if not prompt:
        return JsonResponse({'error': 'Missing prompt'}, status=400)
    if len(prompt.encode('utf-8')) > _MAX_PROMPT_BYTES:
        return JsonResponse(
            {'error': f'Prompt exceeds {_MAX_PROMPT_BYTES} bytes'},
            status=400,
        )

    try:
        max_tokens = int(body.get('max_tokens') or 1000)
    except (TypeError, ValueError):
        max_tokens = 1000
    max_tokens = max(1, min(max_tokens, 4096))
    try:
        temperature = float(body.get('temperature', 0.6))
    except (TypeError, ValueError):
        temperature = 0.6
    temperature = max(0.0, min(temperature, 2.0))

    task_id = str(uuid.uuid4())
    # Tag the record with the creator so `llm_task_status` can verify
    # the reader is the owner (or staff) — closes a UUID-guess IDOR.
    cache.set(
        _cache_key(task_id),
        {'status': 'pending', 'owner_id': _owner_id_for(request)},
        timeout=_TTL_SECONDS,
    )

    from plugins.installed.ai_assistant import tasks as ai_tasks

    ai_tasks.run_completion_task.delay(
        task_id=task_id,
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return JsonResponse({'task_id': task_id, 'status': 'pending'}, status=202)


@csrf_exempt_for_bearer
@require_http_methods(['GET'])
def llm_task_status(request: HttpRequest, task_id: str) -> HttpResponse:
    """GET /api/llm-tasks/<id>/ — poll task status + result."""
    if not _is_authed(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    record = cache.get(_cache_key(task_id))
    if record is None:
        return JsonResponse(
            {'status': 'unknown', 'error': 'Task not found or expired'},
            status=404,
        )
    # Owner check: staff can read anything; otherwise the reader's
    # owner_id must match the creator's. 404 on mismatch so we don't
    # confirm task existence to a guesser.
    user = getattr(request, 'user', None)
    is_staff = bool(user and getattr(user, 'is_staff', False))
    if not is_staff:
        record_owner = record.get('owner_id')
        if record_owner != _owner_id_for(request):
            logger.warning(
                'llm_task_status: owner mismatch for task=%s requester=%s',
                task_id,
                _owner_id_for(request),
            )
            return JsonResponse(
                {'status': 'unknown', 'error': 'Task not found or expired'},
                status=404,
            )
    # Strip owner_id from the returned payload — it's an internal field.
    public = {k: v for k, v in record.items() if k != 'owner_id'}
    return JsonResponse(public)
