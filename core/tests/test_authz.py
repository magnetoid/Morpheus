"""The authorization seam.

These tests pin the two properties that make it safe to ship an authorization
layer into a running store:

  1. It **fails open on absence.** No answerer installed → the pre-RBAC
     behaviour (`is_staff`), never a lockout.
  2. It **denies only when explicitly told to.** The default mode records what
     it would have denied and denies nothing.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from core import authz


def _plugin():
    from plugins.registry import app_registry

    return app_registry.get('rbac')


def _set_mode(mode: str) -> None:
    p = _plugin()
    p.set_config('enforcement_mode', mode)
    p.invalidate_config_cache()


class CapabilityResolutionTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.owner = U.objects.create_user(
            username='authz_owner', email='o@x.io', password='x', is_staff=True, is_superuser=True
        )
        self.staff = U.objects.create_user(
            username='authz_staff', email='s@x.io', password='x', is_staff=True
        )
        self.shopper = U.objects.create_user(username='authz_shopper', email='c@x.io', password='x')

    def test_superuser_always_passes(self):
        """The escape hatch: a misconfigured role must never be unrecoverable."""
        self.assertTrue(authz.has_capability(self.owner, 'orders.refund'))

    def test_anonymous_never_passes(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(authz.has_capability(AnonymousUser(), 'orders.read'))
        self.assertFalse(authz.has_capability(None, 'orders.read'))

    def test_staff_without_a_role_holds_nothing(self):
        """rbac is active and answers: no binding means no capability."""
        self.assertFalse(authz.has_capability(self.staff, 'orders.refund'))

    def test_granting_a_role_grants_its_capabilities(self):
        # rbac seeds the built-in roles in ready(), which runs at boot — before
        # the test database exists — so the table is empty here. Seed it.
        from plugins.installed.rbac.models import Role
        from plugins.installed.rbac.services import grant

        Role.ensure_system_roles()
        self.assertIsNotNone(grant(self.staff, 'support_agent'), 'role grant failed')
        self.assertTrue(authz.has_capability(self.staff, 'orders.refund'))
        # …and only its capabilities — support_agent has no catalog.write.
        self.assertFalse(authz.has_capability(self.staff, 'catalog.write'))

    def test_falls_back_to_is_staff_when_nothing_answers(self):
        """The safety property: with no authority installed, behave as before.

        Simulated by emptying the filter's subscriber list, which is what a
        disabled or absent rbac produces at the bus level.
        """
        from core.hooks import MorpheusEvents, hook_registry

        event = MorpheusEvents.AUTHZ_CAPABILITY_CHECK
        saved = hook_registry._handlers.get(event, [])
        hook_registry._handlers[event] = []
        try:
            self.assertTrue(authz.has_capability(self.staff, 'orders.refund'))
            self.assertFalse(authz.has_capability(self.shopper, 'orders.refund'))
        finally:
            hook_registry._handlers[event] = saved


class EnforcementModeTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user(
            username='mode_staff', email='m@x.io', password='x', is_staff=True
        )
        self.addCleanup(_set_mode, 'log')

    def test_default_is_log_only(self):
        _plugin().set_config('enforcement_mode', '')
        _plugin().invalidate_config_cache()
        self.assertEqual(authz.enforcement_mode(), authz.MODE_LOG)

    def test_log_mode_allows_a_failed_check(self):
        """The whole point of log mode: report, don't block."""
        _set_mode('log')
        self.assertTrue(authz.check(self.staff, 'orders.refund'))

    def test_enforce_mode_denies_a_failed_check(self):
        _set_mode('enforce')
        self.assertFalse(authz.check(self.staff, 'orders.refund'))

    def test_off_mode_skips_the_check_entirely(self):
        _set_mode('off')
        self.assertTrue(authz.check(self.staff, 'orders.refund'))

    def test_a_would_be_denial_is_audited_in_log_mode(self):
        """Log mode is only useful if the merchant can read what it caught."""
        from core.audit.models import AuditEvent

        _set_mode('log')
        authz.check(self.staff, 'orders.refund', target='/dashboard/x/')
        self.assertTrue(
            AuditEvent.objects.filter(event_type='authz.would_deny').exists(),
            'log mode must record what it would have denied',
        )

    def test_an_enforced_denial_is_audited(self):
        from core.audit.models import AuditEvent

        _set_mode('enforce')
        authz.check(self.staff, 'orders.refund', target='/dashboard/x/')
        self.assertTrue(AuditEvent.objects.filter(event_type='authz.denied').exists())


class RequireCapabilityDecoratorTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user(
            username='deco_staff', email='d@x.io', password='x', is_staff=True
        )
        self.rf = RequestFactory()
        self.addCleanup(_set_mode, 'log')

        from django.http import HttpResponse

        @authz.require_capability('orders.refund')
        def view(request):
            return HttpResponse('did the thing')

        self.view = view

    def _req(self, **headers):
        r = self.rf.post('/dashboard/orders/1/refund/', **headers)
        r.user = self.staff
        return r

    def test_log_mode_lets_the_view_run(self):
        _set_mode('log')
        self.assertEqual(self.view(self._req()).status_code, 200)

    def test_enforce_mode_returns_403(self):
        _set_mode('enforce')
        self.assertEqual(self.view(self._req()).status_code, 403)

    def test_enforce_mode_returns_JSON_for_an_ajax_request(self):
        """A dashboard fetch endpoint must fail as JSON, or the JS shows a
        false 'Saved' — the dashboard-ajax-json-contract landmine."""
        import json

        _set_mode('enforce')
        resp = self.view(self._req(HTTP_X_REQUESTED_WITH='XMLHttpRequest'))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp['Content-Type'], 'application/json')
        self.assertFalse(json.loads(resp.content)['ok'])

    def test_the_required_capability_is_introspectable(self):
        """Tooling and tests need to see what a view demands without calling it."""
        self.assertEqual(self.view.required_capability, 'orders.refund')


class CapabilityVocabularyTests(TestCase):
    """Every capability a view demands must be one a role can actually hold.

    A typo'd or invented capability is invisible until someone switches to
    enforce mode — and then it denies *everyone* except superusers, forever,
    because no role grants it. This caught `marketing.write` (there is no
    marketing.* capability) before it shipped.
    """

    def _vocabulary(self) -> set[str]:
        from plugins.installed.rbac.models import _DEFAULT_TEMPLATES

        return {cap for caps in _DEFAULT_TEMPLATES.values() for cap in caps}

    def _required_capabilities(self) -> dict[str, str]:
        """{'module:view': 'capability'} for every gated view on disk."""
        import pathlib
        import re

        from django.conf import settings

        root = pathlib.Path(settings.BASE_DIR) / 'plugins' / 'installed'
        found: dict[str, str] = {}
        pattern = re.compile(r"@require_capability\(\s*'([^']+)'.*?\)\s*\ndef\s+(\w+)", re.S)
        for path in root.rglob('*.py'):
            for cap, view in pattern.findall(path.read_text(encoding='utf-8', errors='ignore')):
                found[f'{path.name}:{view}'] = cap
        return found

    def test_every_required_capability_is_grantable(self):
        vocab = self._vocabulary()
        required = self._required_capabilities()
        self.assertTrue(required, 'no gated views found — did the decorator move?')
        bogus = {k: v for k, v in required.items() if v not in vocab}
        self.assertEqual(
            bogus,
            {},
            f'these views demand capabilities no role can hold: {bogus}. '
            f'Add them to rbac _DEFAULT_TEMPLATES or use an existing one. '
            f'Vocabulary: {sorted(vocab)}',
        )

    def test_the_money_paths_are_gated(self):
        """Refunds and destructive catalog edits must not be reachable on
        is_staff alone. Pins the wiring, so removing a decorator fails here."""
        required = self._required_capabilities()
        self.assertEqual(required.get('orders.py:order_refund'), 'orders.refund')
        self.assertEqual(required.get('products.py:product_delete'), 'catalog.write')
        self.assertEqual(required.get('customers.py:customer_delete'), 'crm.write')
