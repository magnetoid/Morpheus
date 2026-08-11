"""staff_sso login-button surface tests — the config-gated SSO link.

Covers the Phase 4a surface: the ``{% staff_sso_login_url %}`` tag and the
``staff_sso/blocks/login_button.html`` block must produce a "Sign in with SSO"
link ONLY when the plugin is enabled AND an OIDC IdP is configured (a SocialApp
exists), and render nothing otherwise — so disabling/unconfiguring SSO removes
the button cleanly.

The provider login URL is computed through allauth's real adapter (no mocks of
our own code); only the IdP transport is absent (no live IdP is contacted to
build a login URL).

Run:
    DATABASE_URL='sqlite:///:memory:' ... manage.py test plugins.installed.staff_sso
"""

from __future__ import annotations

from django.template import Context, Template
from django.test import RequestFactory, TestCase

from plugins.installed.staff_sso import services
from plugins.registry import app_registry


def _request():
    rf = RequestFactory()
    req = rf.get('/auth/login/')
    from django.contrib.auth.models import AnonymousUser
    from django.contrib.sessions.backends.db import SessionStore

    # render_to_string runs the project's context processors (currency, cart…)
    # which read request.session / request.user — supply both.
    req.session = SessionStore()
    req.user = AnonymousUser()
    return req


def _configure(*, domains='acme.com', enabled=True):
    """Write the plugin config + sync the SocialApp + drive registry state,
    matching how the plugin's ready() wires the provider in prod."""
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
            },
        },
    )
    plugin = app_registry.get('staff_sso')
    if plugin is not None:
        plugin.invalidate_config_cache()
    services.sync_social_app(services.get_settings(plugin) if plugin else {})

    if enabled:
        app_registry._active.add('staff_sso')
    else:
        app_registry._active.discard('staff_sso')
    return plugin


def _render_tag(request):
    """Render the tag in isolation and return the captured URL string."""
    tmpl = Template('{% load staff_sso %}{% staff_sso_login_url as sso_url %}{{ sso_url }}')
    return tmpl.render(Context({'request': request})).strip()


def _render_block(request, extra=None):
    """Render the actual block template the StorefrontBlock points at."""
    from django.template.loader import render_to_string

    ctx = {'request': request}
    if extra:
        ctx.update(extra)
    return render_to_string('staff_sso/blocks/login_button.html', ctx, request=request)


class ConfiguredButtonRenders(TestCase):
    """Enabled + a configured SocialApp → the tag returns a URL and the block
    renders the 'Sign in with SSO' link."""

    def setUp(self):
        _configure(domains='acme.com', enabled=True)

    def test_tag_returns_login_url(self):
        url = _render_tag(_request())
        self.assertTrue(url, 'expected a non-empty provider login URL')
        # allauth builds the openid_connect login URL off the provider id.
        self.assertIn(services.PROVIDER_ID, url)

    def test_block_renders_sso_link(self):
        html = _render_block(_request())
        self.assertIn('Sign in with SSO', html)
        self.assertIn('process=login', html)
        # default next when none supplied by the page.
        self.assertIn('/dashboard/', html)

    def test_block_respects_next_param(self):
        html = _render_block(_request(), extra={'next': '/dashboard/orders/'})
        self.assertIn('next=%2Fdashboard%2Forders%2F', html)


class UnconfiguredRendersNothing(TestCase):
    """No SocialApp / blank config → the tag is falsy and the block draws no
    button (the surface vanishes when SSO isn't wired up)."""

    def test_no_socialapp_tag_is_empty(self):
        # Enabled but never configured: ensure no SocialApp lingers.
        services.sync_social_app({})
        app_registry._active.add('staff_sso')
        self.assertEqual(_render_tag(_request()), '')

    def test_no_socialapp_block_is_empty(self):
        services.sync_social_app({})
        app_registry._active.add('staff_sso')
        html = _render_block(_request()).strip()
        self.assertNotIn('Sign in with SSO', html)
        self.assertEqual(html, '')


class DisabledRendersNothing(TestCase):
    """Plugin disabled → even with a SocialApp present, no button renders."""

    def test_disabled_plugin_tag_is_empty(self):
        # Configure a SocialApp, then mark the plugin inactive.
        _configure(domains='acme.com', enabled=True)
        app_registry._active.discard('staff_sso')
        self.assertEqual(_render_tag(_request()), '')

    def test_disabled_plugin_block_is_empty(self):
        _configure(domains='acme.com', enabled=True)
        app_registry._active.discard('staff_sso')
        html = _render_block(_request()).strip()
        self.assertEqual(html, '')


# ── SAML (Phase 4b) login-button surface ─────────────────────────────────────
def _configure_saml(*, enabled=True, saml_enabled=True):
    """Write config with the SAML section populated + sync the SAML SocialApp +
    drive registry state, matching how ready() wires the SAML provider in prod."""
    from plugins.models import PluginConfig

    PluginConfig.objects.update_or_create(
        plugin_name='staff_sso',
        defaults={
            'is_enabled': enabled,
            'config': {
                'allowed_domains': 'acme.com',
                'saml_enabled': saml_enabled,
                'saml_org_slug': 'staff_sso_saml',
                'saml_idp_entity_id': 'https://idp.example/entity',
                'saml_idp_sso_url': 'https://idp.example/sso',
                'saml_idp_x509cert': 'MIICert==',
            },
        },
    )
    plugin = app_registry.get('staff_sso')
    if plugin is not None:
        plugin.invalidate_config_cache()
    services.sync_saml_app(services.get_saml_settings(plugin) if plugin else {})

    if enabled:
        app_registry._active.add('staff_sso')
    else:
        app_registry._active.discard('staff_sso')
    return plugin


def _render_saml_tag(request):
    tmpl = Template('{% load staff_sso %}{% staff_sso_saml_login_url as u %}{{ u }}')
    return tmpl.render(Context({'request': request})).strip()


class SamlButtonRenders(TestCase):
    """SAML enabled + configured → the SAML tag returns a URL and the block
    renders the 'Sign in with SSO (SAML)' link."""

    def setUp(self):
        _configure_saml(enabled=True, saml_enabled=True)

    def test_saml_tag_returns_login_url(self):
        url = _render_saml_tag(_request())
        self.assertTrue(url, 'expected a non-empty SAML provider login URL')
        # allauth reverses saml_login off the org slug.
        self.assertIn('staff_sso_saml', url)
        self.assertIn('/saml/', url)

    def test_block_renders_saml_link(self):
        html = _render_block(_request())
        self.assertIn('Sign in with SSO (SAML)', html)
        self.assertIn('process=login', html)


class SamlButtonDisableSafe(TestCase):
    """(4) disable-safe — SAML disabled / plugin disabled → no SAML SocialApp,
    no SAML button."""

    def test_saml_disabled_no_app_no_button(self):
        from allauth.socialaccount.models import SocialApp

        _configure_saml(enabled=True, saml_enabled=False)
        # SAML turned off → no SAML SocialApp synced.
        self.assertFalse(SocialApp.objects.filter(provider_id=services.SAML_PROVIDER_ID).exists())
        self.assertEqual(_render_saml_tag(_request()), '')
        self.assertNotIn('SAML', _render_block(_request()))

    def test_plugin_disabled_no_saml_button(self):
        _configure_saml(enabled=True, saml_enabled=True)
        app_registry._active.discard('staff_sso')
        self.assertEqual(_render_saml_tag(_request()), '')
        self.assertEqual(_render_block(_request()).strip(), '')
