"""Regression: the OTel PII scrubber must rewrite span attributes IN PLACE.

The old code called `span.set_attribute()` inside the processor's `on_end`,
which is a silent no-op on an already-ended ReadableSpan — so PII (emails,
IPs) leaked to the exporter unscrubbed. The fix is a module-level
`scrub_span_attributes(span)` that mutates `span._attributes` directly and
returns the number of attributes rewritten.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.observability import scrub_span_attributes


class _FakeSpan:
    """Stand-in for a ReadableSpan — only the backing `_attributes` map matters."""

    def __init__(self, attributes):
        self._attributes = attributes


class ScrubSpanAttributesTests(SimpleTestCase):
    def test_pii_attributes_redacted_in_place(self):
        span = _FakeSpan(
            {
                'user.email': 'jane.doe@example.com',
                'http.client_ip': '203.0.113.7',
                'db.statement': 'SELECT 1',
                'n': 5,
            }
        )
        n = scrub_span_attributes(span)

        attrs = span._attributes
        # Email + IP are rewritten in place: redacted marker, no raw value left.
        self.assertIn('<redacted:', attrs['user.email'])
        self.assertNotEqual(attrs['user.email'], 'jane.doe@example.com')
        self.assertIn('<redacted:', attrs['http.client_ip'])
        self.assertNotEqual(attrs['http.client_ip'], '203.0.113.7')
        # Non-PII string is untouched.
        self.assertEqual(attrs['db.statement'], 'SELECT 1')
        # Non-str value is skipped entirely.
        self.assertEqual(attrs['n'], 5)
        # Exactly two attributes were rewritten (email + ip).
        self.assertEqual(n, 2)

    def test_none_attributes_returns_zero_and_does_not_raise(self):
        self.assertEqual(scrub_span_attributes(_FakeSpan(None)), 0)

    def test_missing_attributes_returns_zero_and_does_not_raise(self):
        class _NoAttrs:
            pass

        self.assertEqual(scrub_span_attributes(_NoAttrs()), 0)

    def test_empty_attributes_returns_zero(self):
        self.assertEqual(scrub_span_attributes(_FakeSpan({})), 0)

    def test_idempotent_no_double_redaction(self):
        span = _FakeSpan(
            {
                'user.email': 'jane.doe@example.com',
                'http.client_ip': '203.0.113.7',
            }
        )
        first = scrub_span_attributes(span)
        self.assertEqual(first, 2)
        snapshot = dict(span._attributes)

        # A second pass must not rewrite the already-redacted markers.
        second = scrub_span_attributes(span)
        self.assertEqual(second, 0)
        self.assertEqual(span._attributes, snapshot)
        self.assertIn('<redacted:', span._attributes['user.email'])
