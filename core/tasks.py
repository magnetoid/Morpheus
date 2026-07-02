"""
Morpheus CMS — Async tasks (webhooks, outbox publisher).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

import requests
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

logger = logging.getLogger('morpheus.core.webhooks')


def _canonical_payload(payload: Any) -> bytes:
    """Stable JSON representation used for signing (sorted keys, no spaces)."""
    return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')


def compute_hmac_signature(secret: str, payload: Any) -> str:
    """Compute X-Morpheus-Signature for an outbound webhook payload."""
    body = _canonical_payload(payload)
    return hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()


def verify_hmac_signature(secret: str, payload_bytes: bytes, provided_signature: str) -> bool:
    """Constant-time verification helper for inbound webhook receivers."""
    expected = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided_signature or '')


@shared_task(
    bind=True,
    max_retries=3,
    time_limit=30,
    soft_time_limit=20,
)
def dispatch_webhook(
    self,
    url: str,
    secret: str,
    event_name: str,
    payload: dict[str, Any],
) -> None:
    """
    POST event data to a Remote Plugin endpoint.

    Adds an HMAC-SHA256 signature header (`X-Morpheus-Signature`) when a secret
    is configured so the receiver can verify authenticity. Retries on transient
    HTTP errors with exponential backoff; gives up on 4xx (other than 408/429).
    """
    body = _canonical_payload(payload)
    headers = {
        'Content-Type': 'application/json',
        'X-Morpheus-Event': event_name,
        'User-Agent': 'Morpheus-Webhook/1.0',
    }
    if secret:
        headers['X-Morpheus-Signature'] = (
            'sha256=' + hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
        )

    try:
        response = requests.post(url, data=body, headers=headers, timeout=10)
    except SoftTimeLimitExceeded:
        logger.warning('Webhook soft time limit hit: %s -> %s', event_name, url)
        raise self.retry(countdown=2**self.request.retries)  # noqa: B904
    except requests.exceptions.RequestException as e:
        logger.warning('Webhook transport error: %s -> %s. %s', event_name, url, e)
        raise self.retry(exc=e, countdown=2**self.request.retries)  # noqa: B904

    if 500 <= response.status_code < 600 or response.status_code in (408, 429):
        logger.warning(
            'Webhook retryable status: %s -> %s [%s]',
            event_name,
            url,
            response.status_code,
        )
        raise self.retry(countdown=2**self.request.retries)

    if response.status_code >= 400:
        logger.error(
            'Webhook permanent failure: %s -> %s [%s] %s',
            event_name,
            url,
            response.status_code,
            response.text[:200],
        )
        return

    logger.info('Webhook delivered: %s -> %s [%s]', event_name, url, response.status_code)


def _publish_to_nats_sync(event_type: str, payload: dict[str, Any]) -> None:
    """
    Synchronous NATS publisher used from Celery workers.

    Using the sync client avoids spinning up an asyncio event loop per event,
    which can conflict with workers that already run async code (e.g. when
    `worker_pool=eventlet/gevent`).
    """
    try:
        # nats-py exposes a sync client at the top level for simple publish flows.
        from nats.aio.client import Client  # noqa: F401  (ensures package is installed)
    except ImportError:  # pragma: no cover
        raise RuntimeError('nats-py is not installed; cannot publish to NATS')  # noqa: B904

    # nats-py is async-only; run a short-lived loop with asyncio.run is acceptable
    # only because we are inside a synchronous Celery task — but we wrap it so
    # any RuntimeError ('event loop already running') falls back to a fresh loop.
    import asyncio

    async def _publish() -> None:
        import nats
        import nats.js.errors

        nats_url = os.environ.get('NATS_URL', 'nats://localhost:4222')
        nc = await nats.connect(nats_url, connect_timeout=5)
        try:
            js = nc.jetstream()
            subject = f'morpheus.events.{event_type.replace(".", "_")}'
            try:
                await js.stream_info('morpheus_events')
            except nats.js.errors.NotFoundError:
                await js.add_stream(name='morpheus_events', subjects=['morpheus.events.*'])
            await js.publish(subject, json.dumps(payload).encode())
        finally:
            await nc.close()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an existing loop — schedule and wait.
            future = asyncio.run_coroutine_threadsafe(_publish(), loop)
            future.result(timeout=10)
            return
    except RuntimeError:
        pass
    asyncio.run(_publish())


# Max publish attempts before an OutboxEvent is dead-lettered (status=FAILED).
# Below this, a failed publish stays PENDING and retries on the next drain.
_OUTBOX_MAX_ATTEMPTS = 5


def _nats_configured() -> bool:
    """True only when NATS is actually wired up for this deployment (NATS_URL set).

    Production `docker-compose.yml` ships WITHOUT NATS (it's commented out as
    optional — the outbox "works without NATS"); only the dev compose sets
    NATS_URL. Without this guard, the beat-scheduled drain would try localhost:4222
    every minute, fail every event, and spam the error log / dead-letter the whole
    backlog. When NATS is unconfigured we skip the drain and leave rows PENDING
    (harmless — there are no consumers yet), ready for whenever NATS is deployed.
    """
    return bool(os.environ.get('NATS_URL'))


def _process_outbox_event(event) -> None:
    """Publish a single OutboxEvent with bounded retry, in its own transaction.

    A transient failure keeps the row PENDING (retried on the next drain) and
    increments ``attempts``; only after ``_OUTBOX_MAX_ATTEMPTS`` is it
    dead-lettered to FAILED. Extracted from ``process_outbox`` so this
    retry/dead-letter logic is unit-testable without the ``FOR UPDATE SKIP
    LOCKED`` drain query (which sqlite — the test DB — cannot run).
    """
    from django.db import transaction

    with transaction.atomic():
        try:
            _publish_to_nats_sync(event.event_type, event.payload)
        except SoftTimeLimitExceeded:
            event.attempts += 1
            event.error_message = 'soft time limit exceeded'
            event.status = 'FAILED' if event.attempts >= _OUTBOX_MAX_ATTEMPTS else 'PENDING'
            logger.warning(
                'Outbox publish soft-timeout for %s (attempt %d, -> %s)',
                event.id,
                event.attempts,
                event.status,
            )
        except Exception as e:  # noqa: BLE001 — explicitly logged with traceback
            event.attempts += 1
            event.error_message = str(e)[:1000]
            # A transient NATS/network failure must retry, not permanently strand
            # the event; only dead-letter (FAILED) after the attempt cap.
            event.status = 'FAILED' if event.attempts >= _OUTBOX_MAX_ATTEMPTS else 'PENDING'
            logger.error(
                'Failed to publish OutboxEvent %s (attempt %d, -> %s): %s',
                event.id,
                event.attempts,
                event.status,
                e,
                exc_info=True,
            )
        else:
            event.status = 'PUBLISHED'
            event.published_at = timezone.now()
        event.save(update_fields=['status', 'published_at', 'error_message', 'attempts'])


@shared_task(bind=True, time_limit=120, soft_time_limit=100)
def process_outbox(self) -> None:
    """
    Drain pending OutboxEvent rows into NATS JetStream.

    A row is locked with `SELECT ... FOR UPDATE SKIP LOCKED` so multiple
    workers can run concurrently without double-publishing. Each event is
    handled in its own transaction so a single failure does not roll back
    successfully published siblings.

    No-ops when NATS is not configured for this deployment (see
    `_nats_configured`) so the beat schedule doesn't error-spam a NATS-less prod.
    """
    if not _nats_configured():
        logger.debug('process_outbox: NATS_URL unset; skipping drain (events left PENDING)')
        return

    from django.db import transaction

    from core.models import OutboxEvent

    with transaction.atomic():
        events = list(
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(status='PENDING')
            .order_by('created_at')[:100]
        )

    for event in events:
        _process_outbox_event(event)


# ── Async hook handler dispatch ───────────────────────────────────────────────


@shared_task(
    name='core.tasks.run_hook_handler_async',
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    time_limit=60,
)
def run_hook_handler_async(self, event: str, handler_path: str, kwargs: dict) -> None:
    """Re-invoke a hook handler from a Celery worker.

    Used by HookRegistry when a handler was registered with mode='async'.
    Resolves the handler from its dotted import path so we don't have to
    pickle the callable, and invokes it with the serialised kwargs.

    Failures here are NOT re-raised by default — async hook handlers that
    fail get a structured log line and a retry. After max_retries the
    event is dropped (we don't want stuck handlers to block the queue).
    Surfaced to the merchant via the existing observability error log.
    """
    import importlib

    module_path, _, attr_name = handler_path.rpartition('.')
    if not module_path or not attr_name:
        logger.error('async hook: malformed handler path %s', handler_path)
        return

    # Walk through dotted attr lookups so `module.Class.method` works.
    try:
        mod = importlib.import_module(
            module_path.split('.', 1)[0]
            if '.' not in module_path
            else module_path.rsplit('.', 1)[0]
            if False
            else module_path
        )
    except Exception as exc:  # noqa: BLE001
        # Handle qualnames like 'pkg.mod.Class.method' — split on the last dot
        # of the module path, treat the remainder as attribute chain.
        try:
            mod_chain, _, tail = handler_path.rpartition('.')
            mod = importlib.import_module(mod_chain.rsplit('.', 1)[0])
        except Exception:  # noqa: BLE001
            logger.error('async hook: cannot import module for %s: %s', handler_path, exc)
            return

    # Resolve the handler — walk dotted attrs to support nested methods.
    target = mod
    for part in handler_path.split('.')[1:]:
        target = getattr(target, part, None)
        if target is None:
            logger.error('async hook: cannot resolve %s on %s', part, handler_path)
            return

    try:
        target(**(kwargs or {}))
    except Exception as exc:  # noqa: BLE001 — logged + auto-retry
        logger.warning(
            'async hook handler %s failed (attempt %s): %s',
            handler_path,
            self.request.retries + 1,
            exc,
            exc_info=True,
        )
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                'async hook handler %s exhausted retries; dropping event %s',
                handler_path,
                event,
            )


# ── Daily platform update check ───────────────────────────────────────────────


@shared_task(name='core.tasks.check_for_updates', time_limit=60, soft_time_limit=45)
def check_for_updates() -> dict:
    """Daily: fetch upstream + cache update status so dashboard surfaces can
    flag "update available" without a per-request git fetch. Best-effort —
    network/git errors degrade to an 'unknown'/'unavailable' status, never raise."""
    from core.updates import refresh_update_status

    try:
        status = refresh_update_status()
    except Exception:  # noqa: BLE001 — a failed check must not crash the beat worker
        logging.getLogger('morpheus.core.updates').warning('update check failed', exc_info=True)
        return {'available': 'unknown'}
    if status.get('available') == 'yes':
        logging.getLogger('morpheus.core.updates').info(
            'update available: %s behind, latest=%s',
            status.get('behind'),
            status.get('latest'),
        )
    return status
