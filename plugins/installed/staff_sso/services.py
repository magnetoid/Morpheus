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

# SAML (Phase 4b). allauth's saml provider has a fixed provider id of "saml"
# (SAMLProvider.id), and it reverses its login URL off SocialApp.client_id as the
# `organization_slug` — so for SAML we store the org slug in `client_id`, not in
# `provider_id`. A SocialLogin built by the SAML ACS view therefore carries
# account.provider == "saml" (the provider id), which is what the adapter gates on.
SAML_PROVIDER = 'saml'
SAML_PROVIDER_ID = 'saml'
SAML_APP_NAME = 'Staff SSO (SAML)'
DEFAULT_SAML_ORG_SLUG = 'staff_sso_saml'

# The set of allauth provider ids the StaffSsoAdapter owns. The adapter is a
# process-wide SOCIALACCOUNT_ADAPTER, so it must run its gate/JIT/MFA logic ONLY
# for these; any other (future, customer-facing) social provider passes through
# to allauth's default untouched. OIDC logins carry the subprovider's
# provider_id ("staff_sso"); SAML logins carry the SAML provider id ("saml").
OUR_PROVIDERS = frozenset({PROVIDER_ID, SAML_PROVIDER_ID})


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


# ── SAML config (Phase 4b) ───────────────────────────────────────────────────
def get_saml_settings(plugin) -> dict:
    """Read the saved SAML IdP config off the plugin's PluginConfig row.

    Shares the staff-gate fields (``allowed_domains`` / ``staff_groups``) with
    OIDC — the gate is protocol-agnostic — and adds the SAML-specific IdP
    descriptors plus the attribute-mapping names the IdP uses in its assertion.
    """

    def _get(key, default=''):
        return (plugin.get_config_value(key, default) or '').strip()

    return {
        'enabled': bool(plugin.get_config_value('saml_enabled', False)),
        'org_slug': _get('saml_org_slug', DEFAULT_SAML_ORG_SLUG) or DEFAULT_SAML_ORG_SLUG,
        'idp_metadata_url': _get('saml_idp_metadata_url'),
        'idp_entity_id': _get('saml_idp_entity_id'),
        'idp_sso_url': _get('saml_idp_sso_url'),
        'idp_x509cert': _get('saml_idp_x509cert'),
        'email_attr': _get('saml_email_attr'),
        'first_name_attr': _get('saml_first_name_attr'),
        'last_name_attr': _get('saml_last_name_attr'),
        'groups_attr': _get('saml_groups_attr'),
        'allowed_domains': _csv_list(plugin.get_config_value('allowed_domains', [])),
        'staff_groups': _csv_list(plugin.get_config_value('staff_groups', [])),
    }


def is_saml_configured(cfg: dict) -> bool:
    """A SAML IdP is usable when SAML is enabled AND the IdP is described either
    by a metadata URL OR by the (entity_id + sso_url + x509cert) triple. Blank
    config → no SAML SocialApp → the SAML path is inert (email-OTP unaffected)."""
    if not cfg.get('enabled'):
        return False
    if cfg.get('idp_metadata_url'):
        return True
    return bool(cfg.get('idp_entity_id') and cfg.get('idp_sso_url') and cfg.get('idp_x509cert'))


def build_saml_app_settings(cfg: dict) -> dict:
    """Translate our flat config into the nested dict allauth's saml provider
    expects in ``SocialApp.settings`` (read by ``build_saml_config`` /
    ``SAMLProvider._extract``).

    - ``idp``: either ``{metadata_url, entity_id}`` (allauth fetches+parses it)
      or the explicit ``{entity_id, x509cert, sso_url}`` triple.
    - ``attribute_mapping``: allauth's ``_extract`` does
      ``provider_config.get("attribute_mapping", default)`` — passing ANY mapping
      *replaces* the whole default (dropping the built-in ``email``/``uid``/… maps
      and 403-ing logins that only set one attr). So we SEED from
      ``SAMLProvider.default_attribute_mapping`` and OVERLAY only the keys the
      merchant configured (``email``/``first_name``/``last_name``); every unset
      key keeps allauth's default. Groups are NOT mapped here — the adapter reads
      SAML groups from the raw ``extra_data`` by the ``saml_groups_attr`` NAME
      (``_resolve_groups``), so a ``groups`` key here is useless and is exactly
      what would trigger the default-replacement.
    - ``advanced.want_assertion_signed``: allauth defaults
      ``security.wantAssertionsSigned`` to ``False``; we require signed assertions
      for the staff boundary (closes XML-Signature-Wrapping). Okta/Entra/Google
      sign assertions by default, so this is low-friction.
    """
    from allauth.socialaccount.providers.saml.provider import SAMLProvider

    if cfg.get('idp_metadata_url'):
        idp: dict = {'metadata_url': cfg['idp_metadata_url']}
        if cfg.get('idp_entity_id'):
            idp['entity_id'] = cfg['idp_entity_id']
    else:
        idp = {
            'entity_id': cfg['idp_entity_id'],
            'sso_url': cfg['idp_sso_url'],
            'x509cert': cfg['idp_x509cert'],
        }

    attribute_mapping: dict = dict(SAMLProvider.default_attribute_mapping)
    if cfg.get('email_attr'):
        attribute_mapping['email'] = cfg['email_attr']
    if cfg.get('first_name_attr'):
        attribute_mapping['first_name'] = cfg['first_name_attr']
    if cfg.get('last_name_attr'):
        attribute_mapping['last_name'] = cfg['last_name_attr']

    return {
        'idp': idp,
        'attribute_mapping': attribute_mapping,
        'advanced': {'want_assertion_signed': True},
    }


def sync_saml_app(cfg: dict) -> None:
    """Create/update the single SAML SocialApp from saved config, or remove it
    when SAML is disabled/blank. Idempotent; safe on every boot.

    allauth keys SAML apps by ``client_id == organization_slug`` (it reverses
    the login URL off it), so the org slug lives in ``client_id`` and the row is
    identified by ``provider='saml'`` + that slug."""
    from allauth.socialaccount.models import SocialApp

    if not is_saml_configured(cfg):
        SocialApp.objects.filter(provider=SAML_PROVIDER, provider_id=SAML_PROVIDER_ID).delete()
        return

    org_slug = cfg['org_slug']
    app, _created = SocialApp.objects.get_or_create(
        provider=SAML_PROVIDER,
        provider_id=SAML_PROVIDER_ID,
        defaults={'name': SAML_APP_NAME},
    )
    app.name = SAML_APP_NAME
    # The org slug is the SAML callback-URL segment; allauth resolves the app by
    # client_id == organization_slug. No OAuth client secret for SAML.
    app.client_id = org_slug
    app.secret = ''
    app.settings = build_saml_app_settings(cfg)
    app.save()

    from django.conf import settings as dj_settings

    try:
        app.sites.add(dj_settings.SITE_ID)
    except Exception as exc:  # noqa: BLE001 — site binding is best-effort
        logger.warning('staff_sso: could not bind SAML SocialApp to site: %s', exc)


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
