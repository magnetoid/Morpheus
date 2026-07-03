"""The merchant-edited transactional-email copy is CONTRIBUTED by cms via
the EMAIL_TEMPLATE_OVERRIDE filter — core.emails no longer imports
cms.models. Disabling cms means emails fall back to filesystem templates.
"""

# Lazy imports inside test methods are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import TestCase

_HANDLERS_PY = Path(settings.BASE_DIR) / 'core/emails/handlers.py'


class EmailTemplateOverrideTests(TestCase):
    def test_core_emails_no_longer_imports_cms(self):
        src = _HANDLERS_PY.read_text(encoding='utf-8')
        self.assertNotIn(
            'plugins.installed',
            src,
            'core.emails.handlers imports a plugin — overrides belong in the '
            'EMAIL_TEMPLATE_OVERRIDE subscriber',
        )

    def test_cms_is_subscribed(self):
        from core.hooks import MorpheusEvents, hook_registry

        quals = {
            getattr(hook_registry._unpack(entry)[1], '__qualname__', '')
            for entry in hook_registry._handlers.get(MorpheusEvents.EMAIL_TEMPLATE_OVERRIDE, [])
        }
        self.assertTrue(any('CmsPlugin' in q for q in quals), 'cms not subscribed')

    def test_no_row_falls_back_to_filesystem(self):
        from core.emails.handlers import _db_override

        self.assertEqual(_db_override('emails/order_placed', {}), (None, None, None))

    def test_active_row_supplies_rendered_copy(self):
        from core.emails.handlers import _db_override
        from plugins.installed.cms.models import EmailTemplate

        EmailTemplate.objects.create(
            key='order_placed',
            is_active=True,
            subject='Thanks, {{ name }}!',
            body_text='Hi {{ name }}, your order is in.',
        )
        subject, text, html = _db_override('emails/order_placed', {'name': 'Ada'})
        self.assertEqual(subject, 'Thanks, Ada!')
        self.assertEqual(text, 'Hi Ada, your order is in.')
        self.assertIsNone(html)

    def test_inactive_row_is_ignored(self):
        from core.emails.handlers import _db_override
        from plugins.installed.cms.models import EmailTemplate

        EmailTemplate.objects.create(key='order_placed', is_active=False, subject='nope')
        self.assertEqual(_db_override('emails/order_placed', {}), (None, None, None))

    def test_broken_merchant_template_falls_back(self):
        from core.emails.handlers import _db_override
        from plugins.installed.cms.models import EmailTemplate

        EmailTemplate.objects.create(
            key='order_placed',
            is_active=True,
            subject='{% invalid_tag %}',
        )
        self.assertEqual(_db_override('emails/order_placed', {}), (None, None, None))
