"""staff_sso SAML (Phase 4b) tests — the SAML provider runs the SAME gate /
JIT / MFA logic OIDC does, just via the ``saml`` provider id.

Mirrors ``test_adapter.py``'s mocked style: we construct a real allauth
``SocialLogin`` whose ``account.provider == services.SAML_PROVIDER_ID`` carrying
the mapped attributes, then call ``pre_social_login`` / ``populate_user`` — no
full SAML HTTP/XML round-trip. The only thing "mocked" is the IdP transport;
every allauth interface the adapter touches (the base adapter, the
``ImmediateHttpResponse`` exception, the SocialLogin/SocialAccount/EmailAddress
contract) is exercised for real.

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

# The SAML attribute name we tell the IdP carries group values. allauth stores
# raw SAML attributes in SocialAccount.extra_data keyed by their attribute NAME,
# so the group gate must look this up (not a logical "groups" key).
GROUPS_ATTR = 'http://schemas.example/ws/2005/05/identity/claims/groups'


def _request():
    rf = RequestFactory()
    req = rf.post('/auth/saml/staff_sso_saml/acs/finish/')
    from django.contrib.auth.models import AnonymousUser
    from django.contrib.sessions.backends.db import SessionStore

    req.session = SessionStore()
    req.user = AnonymousUser()
    return req


def _saml_sociallogin(email, *, verified=False, groups=None, uid='saml-nameid-1', user=None):
    """Build a SAML SocialLogin the way allauth's ACS view does: account.provider
    == 'saml', raw SAML attributes in extra_data (keyed by attr NAME), and an
    EmailAddress. We pass ``verified=False`` by default to prove SAML accepts the
    email on signature-trust, not a per-address verified flag."""
    extra = {}
    if groups is not None:
        extra[GROUPS_ATTR] = list(groups)
    account = SocialAccount(provider=services.SAML_PROVIDER_ID, uid=uid, extra_data=extra)
    if user is None:
        user = User(email='', username='')
    return SocialLogin(
        user=user,
        account=account,
        email_addresses=[EmailAddress(email=email, verified=verified, primary=True)],
    )


def _configure(*, domains='acme.com', groups='', enabled=True, mfa=True, saml_enabled=True):
    """Write plugin config (SAML section populated) + sync the SAML SocialApp +
    drive registry active-state, matching how ready() wires the provider in prod."""
    from plugins.models import PluginConfig

    PluginConfig.objects.update_or_create(
        plugin_name='staff_sso',
        defaults={
            'is_enabled': enabled,
            'config': {
                'allowed_domains': domains,
                'staff_groups': groups,
                'saml_enabled': saml_enabled,
                'saml_org_slug': 'staff_sso_saml',
                'saml_idp_entity_id': 'https://idp.example/entity',
                'saml_idp_sso_url': 'https://idp.example/sso',
                'saml_idp_x509cert': 'MIICert==',
                'saml_groups_attr': GROUPS_ATTR,
            },
        },
    )
    plugin = app_registry.get('staff_sso')
    if plugin is not None:
        plugin.invalidate_config_cache()

    # Register the SAML SocialApp exactly as ready() does, so allauth can resolve
    # the provider when the adapter calls sociallogin.connect() to link.
    services.sync_saml_app(services.get_saml_settings(plugin) if plugin else {})

    if enabled:
        app_registry._active.add('staff_sso')
    else:
        app_registry._active.discard('staff_sso')
    if mfa:
        app_registry._active.add('staff_mfa')
    else:
        app_registry._active.discard('staff_mfa')
    return plugin


class SamlJitProvisioning(TestCase):
    """(1) First SAML login JIT-creates a staff Customer; a second re-uses it."""

    def setUp(self):
        _configure(domains='acme.com')
        self.adapter = StaffSsoAdapter()

    def test_first_login_populates_staff_customer(self):
        sl = _saml_sociallogin('newhire@acme.com')
        # No existing user → pre_social_login leaves it for allauth to create.
        self.adapter.pre_social_login(_request(), sl)

        user = self.adapter.populate_user(
            _request(), sl, {'email': 'newhire@acme.com', 'first_name': 'New', 'last_name': 'Hire'}
        )
        self.assertEqual(user.email, 'newhire@acme.com')
        self.assertTrue(user.is_staff)
        # Provenance stamped from the SAML provider id + the NameID/uid.
        self.assertEqual(user.metadata['sso']['provider'], services.SAML_PROVIDER_ID)
        self.assertEqual(user.metadata['sso']['idp_sub'], 'saml-nameid-1')

    def test_existing_customer_is_linked_not_duplicated(self):
        existing = User.objects.create_user(
            username='boss@acme.com', email='boss@acme.com', is_staff=True
        )
        sl = _saml_sociallogin('boss@acme.com')
        self.adapter.pre_social_login(_request(), sl)
        self.assertEqual(sl.user.pk, existing.pk)
        self.assertEqual(User.objects.filter(email__iexact='boss@acme.com').count(), 1)


class SamlStaffGate(TestCase):
    """(2) The staff gate rejects a disallowed domain / group on the SAML path —
    no account, no session."""

    def setUp(self):
        self.adapter = StaffSsoAdapter()

    def test_disallowed_domain_rejected_no_account_no_session(self):
        _configure(domains='acme.com')
        sl = _saml_sociallogin('intruder@evil.com')
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(_request(), sl)
        self.assertEqual(ctx.exception.response.status_code, 403)
        self.assertFalse(User.objects.filter(email__iexact='intruder@evil.com').exists())

    def test_disallowed_group_rejected(self):
        # Domain not allowlisted; group gate active but the SAML groups attribute
        # doesn't intersect the configured staff groups.
        _configure(domains='', groups='staff,admins')
        sl = _saml_sociallogin('x@other.com', groups=['marketing', 'sales'])
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(_request(), sl)
        self.assertFalse(User.objects.filter(email__iexact='x@other.com').exists())

    def test_matching_saml_group_admitted_off_domain(self):
        # The configured SAML groups attribute carries a matching value → admit
        # even though the domain is not allowlisted. Proves the SAML-attr group
        # resolver works (raw attribute name, not a logical "groups" key).
        _configure(domains='', groups='staff')
        sl = _saml_sociallogin('contractor@partner.com', groups=['staff'])
        self.adapter.pre_social_login(_request(), sl)  # must NOT raise


class SamlRespectsMfa(TestCase):
    """(3) THE HEADLINE: an enrolled-staff SAML login is forced through the TOTP
    challenge via ImmediateHttpResponse — allauth's login() is NOT allowed to
    complete (no MFA bypass over SAML, mirroring the OIDC guarantee)."""

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
        sl = _saml_sociallogin('mfa@acme.com')
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(_request(), sl)
        resp = ctx.exception.response
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/auth/mfa/challenge/', resp.url)

    def test_with_mfa_disabled_no_challenge(self):
        _configure(domains='acme.com', mfa=False)
        sl = _saml_sociallogin('mfa@acme.com')
        self.adapter.pre_social_login(_request(), sl)  # no challenge → no raise


class SamlEmailTrust(TestCase):
    """SAML accepts the signed-assertion email even without a per-address
    verified flag (trust comes from the validated signature). But an assertion
    with NO email is still rejected — we can't identify the user."""

    def setUp(self):
        self.adapter = StaffSsoAdapter()
        _configure(domains='acme.com')

    def test_unverified_flag_still_links_existing(self):
        existing = User.objects.create_user(
            username='ceo@acme.com', email='ceo@acme.com', is_staff=True
        )
        # verified=False — SAML must STILL link (unlike OIDC) because the
        # assertion signature is the trust anchor.
        sl = _saml_sociallogin('ceo@acme.com', verified=False)
        self.adapter.pre_social_login(_request(), sl)
        self.assertEqual(sl.user.pk, existing.pk)

    def test_no_email_rejected(self):
        sl = _saml_sociallogin('')
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(_request(), sl)
        self.assertEqual(ctx.exception.response.status_code, 403)
        self.assertFalse(_user_in_db(sl.user))


