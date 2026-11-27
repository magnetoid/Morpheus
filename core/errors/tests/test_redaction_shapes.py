"""Secret shapes the error log kept as they were (review, 2026-11).

Each row is text an error can quote: the secret in it must not survive
``redact_secrets``. Ordinary text must come through unchanged. A browser's page
and script addresses are stored without their query string, since a visitor's
email or a token rides there, and a payment link loses its token.
"""

from __future__ import annotations

from django.core import signing
from django.test import RequestFactory, SimpleTestCase, TestCase

from core.errors.models import ErrorEvent
from core.errors.services import record_client_error, redact_secrets

_TURN_TOKEN = 'lt1.' + signing.dumps({'u': 1, 'c': 'chat:9'}, salt='t', compress=True)

#: (what the error said, the secret in it)
LEAKS = (
    (
        '400 Client Error: Bad Request for url: https://generativelanguage.googleapis.com/v1beta/'
        'models/gemini-2.5-flash:generateContent?key=AIzaSyD4abcdefghijklmnopqrstuvwxyz01234',
        'AIzaSyD4abcdefghijklmnopqrstuvwxyz01234',
    ),
    (
        'GOOGLE_API_KEY=AIzaSyD4abcdefghijklmnopqrstuvwxyz01234',
        'AIzaSyD4abcdefghijklmnopqrstuvwxyz01234',
    ),
    ('OPENROUTER_API_KEY=or-v1-0123abcd4567efgh', 'or-v1-0123abcd4567efgh'),
    ('Error 111 connecting to redis://:r3dis-pass@redis:6379/0', 'r3dis-pass'),
    ('could not connect: postgres://morph:pa/ss-word@db:5432/morph', 'pa/ss-word'),
    ('token refresh failed: client_secret=GOCSPX-abc123def456', 'GOCSPX-abc123def456'),
    ('refresh_token=1//0gAbCdEfGhIjKlMn&grant_type=refresh_token', '1//0gAbCdEfGhIjKlMn'),
    ('id_token=eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxIn0.sig', 'eyJhbGciOiJSUzI1NiJ9'),
    (
        'Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b',
        '9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b',
    ),
    ("{'HTTP_AUTHORIZATION': 'Token 9944b09199c62bcf9418ad84'}", '9944b09199c62bcf9418ad84'),
    ('Cookie: sessionid=k2jx9sessionvalue; csrftoken=Zq81csrfvalue', 'k2jx9sessionvalue'),
    ('Cookie: sessionid=k2jx9sessionvalue; csrftoken=Zq81csrfvalue', 'Zq81csrfvalue'),
    ('confirm failed for pi_3NxYzAbCdEfGh_secret_LmNoPqRsTuVwXyZ0', 'LmNoPqRsTuVwXyZ0'),
    (f'MCP call refused for {_TURN_TOKEN}', _TURN_TOKEN.split(':', 1)[1]),
    ("ValidationError({'password': 'hunter2-secret'})", 'hunter2-secret'),
    ('GET https://shop.example/pay/Tk9xQ2abc/ 500', 'Tk9xQ2abc'),
)

#: Text that must come through as it was.
ORDINARY = (
    'GET https://shop.example/products/?page=2&sort=price answered 500',
    "KeyError: 'title'",
    'The token expired. Ask for a new sign-in code.',
    'Authorization failed for staff user 42',
    'File "/app/plugins/installed/payments/views_pay.py", line 12, in pay_order',
    'https://example.com:8080/a?email=x answered 404',
    'payment pi_3NxYzAbCdEfGh failed: card_declined',
)


class RedactionShapeTests(SimpleTestCase):
    def test_every_secret_shape_is_removed(self):
        for text, secret in LEAKS:
            with self.subTest(text=text):
                self.assertNotIn(secret, redact_secrets(text))

    def test_ordinary_text_is_untouched(self):
        for text in ORDINARY:
            with self.subTest(text=text):
                self.assertEqual(redact_secrets(text), text)

    def test_the_payment_intent_id_stays_for_the_fixer(self):
        self.assertIn(
            'pi_3NxYzAbCdEfGh', redact_secrets('pi_3NxYzAbCdEfGh_secret_LmNoPqRsTuVwXyZ0')
        )


class BrowserAddressTests(TestCase):
    def test_a_page_and_script_address_lose_their_query_and_payment_token(self):
        record_client_error(
            {
                'message': 'TypeError: x is undefined',
                'page': 'https://shop.example/pay/TOKEN123/?email=jane@example.com&token=abc#k=v',
                'source': 'https://shop.example/static/app.js?v=3&token=abc',
                'lineno': 4,
            },
            request=RequestFactory().post('/api/errors/client/'),
        )
        event = ErrorEvent.objects.get()
        stored = event.path + ' ' + event.metadata['source_url']
        for kept in ('TOKEN123', 'jane', 'token=abc', 'k=v', '?'):
            self.assertNotIn(kept, stored)
        self.assertEqual(event.path, 'https://shop.example/pay/<token>/')
        self.assertEqual(event.metadata['source_url'], 'https://shop.example/static/app.js')
