"""GDPR/ePrivacy master switch (Settings → General → gdpr_enabled).

Default ON (no change to existing stores). When a merchant outside GDPR
jurisdiction turns it OFF, the self-service data-rights pages 404 and the
cookie-consent banner is suppressed.
"""

from __future__ import annotations

from django.core.cache import cache
from django.http import Http404
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

    # The data-rights views (account_data_export / account_delete) carry a
    # _gdpr_required() gate; they are not yet URL-routed (dead code — flagged
    # for Phase 2), so we unit-test the gate directly rather than over HTTP.

    def test_gate_default_passes(self):
        from plugins.installed.storefront.views.account import _gdpr_required

        _gdpr_required()  # no store row → default True → does not raise

    def test_gate_raises_when_disabled(self):
        from plugins.installed.storefront.views.account import _gdpr_required

        self._set_gdpr(False)
        with self.assertRaises(Http404):
            _gdpr_required()

    def test_gate_passes_when_reenabled(self):
        from plugins.installed.storefront.views.account import _gdpr_required

        self._set_gdpr(False)
        with self.assertRaises(Http404):
            _gdpr_required()
        self._set_gdpr(True)
        _gdpr_required()  # no raise

    def test_consent_banner_suppressed_when_disabled(self):
        req = RequestFactory().get('/')
        req.COOKIES = {}  # no decision cookie → banner would normally show
        tpl = Template('{% load consent %}{% consent_show as s %}{{ s }}')

        self._set_gdpr(True)
        self.assertEqual(tpl.render(Context({'request': req})).strip(), 'True')

        self._set_gdpr(False)
        self.assertEqual(tpl.render(Context({'request': req})).strip(), 'False')