class SamlSyncAndConfig(TestCase):
    """SocialApp sync round-trips the allauth SAML settings shape, and disabling
    SAML removes the app (disable-safe)."""

    def test_metadata_url_settings_shape(self):
        cfg = {
            'enabled': True,
            'org_slug': 'acme_saml',
            'idp_metadata_url': 'https://idp.example/metadata',
            'idp_entity_id': '',
            'idp_sso_url': '',
            'idp_x509cert': '',
            'email_attr': 'my-email-attr',
            'groups_attr': 'groups',
        }
        s = services.build_saml_app_settings(cfg)
        self.assertEqual(s['idp'], {'metadata_url': 'https://idp.example/metadata'})
        # A configured email attr OVERRIDES only the email key.
        self.assertEqual(s['attribute_mapping']['email'], 'my-email-attr')
        # Groups are NOT mapped here — the adapter reads them from raw extra_data
        # by the saml_groups_attr name, so attribute_mapping carries no groups key.
        self.assertNotIn('groups', s['attribute_mapping'])

    def test_attribute_mapping_merges_onto_allauth_default(self):
        """REGRESSION (BLOCKER): configuring ONLY groups_attr must NOT wipe
        allauth's built-in email/uid/first_name/last_name maps. allauth's
        ``_extract`` does ``provider_config.get("attribute_mapping", default)`` —
        any mapping we pass *replaces* the default, so build_saml_app_settings
        MUST seed from SAMLProvider.default_attribute_mapping. Fails against the
        old replace-behaviour (email key absent → empty email → 403); passes once
        the mapping is merged onto the default."""
        from allauth.socialaccount.providers.saml.provider import SAMLProvider

        cfg = {
            'enabled': True,
            'org_slug': 'acme_saml',
            'idp_metadata_url': '',
            'idp_entity_id': 'https://idp/entity',
            'idp_sso_url': 'https://idp/sso',
            'idp_x509cert': 'CERT==',
            # email / first / last left blank — ONLY the groups attr is set.
            'groups_attr': GROUPS_ATTR,
        }
        s = services.build_saml_app_settings(cfg)
        mapping = s['attribute_mapping']
        default = SAMLProvider.default_attribute_mapping
        # The built-in email mapping survives untouched (this is what _verified_email
        # depends on; if it's gone the login 403s).
        self.assertEqual(mapping['email'], default['email'])
        # And the rest of allauth's defaults are intact too.
        for key in ('uid', 'email_verified', 'first_name', 'last_name', 'username'):
            self.assertEqual(mapping[key], default[key])
        # allauth's _extract reads exactly this dict via
        # ``provider_config.get("attribute_mapping", default)`` — drive that same
        # lookup to prove the effective email mapping resolves to allauth's default.
        effective = s.get('attribute_mapping', SAMLProvider.default_attribute_mapping)
        self.assertEqual(effective['email'], default['email'])

    def test_assertions_must_be_signed(self):
        """Staff boundary hardening: the synced SocialApp requires signed SAML
        assertions (allauth maps advanced.want_assertion_signed →
        security.wantAssertionsSigned, which it otherwise defaults to False)."""
        from allauth.socialaccount.models import SocialApp

        _configure(saml_enabled=True)
        app = SocialApp.objects.get(
            provider=services.SAML_PROVIDER, provider_id=services.SAML_PROVIDER_ID
        )
        self.assertIs(app.settings['advanced']['want_assertion_signed'], True)

    def test_explicit_idp_settings_shape(self):
        cfg = {
            'enabled': True,
            'org_slug': 'acme_saml',
            'idp_metadata_url': '',
            'idp_entity_id': 'https://idp/entity',
            'idp_sso_url': 'https://idp/sso',
            'idp_x509cert': 'CERT==',
        }
        s = services.build_saml_app_settings(cfg)
        # We store our flat triple in SocialApp.settings['idp']; allauth's
        # build_saml_config() reads entity_id/sso_url/x509cert from it and maps
        # them to onelogin's entityId/singleSignOnService/x509cert at login time.
        self.assertEqual(
            s['idp'],
            {
                'entity_id': 'https://idp/entity',
                'sso_url': 'https://idp/sso',
                'x509cert': 'CERT==',
            },
        )

    def test_is_saml_configured(self):
        self.assertFalse(services.is_saml_configured({'enabled': False, 'idp_metadata_url': 'x'}))
        self.assertTrue(services.is_saml_configured({'enabled': True, 'idp_metadata_url': 'x'}))
        self.assertTrue(
            services.is_saml_configured(
                {
                    'enabled': True,
                    'idp_entity_id': 'e',
                    'idp_sso_url': 's',
                    'idp_x509cert': 'c',
                }
            )
        )
        self.assertFalse(
            services.is_saml_configured({'enabled': True, 'idp_entity_id': 'e', 'idp_sso_url': 's'})
        )

    def test_configured_then_disabled_removes_app(self):
        from allauth.socialaccount.models import SocialApp

        _configure(saml_enabled=True)
        self.assertTrue(
            SocialApp.objects.filter(
                provider=services.SAML_PROVIDER, provider_id=services.SAML_PROVIDER_ID
            ).exists()
        )
        # SAML disabled → app removed.
        services.sync_saml_app({})
        self.assertFalse(SocialApp.objects.filter(provider_id=services.SAML_PROVIDER_ID).exists())
