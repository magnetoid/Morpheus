"""staff_sso template tags — the config-gated SSO login URL.

A StorefrontBlock template can't read plugin config, so the gating lives here:
``{% staff_sso_login_url as sso_url %}`` returns allauth's real provider login
URL **only** when the plugin is enabled AND an OIDC IdP is configured (a
SocialApp row exists for our provider). Otherwise it returns ``''`` and the
block renders no button — so the surface vanishes the moment SSO is unconfigured
or the plugin is disabled.

The URL is computed through allauth's adapter (the same path its stock
``{% provider_login_url %}`` tag uses): ``get_provider(request, PROVIDER_ID)``
resolves the openid_connect subprovider by ``provider_id``, then
``provider.get_login_url(request)`` builds the callback-initiating URL — never a
hardcoded path.
"""

# ruff: noqa: PLC0415 — inline imports keep this templatetag module importable
# at settings-load time without pulling allauth/registry into the import graph.
from __future__ import annotations

import logging

from django import template

register = template.Library()

logger = logging.getLogger('morpheus.staff_sso')


def _is_configured() -> bool:
    """True iff an OIDC SocialApp for our provider exists with a client_id —
    i.e. the merchant has wired up an IdP. Mirrors services.is_configured but
    reads the synced SocialApp (the live source of truth allauth logs in with)."""
    try:
        from allauth.socialaccount.models import SocialApp

        from plugins.installed.staff_sso import services

        return (
            SocialApp.objects.filter(
                provider=services.PROVIDER,
                provider_id=services.PROVIDER_ID,
            )
            .exclude(client_id='')
            .exists()
        )
    except Exception:  # noqa: BLE001 — fail closed: no button if we can't tell
        return False


def _plugin_active() -> bool:
    """Enabled-gate shared by both protocol tags."""
    try:
        from plugins.registry import plugin_registry

        return bool(plugin_registry.is_active('staff_sso'))
    except ImportError:
        return False


def _saml_app():
    """Return the synced SAML SocialApp (or None) — the live source of truth the
    SAML login URL is built from. Keyed by provider='saml' + a non-blank
    client_id (the org slug allauth reverses its callback URL off)."""
    try:
        from allauth.socialaccount.models import SocialApp

        from plugins.installed.staff_sso import services

        return (
            SocialApp.objects.filter(
                provider=services.SAML_PROVIDER,
                provider_id=services.SAML_PROVIDER_ID,
            )
            .exclude(client_id='')
            .first()
        )
    except Exception:  # noqa: BLE001 — fail closed: no button if we can't tell
        return None


@register.simple_tag(takes_context=True)
def staff_sso_login_url(context) -> str:
    """Return the allauth OIDC provider login URL, or '' when off/unconfigured.

    Gated on: plugin enabled (registry) AND a configured SocialApp. Resolves the
    URL via allauth's adapter so the openid_connect callback path is owned by
    allauth, not hardcoded here.
    """
    if not _plugin_active():
        return ''

    # Configured-gate: a SocialApp with a client_id exists.
    if not _is_configured():
        return ''

    request = context.get('request')
    try:
        from allauth.socialaccount.adapter import get_adapter

        from plugins.installed.staff_sso import services

        provider = get_adapter().get_provider(request, services.PROVIDER_ID)
        return provider.get_login_url(request) or ''
    except Exception as exc:  # noqa: BLE001 — never break the login page on a bad provider
        logger.warning('staff_sso: could not resolve provider login URL: %s', exc)
        return ''


@register.simple_tag(takes_context=True)
def staff_sso_saml_login_url(context) -> str:
    """Return the allauth SAML provider login URL, or '' when off/unconfigured.

    Gated on: plugin enabled (registry) AND a synced SAML SocialApp. Resolves the
    URL via allauth's adapter (``get_provider(request, 'saml', client_id=<slug>)``
    → ``provider.get_login_url(request)``, which reverses ``saml_login`` off the
    org slug) — the callback path is owned by allauth, never hardcoded.
    """
    if not _plugin_active():
        return ''

    app = _saml_app()
    if app is None:
        return ''

    request = context.get('request')
    try:
        from allauth.socialaccount.adapter import get_adapter

        from plugins.installed.staff_sso import services

        provider = get_adapter().get_provider(
            request, services.SAML_PROVIDER, client_id=app.client_id
        )
        return provider.get_login_url(request) or ''
    except Exception as exc:  # noqa: BLE001 — never break the login page on a bad provider
        logger.warning('staff_sso: could not resolve SAML provider login URL: %s', exc)
        return ''
