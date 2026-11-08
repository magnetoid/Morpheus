"""The bot check on public forms: one seam, and no protected form without its tag.

A view asks `core.bot_check.passes(request, kind)`; a form without the
`{% bot_check "<kind>" %}` tag never sends a token, so the day a store switches the
check on, that form would refuse every real visitor. The scan reads every template
that can post one of the protected forms, in every theme.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase

from core import bot_check
from core.hooks import MorpheusEvents, hook_registry

_ROOT = Path(settings.BASE_DIR)
_FORM = re.compile(r'<form\b[^>]*>', re.I)


def _kind(path: str, tag: str) -> str | None:
    """The kind of protected form `tag` opens, or None."""
    if not (re.search(r'method=["\']?post', tag, re.I) or 'data-nl-form' in tag):
        return None
    if 'action="/contact/"' in tag or path.endswith(('do_not_sell.html', 'cms/_form.html')):
        return 'contact'
    if '/newsletter/subscribe/' in tag or 'data-nl-form' in tag:
        return 'newsletter'
    if re.search(r"url ['\"](account_login|account_signup|account_reset_password)['\"]", tag):
        return 'sign_in'
    if path.endswith('otp_request.html'):
        return 'sign_in'
    if path.endswith('affiliates/_apply_form.html'):
        return 'affiliates'
    return None


class BotCheckSeamTests(SimpleTestCase):
    def setUp(self):
        # Nothing answers: the real handlers are put back afterwards (CLAUDE.md).
        for event in (MorpheusEvents.BOT_CHECK_PASSES, MorpheusEvents.BOT_CHECK_WIDGET):
            saved = list(hook_registry._handlers.get(event, []))
            hook_registry._handlers[event] = []
            self.addCleanup(hook_registry._handlers.__setitem__, event, saved)

    def test_with_no_app_every_form_passes_and_shows_nothing(self):
        request = RequestFactory().post('/contact/', {})
        self.assertTrue(bot_check.passes(request, 'contact'))
        html = Template('{% load morph %}{% bot_check "contact" %}').render(Context({}))
        self.assertEqual(html, '')

    def test_an_app_that_refuses_is_heard(self):
        hook_registry.register(MorpheusEvents.BOT_CHECK_PASSES, lambda value, **kw: False)
        self.assertFalse(bot_check.passes(RequestFactory().post('/'), 'contact'))


class ProtectedFormTemplateTests(SimpleTestCase):
    def test_every_protected_form_carries_its_tag(self):
        roots = [
            _ROOT / 'themes' / 'library',
            _ROOT / 'templates',
            _ROOT / 'core' / 'auth' / 'templates',
            _ROOT / 'plugins' / 'installed',
        ]
        seen = {}
        for root in roots:
            for path in root.rglob('*.html'):
                rel = path.relative_to(_ROOT).as_posix()
                if '/templates/' not in f'/{rel}':
                    continue
                src = path.read_text()
                for m in _FORM.finditer(src):
                    kind = _kind(rel, m.group(0))
                    if not kind:
                        continue
                    body = src[m.end() : src.find('</form>', m.end())]
                    seen[rel] = kind
                    with self.subTest(template=rel):
                        self.assertIn(f'{{% bot_check "{kind}" %}}', body)
        # The scan found the forms it exists for (a scan that matches nothing passes).
        self.assertIn('themes/library/dot_books/templates/storefront/contact.html', seen)
        self.assertIn('templates/account/login.html', seen)
        self.assertIn('core/auth/templates/account/otp_request.html', seen)
        self.assertEqual(set(seen.values()), {'contact', 'newsletter', 'sign_in', 'affiliates'})
