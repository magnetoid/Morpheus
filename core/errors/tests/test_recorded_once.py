"""One exception is one row, however many doors report it.

The middleware records a view's exception; Django then logs the same 500 on
``django.request`` with ``exc_info`` and the log handler recorded it again, by then
with a longer traceback, so it landed as a second row in a second group. The API's
REST and GraphQL handlers log and record too. The handler is not attached under
tests, so the suite never saw it.
"""

from __future__ import annotations

import logging
import sys

from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from core.brain.log_handler import ErrorEventLogHandler
from core.errors.middleware import ErrorCaptureMiddleware
from core.errors.models import ErrorEvent
from core.errors.services import record_error


def _view():
    raise KeyError('missing')


class RecordedOnceTests(TestCase):
    def test_the_request_log_line_after_the_middleware_adds_no_row(self):
        request = RequestFactory().get('/products/')
        middleware = ErrorCaptureMiddleware(lambda r: HttpResponse())
        try:
            try:
                _view()
            except KeyError as exc:
                middleware.process_exception(request, exc)
                raise  # as Django does after the middleware returns None
        except KeyError:
            exc_info = sys.exc_info()  # the longer traceback Django logs
        record = logging.LogRecord(
            'django.request', logging.ERROR, __file__, 1, 'Internal Server Error: %s',
            ('/products/',), exc_info,
        )  # fmt: skip
        ErrorEventLogHandler().emit(record)
        self.assertEqual(ErrorEvent.objects.count(), 1)

    def test_recording_the_same_exception_twice_keeps_one_row(self):
        try:
            _view()
        except KeyError as exc:
            record_error(exc, kind='server')
            record_error(exc, kind='server', extra={'source': 'api.rest'})
        self.assertEqual(ErrorEvent.objects.count(), 1)

    def test_two_raises_are_two_rows(self):
        for _ in range(2):
            try:
                _view()
            except KeyError as exc:
                record_error(exc, kind='server')
        self.assertEqual(ErrorEvent.objects.count(), 2)
