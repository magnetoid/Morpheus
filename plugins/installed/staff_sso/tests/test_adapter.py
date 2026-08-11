"""staff_sso adapter tests — JIT provisioning, the staff gate, the MFA
no-bypass, the unverified-email guard, and disable-safety.

We unit-test the adapter logic directly: construct a real allauth ``SocialLogin``
with a fake account/email + claims and call ``pre_social_login`` /
``populate_user``. The IdP transport is the only thing mocked — every allauth
interface the adapter touches (the adapter base, the signal contract, the
exception type) is exercised for real.

Run:
    DATABASE_URL='sqlite:///:memory:' ... manage.py test plugins.installed.staff_sso
"""

from __future__ import annotations

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from plugins.installed.staff_sso import services
from plugins.installed.staff_sso.adapters import StaffSsoAdapter, _user_in_db
from plugins.registry import app_registry

User = get_user_model()


# ── Fixtures ─────────────────────────────────────────────────────────────────
def _request():
    rf = RequestFactory()
    req = rf.get('/auth/openid_connect/staff_sso/login/callback/')
    # Adapters/middleware in this path expect a session for the MFA gate, and
    # a .user for the context processors that run when we render() a page.
    from django.contrib.auth.models import AnonymousUser
    from django.contrib.sessions.backends.db import SessionStore

    req.session = SessionStore()
    req.user = AnonymousUser()
    return req


def _sociallogin(email, *, verified=True, claims=None, uid='idp-sub-1', user=None):
    """Build a SocialLogin the way allauth does mid-flow: a not-yet-saved user,
    an unsaved SocialAccount carrying the claims, and the asserted email."""
    account = SocialAccount(provider=services.PROVIDER_ID, uid=uid, extra_data=dict(claims or {}))
    if user is None:
        user = User(email='', username='')
    sl = SocialLogin(
        user=user,
        account=account,
        email_addresses=[EmailAddress(email=email, verified=verified, primary=True)],
    )
    return sl


def _configure(*, domains='acme.com', groups='', enabled=True, mfa=True):
    """Write the plugin config + force registry active-state for the test."""
    from plugins.models import PluginConfig

    PluginConfig.objects.update_or_create(
        plugin_name='staff_sso',
        defaults={
            'is_enabled': enabled,
            'config': {
                'oidc_issuer': 'https://acme.example/.well-known/openid-configuration',
                'oidc_client_id': 'cid',
                'oidc_client_secret': 'secret',
                'allowed_domains': domains,
                'staff_groups': groups,
            },
        },
    )
    plugin = app_registry.get('staff_sso')
    if plugin is not None:
        plugin.invalidate_config_cache()

    # Register the OIDC SocialApp exactly as the plugin's ready() does in prod,
    # so allauth can resolve the provider when the adapter calls
    # sociallogin.connect() to link an existing Customer (the real link path).
    services.sync_social_app(services.get_settings(plugin) if plugin else {})

    # Drive is_active() deterministically regardless of first-run DB seeding.
    if enabled:
        app_registry._active.add('staff_sso')
    else:
        app_registry._active.discard('staff_sso')
    if mfa:
        app_registry._active.add('staff_mfa')
    else:
        app_registry._active.discard('staff_mfa')
    return plugin


class JitProvisioning(TestCase):
    """First SSO login creates a linked staff Customer; a second re-uses it."""

    def setUp(self):
        _configure(domains='acme.com')
        self.adapter = StaffSsoAdapter()

    def test_first_login_populates_staff_customer(self):
        sl = _sociallogin('newhire@acme.com', claims={'sub': 'idp-1', 'given_name': 'New'})
        # No existing user → pre_social_login leaves it for allauth to create.
        self.adapter.pre_social_login(_request(), sl)

        user = self.adapter.populate_user(
            _request(), sl, {'email': 'newhire@acme.com', 'first_name': 'New', 'last_name': 'Hire'}
        )
        self.assertEqual(user.email, 'newhire@acme.com')
        self.assertTrue(user.is_staff)
        self.assertEqual(user.metadata['sso']['provider'], services.PROVIDER_ID)
        self.assertEqual(user.metadata['sso']['idp_sub'], 'idp-sub-1')

    def test_existing_customer_is_linked_not_duplicated(self):
        existing = User.objects.create_user(
            username='boss@acme.com', email='boss@acme.com', is_staff=True
        )
        sl = _sociallogin('boss@acme.com')
        self.adapter.pre_social_login(_request(), sl)
        # The adapter attached the existing Customer to the sociallogin.
        self.assertEqual(sl.user.pk, existing.pk)
        self.assertEqual(User.objects.filter(email__iexact='boss@acme.com').count(), 1)

    def test_existing_non_staff_customer_is_promoted(self):
        # A gate-passing identity matching an EXISTING customer-account user
        # (is_staff=False) must be promoted — populate_user (where is_staff is
        # set) only runs on the JIT-create path, so a linked non-staff user
        # would otherwise log in but never reach the dashboard.
        existing = User.objects.create_user(
            username='shopper@acme.com', email='shopper@acme.com', is_staff=False
        )
        sl = _sociallogin('shopper@acme.com')
        self.adapter.pre_social_login(_request(), sl)

        self.assertEqual(sl.user.pk, existing.pk)
        existing.refresh_from_db()
        self.assertTrue(existing.is_staff)
        # Linked, not duplicated.
        self.assertEqual(User.objects.filter(email__iexact='shopper@acme.com').count(), 1)


