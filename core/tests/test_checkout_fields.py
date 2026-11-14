"""The checkout's extra fields: one seam, answered by the apps that own them.

Apps append field dicts to CHECKOUT_FIELDS; `core.checkout_fields` keeps the well-formed
ones, renders them inside the checkout form, and cleans what the shopper sent before
``completeOrder`` stores it. The real handlers are put back after each test (CLAUDE.md).
"""

from __future__ import annotations

from django.http import QueryDict
from django.test import RequestFactory, SimpleTestCase

from core import checkout_fields
from core.hooks import MorpheusEvents, hook_registry

TERMS = {
    'key': 'terms_accepted',
    'label': 'I accept the terms.',
    'kind': 'checkbox',
    'required': True,
    'link_url': '/pages/terms/',
    'link_text': 'Read them',
    'error': 'Please accept the terms.',
    'order': 90,
}
NOTE = {'key': 'order_notes', 'label': 'Notes', 'kind': 'textarea', 'max_length': 5, 'order': 10}


class _Isolated(SimpleTestCase):
    def setUp(self):
        saved = list(hook_registry._handlers.get(MorpheusEvents.CHECKOUT_FIELDS, []))
        hook_registry._handlers[MorpheusEvents.CHECKOUT_FIELDS] = []
        self.addCleanup(hook_registry._handlers.__setitem__, MorpheusEvents.CHECKOUT_FIELDS, saved)

    def answer(self, *declared):
        hook_registry.register(
            MorpheusEvents.CHECKOUT_FIELDS, lambda value, **kw: [*value, *declared]
        )


class FieldsTests(_Isolated):
    def test_with_no_app_the_checkout_asks_nothing(self):
        self.assertEqual(checkout_fields.fields(), [])
        self.assertFalse(checkout_fields.has_required())
        self.assertEqual(checkout_fields.clean({'order_notes': 'hi'}), ({}, []))

    def test_fields_come_back_in_order(self):
        self.answer(TERMS, NOTE)
        self.assertEqual(
            [f['key'] for f in checkout_fields.fields()], ['order_notes', 'terms_accepted']
        )

    def test_a_malformed_field_is_left_out(self):
        self.answer(
            {'key': 'Bad Key', 'label': 'x'},
            {'key': 'no_label', 'label': ''},
            'not a dict',
            {'key': 'odd_kind', 'label': 'Odd', 'kind': 'radio'},
        )
        found = checkout_fields.fields()
        self.assertEqual([f['key'] for f in found], ['odd_kind'])
        self.assertEqual(found[0]['kind'], 'text')

    def test_the_first_app_to_name_a_key_keeps_it(self):
        self.answer(NOTE, {**NOTE, 'label': 'Second'})
        self.assertEqual([f['label'] for f in checkout_fields.fields()], ['Notes'])

    def test_only_a_web_link_or_a_site_path_is_kept(self):
        for url, kept in (
            ('/pages/terms/', '/pages/terms/'),
            ('https://example.com/terms', 'https://example.com/terms'),
            ('//evil.example/terms', ''),
            ('javascript:alert(1)', ''),
        ):
            with self.subTest(url=url):
                field = checkout_fields._normalise({**TERMS, 'link_url': url})
                self.assertEqual(field['link_url'], kept)

    def test_a_length_is_clamped(self):
        field = checkout_fields._normalise({**NOTE, 'max_length': 10**6})
        self.assertEqual(field['max_length'], checkout_fields.MAX_LENGTH)

    def test_a_required_field_is_one_a_wallet_cannot_answer(self):
        self.answer(NOTE)
        self.assertFalse(checkout_fields.has_required())
        self.answer(TERMS)
        self.assertTrue(checkout_fields.has_required())


class CleanTests(_Isolated):
    def setUp(self):
        super().setUp()
        self.answer(NOTE, TERMS)

    def test_a_missing_required_answer_refuses(self):
        answers, problems = checkout_fields.clean({'order_notes': 'Door'})
        self.assertEqual(problems, ['Please accept the terms.'])
        self.assertEqual(answers, {'order_notes': 'Door'})

    def test_a_tick_is_true_and_text_is_cut_to_its_length(self):
        answers, problems = checkout_fields.clean(
            {'terms_accepted': '1', 'order_notes': '  Leave it  '}
        )
        self.assertEqual(problems, [])
        self.assertEqual(answers, {'terms_accepted': True, 'order_notes': 'Leave'})

    def test_a_key_no_app_declared_is_dropped(self):
        answers, _ = checkout_fields.clean({'terms_accepted': True, 'is_staff': 'yes'})
        self.assertEqual(answers, {'terms_accepted': True})

    def test_garbage_is_no_answer(self):
        answers, problems = checkout_fields.clean('not a dict')
        self.assertEqual(answers, {})
        self.assertEqual(len(problems), 1)
        answers, _ = checkout_fields.clean({'terms_accepted': 'no', 'order_notes': ['x']})
        self.assertEqual(answers, {})

    def test_the_form_sends_its_inputs_by_key(self):
        post = QueryDict('cf_terms_accepted=1&cf_order_notes=Hi&email=a@b.c')
        self.assertEqual(
            checkout_fields.from_post(post), {'terms_accepted': '1', 'order_notes': 'Hi'}
        )


class RenderTests(_Isolated):
    def _render(self, request):
        return checkout_fields.render({'request': request})

    def test_nothing_to_ask_renders_nothing(self):
        self.assertEqual(self._render(RequestFactory().get('/checkout/quick/')), '')

    def test_fields_render_as_inputs_with_their_link(self):
        self.answer(NOTE, TERMS)
        html = self._render(RequestFactory().get('/checkout/quick/'))
        self.assertIn('name="cf_order_notes"', html)
        self.assertIn('maxlength="5"', html)
        self.assertIn('name="cf_terms_accepted" value="1" required', html)
        self.assertIn('href="/pages/terms/"', html)
        self.assertNotIn('checked', html)

    def test_a_re_render_keeps_what_the_shopper_sent(self):
        self.answer(NOTE, TERMS)
        request = RequestFactory().post(
            '/checkout/quick/', {'cf_order_notes': '<b>Hi</b>', 'cf_terms_accepted': '1'}
        )
        html = self._render(request)
        self.assertIn('&lt;b&gt;Hi&lt;/b&gt;</textarea>', html)
        self.assertIn(' checked', html)

    def test_an_app_cannot_inject_markup_through_a_label(self):
        self.answer({**NOTE, 'label': '<script>x</script>'})
        html = self._render(RequestFactory().get('/checkout/quick/'))
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_a_broken_app_never_breaks_the_checkout(self):
        def broken(value, **kwargs):
            raise RuntimeError('boom')

        hook_registry.register(MorpheusEvents.CHECKOUT_FIELDS, broken)
        self.assertEqual(checkout_fields.fields(), [])
        self.assertEqual(self._render(RequestFactory().get('/checkout/quick/')), '')
