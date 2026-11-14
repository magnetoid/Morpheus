"""Every theme's checkout forms carry `{% checkout_fields %}` inside the form that
places the order.

A theme whose form leaves the tag out never sends the answers, so the day a store
switches the terms tick on, ``completeOrder`` refuses every order placed from that
form. The scan reads the review step and the one-page checkout of every theme.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

_THEMES = Path(__file__).resolve().parent / 'library'
_FORMS = ('checkout_review.html', 'checkout_one_page.html')


def _order_form(text: str) -> str:
    """The first POST form: the one whose button places the order."""
    start = re.search(r'<form\b[^>]*method="post"[^>]*>', text, re.I)
    if start is None:
        return ''
    end = text.find('</form>', start.end())
    return text[start.end() : end if end != -1 else len(text)]


class CheckoutFieldsInEveryThemeTests(SimpleTestCase):
    def test_every_checkout_form_asks_the_apps_fields(self):
        themes = sorted(p for p in _THEMES.iterdir() if (p / 'templates' / 'storefront').is_dir())
        self.assertGreaterEqual(len(themes), 5)
        for theme in themes:
            for name in _FORMS:
                path = theme / 'templates' / 'storefront' / name
                if not path.exists():
                    continue
                with self.subTest(theme=theme.name, form=name):
                    form = _order_form(path.read_text())
                    self.assertIn('type="submit"', form)
                    self.assertIn('{% checkout_fields %}', form)
                    tag = form.index('{% checkout_fields %}')
                    self.assertLess(
                        tag, form.index('type="submit"'), 'the fields go above the button'
                    )
