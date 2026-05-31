"""error_log collector — pulls from observability.ErrorEvent.

The observability plugin already records every server-side and client
JS error into an `ErrorEvent` row. Rather than fire a hook on every
record (which would couple the engine to the observability plugin's
write path), we run hourly and read new rows since the last successful
run.

Fingerprint: source + exception class + first frame summary — so 1000
identical 500s become one signal with seen_count=1000.

Cross-plugin import note: this collector is core code reading a plugin
model. That's the only direction allowed; plugins remain forbidden
from importing each other. Self-improvement is at the foundational
tier, so reading observability is a layer-down read, not peer-to-peer
coupling.
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
            return  # observability not installed; collector is a no-op

        since = self._last_successful_run() or (timezone.now() - timedelta(hours=24))
        qs = (
            ErrorEvent.objects.filter(occurred_at__gt=since)
            .order_by('occurred_at')
            .iterator(chunk_size=200)
        )
        for ev in qs:
            yield self._signal_from(ev)

    # ------------------------------------------------------------------

    def _signal_from(self, ev) -> Signal:
        # Top frame of the trace gives a stable cluster key. Trace text
        # varies wildly between requests; the first frame is the signal.
        first_frame = self._first_meaningful_frame(getattr(ev, 'stack_trace', '') or '')
        exc_class = self._exception_class(getattr(ev, 'message', '') or '')
        fp = fingerprint_for(SOURCE, getattr(ev, 'source', '?'), exc_class, first_frame)

        return Signal(
            source=SOURCE,
            fingerprint=fp,
            severity=self._severity_for(ev),
            payload={
                'ev_id': str(getattr(ev, 'id', '')),
                'sub_source': getattr(ev, 'source', '?'),
                'message': (getattr(ev, 'message', '') or '')[:300],
                'first_frame': first_frame,
                'exception_class': exc_class,
            },
            occurred_at=getattr(ev, 'occurred_at', None),
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
    def _exception_class(message: str) -> str:
        """`KeyError: 'seo_meta'` -> `KeyError`. Falls back to '?'."""
        if ':' in message:
            head = message.split(':', 1)[0].strip()
            if head and head.replace('.', '').isalnum():
                return head[:64]
        return '?'

    @staticmethod
    def _severity_for(ev) -> int:
        sub = (getattr(ev, 'source', '') or '').lower()
        # Critical paths (payments, auth, celery beat) get bumped.
        if any(k in sub for k in ('payment', 'auth', 'beat', 'webhook')):
            return 85
        if sub.startswith('client'):
            return 30  # JS errors are advisory unless they spike
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
        """Resolve observability.ErrorEvent lazily — model might not
        be loaded yet at import time, and the plugin might be absent."""
        from django.apps import apps  # noqa: PLC0415 — lazy resolution

        try:
            return apps.get_model('observability', 'ErrorEvent')
        except LookupError:
            return None