class StaffGate(TestCase):
    def setUp(self):
        self.adapter = StaffSsoAdapter()

    def test_disallowed_domain_rejected_no_account_no_session(self):
        _configure(domains='acme.com')
        sl = _sociallogin('intruder@evil.com')
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(_request(), sl)
        self.assertEqual(ctx.exception.response.status_code, 403)
        self.assertFalse(User.objects.filter(email__iexact='intruder@evil.com').exists())

    def test_disallowed_group_rejected(self):
        # Domain not allowlisted; group gate active but claim doesn't intersect.
        _configure(domains='', groups='staff,admins')
        sl = _sociallogin('x@other.com', claims={'groups': ['marketing', 'sales']})
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(_request(), sl)
        self.assertFalse(User.objects.filter(email__iexact='x@other.com').exists())

    def test_matching_group_admitted_off_domain(self):
        _configure(domains='', groups='staff')
        sl = _sociallogin('contractor@partner.com', claims={'groups': ['staff']})
        # Must NOT raise — the group claim admits an off-domain user.
        self.adapter.pre_social_login(_request(), sl)


class SsoRespectsMfa(TestCase):
    """The headline: an enrolled-staff SSO login is forced through TOTP, and
    allauth's login() is NOT allowed to complete (ImmediateHttpResponse)."""

    def setUp(self):
        self.adapter = StaffSsoAdapter()
        self.user = User.objects.create_user(
            username='mfa@acme.com', email='mfa@acme.com', is_staff=True
        )
        from plugins.installed.staff_mfa.models import StaffMfaDevice

        StaffMfaDevice.objects.create(
            user=self.user, secret='JBSWY3DPEHPK3PXP', confirmed_at=timezone.now()
        )

    def test_enrolled_staff_forced_to_totp_challenge(self):
        _configure(domains='acme.com', mfa=True)
        sl = _sociallogin('mfa@acme.com')
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(_request(), sl)
        resp = ctx.exception.response
        # second_factor_response redirects to the staff_mfa challenge view.
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/auth/mfa/challenge/', resp.url)

    def test_with_mfa_disabled_no_challenge(self):
        _configure(domains='acme.com', mfa=False)
        sl = _sociallogin('mfa@acme.com')
        # MFA inactive → no ImmediateHttpResponse; login proceeds normally.
        self.adapter.pre_social_login(_request(), sl)


class UnverifiedEmailGuard(TestCase):
    """Account-takeover guard: an unverified IdP email is never auto-linked
    to an existing Customer (and never creates a session)."""

    def setUp(self):
        self.adapter = StaffSsoAdapter()
        _configure(domains='acme.com')

    def test_unverified_email_not_linked(self):
        victim = User.objects.create_user(
            username='ceo@acme.com', email='ceo@acme.com', is_staff=True
        )
        sl = _sociallogin('ceo@acme.com', verified=False)
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(_request(), sl)
        self.assertEqual(ctx.exception.response.status_code, 403)
        # The existing victim account was NOT attached to the unverified login.
        # (sl.user is the throwaway unsaved instance — Customer.id defaults to a
        # uuid at construction, so we assert DB-non-residency, not pk-is-None.)
        self.assertNotEqual(getattr(sl.user, 'pk', None), victim.pk)
        self.assertFalse(_user_in_db(sl.user))


class DisableSafe(TestCase):
    """Blank config → no provider registered; SSO inert (email-OTP unaffected)."""

    def test_blank_config_registers_no_socialapp(self):
        from allauth.socialaccount.models import SocialApp

        services.sync_social_app({})
        self.assertFalse(
            SocialApp.objects.filter(
                provider=services.PROVIDER, provider_id=services.PROVIDER_ID
            ).exists()
        )

    def test_configured_then_blank_removes_socialapp(self):
        from allauth.socialaccount.models import SocialApp

        cfg = {
            'issuer': 'https://acme.example/.well-known/openid-configuration',
            'client_id': 'cid',
            'client_secret': 'secret',
            'scopes': 'openid email profile',
            'allowed_domains': ['acme.com'],
            'staff_groups': [],
        }
        services.sync_social_app(cfg)
        self.assertTrue(SocialApp.objects.filter(provider_id=services.PROVIDER_ID).exists())
        services.sync_social_app({})  # disable / clear config
        self.assertFalse(SocialApp.objects.filter(provider_id=services.PROVIDER_ID).exists())


class GateUnit(TestCase):
    """Pure gate_decision() truth table — fail-closed when nothing configured."""

    def test_empty_config_fails_closed(self):
        self.assertFalse(
            services.gate_decision(
                {'allowed_domains': [], 'staff_groups': []}, email='a@acme.com', groups=[]
            )
        )

    def test_domain_match(self):
        cfg = {'allowed_domains': ['acme.com'], 'staff_groups': []}
        self.assertTrue(services.gate_decision(cfg, email='a@acme.com', groups=[]))
        self.assertFalse(services.gate_decision(cfg, email='a@evil.com', groups=[]))

    def test_group_match(self):
        cfg = {'allowed_domains': [], 'staff_groups': ['admins']}
        self.assertTrue(services.gate_decision(cfg, email='a@x.com', groups=['Admins']))
        self.assertFalse(services.gate_decision(cfg, email='a@x.com', groups=['users']))
