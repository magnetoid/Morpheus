"""GDPR/ePrivacy master switch (Settings → General → gdpr_enabled).

Default ON (no change to existing stores). When a merchant outside GDPR
jurisdiction turns it OFF, the cookie-consent banner is suppressed.

The self-service data-rights views (export / delete) and their
``gdpr_required()`` gate now live in the ``gdpr`` plugin — see
``plugins/installed/gdpr/tests/test_gdpr.py`` for those. This file keeps only
the storefront-owned surface: the consent banner suppression.
"""

from __future__ import annotations

from django.core.cache import cache
from django.template import Context, Template
from django.test import RequestFactory, TestCase

from core.models import StoreSettings


class GdprToggleTests(TestCase):
    def setUp(self):
        cache.delete('morph:gdpr_enabled')

    def _set_gdpr(self, on: bool):
        s = StoreSettings.objects.first() or StoreSettings()
        s.gdpr_enabled = on
        s.save()
        cache.delete('morph:gdpr_enabled')

    def test_consent_banner_suppressed_when_disabled(self):
        req = RequestFactory().get('/')
        req.COOKIES = {}  # no decision cookie → banner would normally show
        tpl = Template('{% load consent %}{% consent_show as s %}{{ s }}')

        self._set_gdpr(True)
        self.assertEqual(tpl.render(Context({'request': req})).strip(), 'True')

        self._set_gdpr(False)
        self.assertEqual(tpl.render(Context({'request': req})).strip(), 'False')
