"""error_log collector — pulls from core.errors.ErrorEvent.

`core.errors` records every server-side 5xx and client JS error into an
`ErrorEvent` row (ADR 0025 — this is where the write path lives; the old
`observability.ErrorEvent` is retired and no longer written). Rather than
fire a hook on every record, we run hourly and read new rows since the last
successful run.

Fingerprint: source + the model's own stable error fingerprint — so 1000
identical 500s become one signal with seen_count=1000.

Layer note: `core.errors` is core, so this is an intra-core read, not a
cross-plugin one.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import timedelta

from django.utils import timezone

from core.self_improvement.collectors.base import Collector, Signal
from core.self_improvement.models import SiIngestJob
from core.self_improvement.services import fingerprint_for

logger = logging.getLogger('morpheus.self_improvement.error_log')

SOURCE = 'error_log'


class ErrorLogCollector(Collector):
    """Hourly poller. Looks back to the last completed run + small slop;
    falls back to last-24h on first run."""

    name = SOURCE

    def run(self) -> Iterable[Signal]:
        ErrorEvent = self._error_event_model()
        if ErrorEvent is None:
            return  # core.errors not installed; collector is a no-op

        since = self._last_successful_run() or (timezone.now() - timedelta(hours=24))
        qs = (
            ErrorEvent.objects.filter(created_at__gt=since)
            .order_by('created_at')
            .iterator(chunk_size=200)
        )
        for ev in qs:
            yield self._signal_from(ev)

    # ------------------------------------------------------------------

    def _signal_from(self, ev) -> Signal:
        # core.errors already computes a stable per-error fingerprint (class +
        # trace prefix / JS file:line); reuse it, namespaced by SOURCE, so a
        # flood of identical 500s collapses to one signal. Fall back to
        # exception_class + top frame if the row has no fingerprint.
        exc_class = getattr(ev, 'exception_class', '') or '?'
        first_frame = self._first_meaningful_frame(getattr(ev, 'traceback', '') or '')
        err_fp = getattr(ev, 'fingerprint', '') or f'{exc_class}:{first_frame}'
        fp = fingerprint_for(SOURCE, err_fp)

        return Signal(
            source=SOURCE,
            fingerprint=fp,
            severity=self._severity_for(ev),
            payload={
                'ev_id': str(getattr(ev, 'id', '')),
                'kind': getattr(ev, 'kind', '?'),
                'path': (getattr(ev, 'path', '') or '')[:300],
                'message': (getattr(ev, 'message', '') or '')[:300],
                'first_frame': first_frame,
                'exception_class': exc_class,
            },
            occurred_at=getattr(ev, 'created_at', None),
        )

    @staticmethod
    def _first_meaningful_frame(trace: str) -> str:
        """Pick the topmost `File ".../app/..."` line — skips
        site-packages, gives the real culprit. Returns '?' if nothing
        meaningful is found.
        """
        for line in trace.splitlines():
            stripped = line.strip()
            if stripped.startswith('File "') and '/app/' in stripped:
                return stripped[:200]
        # Fallback to the very first frame if we couldn't find /app/
        for line in trace.splitlines():
            stripped = line.strip()
            if stripped.startswith('File "'):
                return stripped[:200]
        return '?'

    @staticmethod
    def _severity_for(ev) -> int:
        # Client JS errors are advisory unless they spike.
        if (getattr(ev, 'kind', '') or '').lower() == 'client':
            return 30
        # Critical request paths (payments, auth, webhooks) get bumped.
        path = (getattr(ev, 'path', '') or '').lower()
        if any(k in path for k in ('payment', 'checkout', 'auth', 'login', 'webhook')):
            return 85
        return 60

    def _last_successful_run(self):
        """Return the started_at of the most recent successful ingest
        job, or None on first run."""
        prev = (
            SiIngestJob.objects.filter(collector=self.name, status='ok')
            .order_by('-started_at')
            .first()
        )
        # Look back slightly before that started_at to catch events
        # that arrived between scan and write of the previous run.
        return prev.started_at - timedelta(minutes=10) if prev else None

    @staticmethod
    def _error_event_model():
        """Resolve core.errors.ErrorEvent lazily — model might not be loaded
        yet at import time."""
        from django.apps import apps  # noqa: PLC0415 — lazy resolution

        try:
            return apps.get_model('morph_errors', 'ErrorEvent')
        except LookupError:
            return None
