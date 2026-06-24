"""Staff SSO service layer — config parsing, staff-gating, provider sync, audit.

Kept thin and importable without Django side effects so the adapter and the
unit tests share one decision point. The OIDC protocol itself is owned by
allauth's ``openid_connect`` provider; this module only configures it from the
dashboard settings panel and decides *who* may sign in (the staff gate).
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.staff_sso')

# The slug under which this build registers its single OIDC SocialApp. One IdP
# config to start (the spec's non-goal: per-tenant multi-IdP); the row is keyed
# by this stable provider_id so re-saving config updates rather than duplicates.
PROVIDER = 'openid_connect'
PROVIDER_ID = 'staff_sso'
APP_NAME = 'Staff SSO'


# ── Config parsing ───────────────────────────────────────────────────────────
def _csv_list(value) -> list[str]:
    """Normalise a CSV string OR a list into a lowercased, de-blanked list."""
    if isinstance(value, str):
        parts = value.replace('\n', ',').split(',')
    elif isinstance(value, list | tuple):
        parts = list(value)
    else:
        return []
    return [str(p).strip().lower() for p in parts if str(p).strip()]


def get_settings(plugin) -> dict:
    """Read the saved IdP config off the plugin's PluginConfig row."""
    return {
        'issuer': (plugin.get_config_value('oidc_issuer', '') or '').strip(),
        'client_id': (plugin.get_config_value('oidc_client_id', '') or '').strip(),
        'client_secret': (plugin.get_config_value('oidc_client_secret', '') or '').strip(),
        'scopes': (plugin.get_config_value('oidc_scopes', 'openid email profile') or '').strip(),
        'allowed_domains': _csv_list(plugin.get_config_value('allowed_domains', [])),
        'staff_groups': _csv_list(plugin.get_config_value('staff_groups', [])),
    }


def is_configured(cfg: dict) -> bool:
    """An IdP is usable only when issuer + client id + secret are all present.
    Blank config → no provider registered → SSO inert (email-OTP unaffected)."""
    return bool(cfg.get('issuer') and cfg.get('client_id') and cfg.get('client_secret'))


# ── Staff gate ───────────────────────────────────────────────────────────────
def gate_decision(cfg: dict, *, email: str, groups: list[str]) -> bool:
    """Return True iff this identity may sign in as staff.

    Pass if the email domain is in ``allowed_domains`` OR an IdP group claim
    intersects ``staff_groups``. With neither list configured, nobody passes
    (fail-closed — a misconfigured panel must not admit the whole internet).
    """
    domains = cfg.get('allowed_domains') or []
    staff_groups = cfg.get('staff_groups') or []
    if not domains and not staff_groups:
        return False

    domain = (email or '').partition('@')[2].lower()
    if domain and domain in domains:
        return True

    claimed = {g.strip().lower() for g in (groups or []) if str(g).strip()}
    return bool(staff_groups and claimed.intersection(staff_groups))


def claim_groups(data) -> list[str]:
    """Pull a groups/roles claim out of the IdP assertion (best-effort)."""
    if not isinstance(data, dict):
        return []
    for key in ('groups', 'roles', 'group', 'role'):
        val = data.get(key)
        if isinstance(val, str):
            return [val]
        if isinstance(val, list | tuple):
            return [str(v) for v in val]
    return []


# ── Provider (allauth SocialApp) sync ────────────────────────────────────────
def sync_social_app(cfg: dict) -> None:
    """Create/update the single OIDC SocialApp from saved config, or remove it
    when config is blank. Idempotent and safe to call on every boot."""
    from allauth.socialaccount.models import SocialApp

    if not is_configured(cfg):
        # Blank/incomplete config → no provider button → login = email-OTP.
        SocialApp.objects.filter(provider=PROVIDER, provider_id=PROVIDER_ID).delete()
        return

    app, _created = SocialApp.objects.get_or_create(
        provider=PROVIDER,
        provider_id=PROVIDER_ID,
        defaults={'name': APP_NAME},
    )
    app.name = APP_NAME
    app.client_id = cfg['client_id']
    app.secret = cfg['client_secret']
    app.settings = {
        **(app.settings or {}),
        'server_url': cfg['issuer'],
        'oauth_pkce_enabled': True,
    }
    scopes = [s for s in cfg.get('scopes', '').split() if s]
    if scopes:
        app.settings['scope'] = scopes
    app.save()

    # SocialApp is multi-site (django.contrib.sites). Bind to the current site
    # so allauth's on_site() lookup finds it during login.
    from django.conf import settings as dj_settings

    try:
        app.sites.add(dj_settings.SITE_ID)
    except Exception as exc:  # noqa: BLE001 — site binding is best-effort
        logger.warning('staff_sso: could not bind SocialApp to site: %s', exc)


# ── Audit ────────────────────────────────────────────────────────────────────
def audit(event_type: str, *, actor=None, target: str = '', metadata=None, severity='info') -> None:
    """Record an sso.* audit event. Never raises (core.audit swallows DB errors)."""
    from core.audit.services import record

    record(
        event_type=event_type,
        actor=actor,
        target=target or '',
        metadata=metadata or {},
        severity=severity,
    )
