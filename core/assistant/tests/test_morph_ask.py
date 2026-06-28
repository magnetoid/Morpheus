"""morph_ask templatetag must HTML-escape its dynamic values.

Today the only call site is the no-arg `{% morph_ask %}` (values come from the
regex-constrained _auto_prefill), so this is hardening — but a future caller
passing a variable must not be able to break out of the button's attributes.
"""

from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase


class MorphAskEscapingTest(SimpleTestCase):
    def _render(self, **ctx):
        request = RequestFactory().get('/dashboard/')
        tmpl = Template(
            '{% load morph_assistant %}{% morph_ask context_label=cl prefill=pf label=lb %}'
        )
        return tmpl.render(Context({'request': request, **ctx}))

    def test_dynamic_values_are_escaped(self):
        evil = '"><img src=x onerror=alert(1)>'
        out = self._render(cl=evil, pf=evil, lb=evil)
        # The raw breakout payload must never appear unescaped.
        self.assertNotIn('<img src=x onerror=alert(1)>', out)
        self.assertNotIn('data-prefill=""><img', out)
        # Its escaped form proves the value rendered (just safely).
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', out)

    def test_benign_values_still_render(self):
        out = self._render(cl='orders', pf='show my orders', lb='Ask Linda')
        self.assertIn('Ask Linda', out)
        self.assertIn('about orders', out)
        self.assertIn('data-prefill="show my orders"', out)
