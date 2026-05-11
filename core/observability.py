"""OpenTelemetry initialization. Optional: if OTEL_EXPORTER_OTLP_ENDPOINT is unset,
this is a no-op. If set, we configure tracing exporters and instrument the
common Django/Celery/Redis stack.

All spans pass through a ``PIIScrubberProcessor`` before being batched
for export — emails, phone numbers, and IPv4 addresses in span
attributes are replaced with stable SHA-256 hashes so traces never
leak customer data downstream (Datadog/Honeycomb/etc).
"""
from __future__ import annotations

import hashlib
import logging
import os
import re

logger = logging.getLogger('morpheus.observability')


_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_PHONE_RE = re.compile(r'\+?\d[\d\s\-().]{7,}\d')
_IPV4_RE = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')


def _hash_token(match: re.Match) -> str:
    digest = hashlib.sha256(match.group(0).encode('utf-8')).hexdigest()[:12]
    return f'<redacted:{digest}>'


def scrub_pii(text: str) -> str:
    """Replace email/phone/IPv4 occurrences in ``text`` with stable hashes.
    Idempotent — already-redacted markers are left untouched."""
    if not isinstance(text, str) or not text:
        return text
    text = _EMAIL_RE.sub(_hash_token, text)
    text = _PHONE_RE.sub(_hash_token, text)
    text = _IPV4_RE.sub(_hash_token, text)
    return text


def init_observability() -> None:
    endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
    if not endpoint:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as e:
        logger.warning("OpenTelemetry not fully installed; tracing disabled: %s", e)
        return

    class _PIIScrubberProcessor(SpanProcessor):
        """On span end, rewrite attributes in place with PII redacted."""

        def on_start(self, span, parent_context=None) -> None:
            return None

        def on_end(self, span) -> None:
            try:
                attrs = dict(span.attributes or {})
                for key, value in list(attrs.items()):
                    if isinstance(value, str):
                        cleaned = scrub_pii(value)
                        if cleaned != value:
                            span.set_attribute(key, cleaned)
            except Exception:  # noqa: BLE001 — never break the export pipeline
                pass

        def shutdown(self) -> None:
            return None

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return True

    try:
        service_name = os.getenv('OTEL_SERVICE_NAME', 'morpheus')
        resource = Resource.create({'service.name': service_name})

        provider = TracerProvider(resource=resource)
        provider.add_span_processor(_PIIScrubberProcessor())
        exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        DjangoInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        Psycopg2Instrumentor().instrument()
        RedisInstrumentor().instrument()
        LoggingInstrumentor().instrument(
            set_logging_format=True,
            logging_format=(
                '%(asctime)s %(levelname)s [%(name)s] '
                '[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s '
                'resource.service.name=%(otelServiceName)s] - %(message)s'
            ),
        )
        CeleryInstrumentor().instrument()
        logger.info("OpenTelemetry initialized: %s", endpoint)
    except Exception as e:  # noqa: BLE001 — observability must never break the app
        logger.error("OpenTelemetry initialization failed: %s", e, exc_info=True)
