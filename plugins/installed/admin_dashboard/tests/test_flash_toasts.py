"""The shell's toasts come from the request's messages, not a view's ``messages``.

The CRM inbox passed its emails as ``messages``, which replaced the messages
framework's variable: the shell drew one empty toast per email (up to 200) down the
right side of the page, and a real "Thread closed." never showed.
"""

from django.contrib import messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.template import Context, Template
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase


class FlashToastTests(SimpleTestCase):
    def _request(self):
        request = RequestFactory().get('/dashboard/')
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_a_view_variable_named_messages_does_not_replace_the_toasts(self):
        request = self._request()
        messages.success(request, 'flash-marker')
        out = Template(
            '{% load morph_dashboard %}{% flash_messages as f %}'
            '{% for m in f %}[{{ m.message }}]{% endfor %}'
        ).render(Context({'request': request, 'messages': [object(), object()]}))
        self.assertEqual(out, '[flash-marker]')

    def test_no_request_means_no_toasts(self):
        out = Template('{% load morph_dashboard %}{% flash_messages as f %}{{ f|length }}').render(
            Context({})
        )
        self.assertEqual(out, '0')

    def test_the_shell_reads_its_toasts_through_the_tag(self):
        source = get_template('admin_dashboard/base.html').template.source
        self.assertIn('{% flash_messages as flash %}', source)
        self.assertNotIn('{% for m in messages %}', source)
