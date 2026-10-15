"""Server-side sends ask one question: did this shopper agree?

The browser pixels have obeyed the banner since v0.91.0; the conversion APIs,
GA4 Measurement Protocol and audience uploads did not. ``core/consent.py``
answers for them: an order carries the shopper's choice from checkout (a
payment webhook has no visitor to ask), a request answers for its visitor,
and with neither the store-level answer applies — refuse when the store
manages consent, send when it does not.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from django.core.cache import cache
from django.test import RequestFactory, TestCase

from core.consent import allowed, decision_for, marketing_customer_ids, stamp
from plugins.installed.consent.models import ConsentLog
from plugins.installed.consent.services import COOKIE_NAME
from plugins.registry import app_registry


def _set_gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


def _request(**flags):
    req = RequestFactory().get('/')
    if flags:
        req.COOKIES[COOKIE_NAME] = json.dumps({'necessary': True, **flags})
    return req


def _order(**consent):
    return SimpleNamespace(metadata={'consent': consent} if consent else {})


class DecisionTests(TestCase):
    def setUp(self):
        _set_gdpr(True)

    def test_a_managed_store_with_no_cookie_grants_nothing(self):
        self.assertEqual(
            decision_for(_request()), {'managed': True, 'analytics': False, 'marketing': False}
        )

    def test_the_cookie_answers_per_category(self):
        d = decision_for(_request(marketing=True))
        self.assertEqual(d, {'managed': True, 'analytics': False, 'marketing': True})

    def test_no_request_means_no_visitor_and_nothing_granted(self):
        self.assertEqual(
            decision_for(None), {'managed': True, 'analytics': False, 'marketing': False}
        )

    def test_global_privacy_control_is_a_refusal(self):
        req = _request()
        req.META['HTTP_SEC_GPC'] = '1'
        self.assertFalse(allowed('marketing', request=req))

    def test_a_store_with_gdpr_off_is_unmanaged(self):
        _set_gdpr(False)
        self.assertTrue(allowed('marketing', request=_request()))
        self.assertTrue(allowed('analytics'))

    def test_with_the_consent_app_off_nothing_answers_and_the_store_is_unmanaged(self):
        self.addCleanup(app_registry.activate, 'consent')
        app_registry.deactivate('consent')
        self.assertEqual(
            decision_for(_request()), {'managed': False, 'analytics': False, 'marketing': False}
        )
        self.assertTrue(allowed('marketing'))

    def test_stamp_is_the_decision(self):
        self.assertEqual(stamp(_request(analytics=True)), decision_for(_request(analytics=True)))

    def test_an_unknown_category_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            allowed('functional')


class OrderStampTests(TestCase):
    def setUp(self):
        _set_gdpr(True)

    def test_the_stamp_beats_the_request(self):
        order = _order(managed=True, analytics=False, marketing=False)
        self.assertFalse(allowed('marketing', order=order, request=_request(marketing=True)))

    def test_a_stamped_yes_is_allowed(self):
        self.assertTrue(allowed('marketing', order=_order(managed=True, marketing=True)))

    def test_an_order_stamped_unmanaged_is_allowed(self):
        self.assertTrue(allowed('analytics', order=_order(managed=False)))

    def test_an_unstamped_order_on_a_managed_store_is_refused(self):
        self.assertFalse(allowed('marketing', order=_order()))

    def test_an_unstamped_order_on_an_unmanaged_store_is_allowed(self):
        _set_gdpr(False)
        self.assertTrue(allowed('marketing', order=_order()))

    def test_a_stamped_no_still_refuses_after_management_is_switched_off(self):
        # Review Focus 4: the shopper never agreed; switching the banner off later
        # does not make their old order consent.
        order = _order(managed=True, marketing=False)
        _set_gdpr(False)
        self.assertFalse(allowed('marketing', order=order))


class MarketingCustomersTests(TestCase):
    def setUp(self):
        _set_gdpr(True)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.yes = User.objects.create_user(username='yes', email='y@x.test', password='x')
        self.changed = User.objects.create_user(username='chg', email='c@x.test', password='x')
        self.never = User.objects.create_user(username='nev', email='n@x.test', password='x')
        ConsentLog.objects.create(customer=self.yes, session_key='a', marketing=True)
        ConsentLog.objects.create(customer=self.changed, session_key='b', marketing=True)
        # The later decision wins.
        later = ConsentLog.objects.create(customer=self.changed, session_key='b', marketing=False)
        ConsentLog.objects.filter(pk=later.pk).update(
            created_at=ConsentLog.objects.get(customer=self.yes).created_at.replace(year=2099)
        )

    def test_only_the_latest_yes_counts(self):
        self.assertEqual(marketing_customer_ids(), {self.yes.pk})

    def test_an_unmanaged_store_has_no_restriction(self):
        _set_gdpr(False)
        self.assertIsNone(marketing_customer_ids())
