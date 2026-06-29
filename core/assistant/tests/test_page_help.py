import json

from django.test import TestCase

from core.assistant.page_help import _parse_json, build_page_help


class _FakeProvider:
    def __init__(self, text):
        self._text = text

    def respond(self, *, messages, tools=None, temperature=0.3, max_tokens=1024):
        class R:  # minimal LLMResponse stand-in
            pass

        r = R()
        r.text = self._text
        return r


GOOD = json.dumps(
    {
        'summary': 'This is your Orders page.',
        'numbers': [{'label': 'Orders', 'reading': '42, up 12%'}],
        'actions': ['Fulfill the 3 pending orders'],
    }
)


class PageHelpTests(TestCase):
    def test_parses_clean_json(self):
        out = build_page_help(
            {
                'page_title': 'Orders',
                'page_url': '/dashboard/orders/',
                'page_text': '42 orders',
                'structured': None,
            },
            provider=_FakeProvider(GOOD),
        )
        self.assertTrue(out['ok'])
        self.assertEqual(out['summary'], 'This is your Orders page.')
        self.assertEqual(out['numbers'][0]['label'], 'Orders')
        self.assertIn('Fulfill', out['actions'][0])

    def test_parses_json_wrapped_in_prose(self):
        wrapped = 'Sure!\n```json\n' + GOOD + '\n```\nHope that helps.'
        self.assertIsNotNone(_parse_json(wrapped))

    def test_empty_page_text_skips_llm(self):
        out = build_page_help(
            {'page_title': 'X', 'page_url': '/x/', 'page_text': '  ', 'structured': None},
            provider=_FakeProvider(GOOD),
        )
        self.assertFalse(out['ok'])

    def test_malformed_json_returns_not_ok(self):
        out = build_page_help(
            {'page_title': 'Orders', 'page_url': '/o/', 'page_text': 'x' * 50, 'structured': None},
            provider=_FakeProvider('not json at all'),
        )
        self.assertFalse(out['ok'])
        self.assertTrue(out['message'])
