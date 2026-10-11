"""A hook fired with an uploaded file still reaches its webhooks and the outbox.

The dashboard's "form saved" hooks pass the request's files along for the
contributors that store them (`fire_entity_form_saved`: `files=request.FILES`).
The remote payload encoder did not know uploaded files, so saving any dashboard
form with an image logged "InMemoryUploadedFile is not JSON serializable" and
dropped the event's webhook and outbox copy (beta.irvingsurvival.com,
2026-10-10, found by the first `errors_report`). The log bridge kept only the
exception text, so the stored error did not even say which event it was.
"""

from __future__ import annotations

import logging

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from core.hooks import hook_registry


class HookPayloadFileTests(TestCase):
    def test_an_uploaded_file_is_described_not_shipped(self):
        files = MultiValueDict(
            {'image': [SimpleUploadedFile('lantern.jpg', b'\xff\xd8 bytes', 'image/jpeg')]}
        )
        payload = hook_registry._serialize_payload({'files': files, 'note': 'x'})
        self.assertEqual(
            payload['files']['image'],
            {'type': 'file', 'name': 'lantern.jpg', 'size': 8, 'content_type': 'image/jpeg'},
        )
        self.assertEqual(payload['note'], 'x')


class LogBridgeKeepsTheLogLineTests(TestCase):
    def test_a_logged_exception_keeps_the_line_that_names_its_cause(self):
        from core.brain.log_handler import ErrorEventLogHandler
        from core.errors.models import ErrorEvent

        try:
            raise TypeError('Object of type Thing is not JSON serializable')
        except TypeError:
            import sys

            record = logging.LogRecord(
                'morpheus.hooks', logging.ERROR, __file__, 1,
                'Failed to serialize payload for event=%s: %s', ('category.form_saved', 'x'),
                sys.exc_info(),
            )  # fmt: skip
        ErrorEventLogHandler().emit(record)
        event = ErrorEvent.objects.get()
        self.assertIn('event=category.form_saved', event.metadata['log_message'])
