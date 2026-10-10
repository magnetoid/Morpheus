"""Token management UI for the MCP admin server.

Lives at /dashboard/apps/agent_mcp/tokens/ (registered as a
DashboardPage with nav='settings' so it surfaces under Settings →
Developer). Lets a merchant create a token for a purpose (a preset, never an
implicit wildcard), hand another party its connection details
(``connection.py``), replace its secret, set its permissions, and revoke it.
Who created a token is recorded on it, and every change writes an audit row.

Storage shape lives on ``PluginConfig['agent_mcp']['public_keys']`` —
a list whose entries are either:

* a raw string (legacy / hand-written), or
* a dict ``{token, label, created_at, last_used_at}``

The reader in ``views._api_keys`` accepts both shapes. The UI here
always writes dicts.

Security:
  - Staff-only (`@staff_member_required`).
  - Full token shown ONCE on creation. Subsequent renders mask all but
    the last 4 characters — so leaving the page open is not a leak.
  - Tokens are 32 random bytes → urlsafe-base64; the prefix `mph_` lets
    you spot a Morpheus token at a glance in logs.
  - Each form POST validates the CSRF token via the standard Django
    middleware (csrf_protect implicit on staff_member_required forms).
"""

from __future__ import annotations

import datetime as _dt
import logging
import secrets
import uuid

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from core.authz import require_capability

logger = logging.getLogger('morpheus.agent_mcp.dashboard')

_TOKEN_PREFIX = 'mph_'
_TOKEN_BYTES = 32


def _approval_tools() -> list[dict]:
    """Every protected tool a token can be granted: the admin server's own tools
    and the store tools Janus can call for an external agent (janus_door.py).

    It read the legacy curated read list until v0.96.0, which has no protected
    tool, so the checklist was always empty and every save wiped the grants."""
    from core.agents import agent_registry
    from core.assistant.tools import get_default_tools

    seen: dict[str, dict] = {}
    for tool in [*get_default_tools(), *agent_registry.platform_tools()]:
        if getattr(tool, 'requires_approval', False):
            seen.setdefault(
                tool.name, {'name': tool.name, 'description': getattr(tool, 'description', '')}
            )
    return sorted(seen.values(), key=lambda d: d['name'])


def _approval_tool_names() -> list[str]:
    return [t['name'] for t in _approval_tools()]


def _load_entries() -> list[dict]:
    """Return the stored entries, PRESERVING every stored key.

    CRITICAL: these entries are round-tripped back through ``_save_entries``
    by every mutating action, so any key dropped here is ERASED from storage.
    Dropping ``mcp_scopes`` / ``graphql_scopes`` / ``approved_tools`` is not
    cosmetic: ``token_scopes`` reads a *missing* ``mcp_scopes`` key as the
    wildcard, so a normalisation that omitted it silently promoted every
    previously-scoped token to full access on the next create/revoke, and
    wiped every per-token approval grant. Keep the whole dict; only fill in
    the display fields the template needs.
    """
    from plugins.models import PluginConfig

    cfg = PluginConfig.objects.filter(plugin_name='agent_mcp').first()
    entries = []
    raw = (cfg.config if cfg else {}) or {}
    for k in raw.get('public_keys') or []:
        if isinstance(k, dict):
            entry = dict(k)  # preserve scopes/approved_tools/rate_limit/etc.
            entry['id'] = str(k.get('id') or '')
            entry['label'] = str(k.get('label') or '')
            entry['token'] = str(k.get('token') or '')
            entry['created_at'] = str(k.get('created_at') or '')
            entry['last_used_at'] = str(k.get('last_used_at') or '')
            entries.append(entry)
        else:
            # Legacy raw-string entry — no metadata to preserve.
            entries.append(
                {
                    'id': '',
                    'label': '(legacy)',
                    'token': str(k or ''),
                    'created_at': '',
                    'last_used_at': '',
                }
            )
    return entries


def _save_entries(entries: list[dict]) -> None:
    from plugins.models import PluginConfig

    cfg, _ = PluginConfig.objects.get_or_create(plugin_name='agent_mcp')
    config = dict(cfg.config or {})
    config['public_keys'] = entries
    cfg.config = config
    cfg.save(update_fields=['config', 'updated_at'])


def _mask(token: str) -> str:
    if not token:
        return ''
    if len(token) <= 8:
        return '••••'
    return f'{token[:4]}…{token[-4:]}'


def _new_token() -> str:
    """Generate a 32-byte urlsafe token with a recognisable prefix."""
    return _TOKEN_PREFIX + secrets.token_urlsafe(_TOKEN_BYTES)


def _find_entry(entries: list[dict], token_id: str) -> dict | None:
    for e in entries:
        if isinstance(e, dict) and e.get('id') == token_id:
            return e
    return None


def _scope_list_from_form(post, prefix: str) -> list[str]:
    """Read checked scope names matching `{prefix}_<scope>` from a
    POST. Used by the permissions form which puts MCP + GraphQL
    scopes on the same submit."""
    from plugins.installed.agent_mcp.scopes import AVAILABLE_SCOPES

    out: list[str] = []
    for scope in AVAILABLE_SCOPES:
        if post.get(f'{prefix}_{scope}') == 'on':
            out.append(scope)
    return out


# What a new token is for. A token is never created as an implicit wildcard
# again: before v0.96.0 a new entry had no scope keys, which every surface reads
# as full access.
PRESETS: dict[str, tuple[str, str]] = {
    'janus_read': (
        'Janus: ask and read',
        'Ask Janus anything. Janus and the token itself can read the store; nothing changes.',
    ),
    'janus_write': (
        'Janus: ask, read and change',
        'Ask Janus to look things up and make everyday changes. Protected changes '
        '(prices, refunds, roles) still need ticking on the token.',
    ),
    'read': ('Read only', 'Read the store over MCP and GraphQL. No Janus, no changes.'),
    'full': (
        'Full access',
        'Everything, Janus included. Protected changes still need ticking on the token.',
    ),
    'custom': ('Custom', 'Nothing until you set its permissions.'),
}
# Granted by hand only: sensitive, destructive or payment-adjacent.
_HAND_ONLY = frozenset({'diagnostics.read', 'system.write', 'catalog.delete', 'acp.checkout'})
# A shopper's own cart and wishlist, not the store's work.
_SHOPPER_SCOPES = ('cart.', 'wishlist.')


def preset_scopes(preset: str) -> list[str]:
    from plugins.installed.agent_mcp.janus_door import SCOPE as JANUS
    from plugins.installed.agent_mcp.scopes import AVAILABLE_SCOPES, WILDCARD

    usable = [s for s in AVAILABLE_SCOPES if s not in _HAND_ONLY and s != JANUS]
    reads = [s for s in usable if s.endswith('.read')]
    writes = [
        s
        for s in usable
        if s.rsplit('.', 1)[-1] in ('write', 'cancel') and not s.startswith(_SHOPPER_SCOPES)
    ]
    chosen = {
        'janus_read': [JANUS, *reads],
        'janus_write': [JANUS, *reads, *writes],
        'read': reads,
        'full': [WILDCARD, JANUS],
    }
    return list(chosen.get(preset, []))


def _surface_scopes(post, prefix: str) -> list[str]:
    """The scopes a permissions form sets on one surface. "Talk to Janus" is kept
    next to the wildcard: the wildcard does not confer it (janus_door.py)."""
    from plugins.installed.agent_mcp.janus_door import SCOPE as JANUS
    from plugins.installed.agent_mcp.scopes import WILDCARD

    if post.get(f'{prefix}_wildcard') == 'on':
        return [WILDCARD] + ([JANUS] if post.get(f'{prefix}_{JANUS}') == 'on' else [])
    return _scope_list_from_form(post, prefix)


def _audit(request, event_type: str, entry: dict, **extra) -> None:
    """One audit row per token change. Never the secret."""
    try:
        from core.audit.services import record

        record(
            event_type=event_type,
            actor=request.user,
            target=f'mcp_token/{entry.get("id") or "legacy"}',
            metadata={'label': str(entry.get('label') or ''), **extra},
        )
    except Exception:  # noqa: BLE001 — an audit failure never blocks the merchant
        logger.warning('agent_mcp: token audit row not written', exc_info=True)


def _kit(request, entry: dict, *, secret: str = '') -> dict:
    from core.utils.site import store_name
    from plugins.installed.agent_mcp.connection import connection_kit

    return connection_kit(
        base_url=request.build_absolute_uri('/'),
        store_name=store_name(),
        entry=entry,
        secret=secret,
    )


def _now() -> str:
    return _dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z'


def _create(request) -> tuple[dict, str]:
    label = (request.POST.get('label') or '').strip()[:120] or 'Untitled token'
    preset = (request.POST.get('preset') or 'custom').strip()
    if preset not in PRESETS:
        preset = 'custom'
    scopes = preset_scopes(preset)
    entries = _load_entries()
    entry = {
        'id': str(uuid.uuid4()),
        'label': label,
        'token': _new_token(),
        'created_at': _now(),
        'last_used_at': '',
        'mcp_scopes': list(scopes),
        'graphql_scopes': list(scopes),
        'approved_tools': [],
        'preset': preset,
        'created_by': {
            'id': str(request.user.pk),  # a UUID: JSON stores it as text
            'email': str(getattr(request.user, 'email', '') or ''),
        },
    }
    entries.append(entry)
    _save_entries(entries)
    _audit(request, 'mcp.token_created', entry, preset=preset)
    messages.success(
        request, 'Token created. Copy its connection details now: the secret is shown only once.'
    )
    return entry, preset


def _rotate(request) -> dict | None:
    entries = _load_entries()
    entry = _find_entry(entries, (request.POST.get('id') or '').strip())
    if entry is None:
        messages.error(request, 'Token not found.')
        return None
    entry['token'] = _new_token()
    entry['rotated_at'] = _now()
    _save_entries(entries)
    _audit(request, 'mcp.token_rotated', entry)
    messages.success(
        request, 'New secret made. The old one stopped working; copy the new details now.'
    )
    return entry


def _revoke(request) -> None:
    target_id = (request.POST.get('id') or '').strip()
    target_token = (request.POST.get('token') or '').strip()
    entries = _load_entries()
    kept = [
        e
        for e in entries
        if (target_id and e.get('id') != target_id)
        or (not target_id and e.get('token') != target_token)
    ]
    if len(kept) == len(entries):
        messages.error(request, 'Token not found.')
        return
    gone = next(e for e in entries if e not in kept)
    _save_entries(kept)
    _audit(request, 'mcp.token_revoked', gone)
    messages.success(request, 'Token revoked.')


def _save_scopes(request) -> None:
    entries = _load_entries()
    entry = _find_entry(entries, (request.POST.get('id') or '').strip())
    if entry is None:
        messages.error(request, 'Token not found.')
        return
    entry['mcp_scopes'] = _surface_scopes(request.POST, 'mcp')
    entry['graphql_scopes'] = _surface_scopes(request.POST, 'graphql')
    # Approved protected tools: the per-token grant for requires_approval writes.
    # A grant for a tool the form does not list (an app that is off, a hand-added
    # name) is kept; a listed one follows its box.
    shown = _approval_tool_names()
    hidden = [t for t in entry.get('approved_tools') or [] if t not in set(shown)]
    entry['approved_tools'] = hidden + [
        t for t in shown if request.POST.get(f'approve_{t}') == 'on'
    ]
    _save_entries(entries)
    _audit(
        request,
        'mcp.token_permissions',
        entry,
        mcp_scopes=entry['mcp_scopes'],
        graphql_scopes=entry['graphql_scopes'],
        approved_tools=entry['approved_tools'],
    )
    messages.success(request, f'Permissions updated for {entry.get("label") or "(unlabelled)"}.')


def _row(entry) -> dict:
    from plugins.installed.agent_mcp.janus_door import janus_granted

    mcp = list(entry.get('mcp_scopes')) if entry.get('mcp_scopes') is not None else None
    gql = list(entry.get('graphql_scopes')) if entry.get('graphql_scopes') is not None else None
    return {
        'id': entry.get('id'),
        'label': entry.get('label') or '(unlabelled)',
        'token_masked': _mask(entry.get('token', '')),
        'token_full': entry.get('token', ''),
        'created_at': _readable_time(entry.get('created_at')),
        'created_by': (entry.get('created_by') or {}).get('email', ''),
        'last_used_at': entry.get('last_used_at'),
        'is_legacy': not entry.get('id'),
        'mcp_scopes': mcp,  # None → wildcard inherited
        'graphql_scopes': gql,
        'mcp_summary': _scope_summary(mcp),
        'graphql_summary': _scope_summary(gql),
        'janus': janus_granted(entry, 'mcp') or janus_granted(entry, 'graphql'),
    }


def _readable_time(value) -> str:
    """``2026-10-10T21:45:18Z`` as ``2026-10-10 21:45 UTC``; anything else as stored."""
    text = str(value or '')
    if len(text) >= 16 and text[10] == 'T':
        return f'{text[:10]} {text[11:16]} UTC'
    return text


def _edit_context(entry) -> dict | None:
    if entry is None:
        return None
    mcp = entry.get('mcp_scopes')
    gql = entry.get('graphql_scopes')
    return {
        'id': entry.get('id'),
        'label': entry.get('label') or '(unlabelled)',
        'mcp_wildcard': mcp is None or '*' in (mcp or []),
        'graphql_wildcard': gql is None or '*' in (gql or []),
        'mcp_active': set(mcp or []),
        'graphql_active': set(gql or []),
        'approval_catalog': _approval_tools(),
        'approved_active': set(entry.get('approved_tools') or []),
    }


@staff_member_required
@require_capability('system.write')
@require_http_methods(['GET', 'POST'])
def tokens_view(request):
    """Create, connect, rotate, set permissions on and revoke API tokens."""
    kit: dict | None = None
    kit_label = ''
    edit_id = (request.GET.get('edit') or '').strip()

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'create':
            entry, preset = _create(request)
            kit, kit_label = _kit(request, entry, secret=entry['token']), entry['label']
            if preset == 'custom':
                edit_id = entry['id']
        elif action == 'rotate':
            entry = _rotate(request)
            if entry is not None:
                kit, kit_label = _kit(request, entry, secret=entry['token']), entry.get('label')
        elif action == 'revoke':
            _revoke(request)
        elif action == 'save_scopes':
            _save_scopes(request)
        else:
            messages.error(request, f'Unknown action {action!r}.')
        # The secret is shown once, on this response; otherwise POST/redirect/GET.
        if kit is None:
            return redirect(request.path)

    entries = _load_entries()
    connect_id = (request.GET.get('connect') or '').strip()
    if kit is None and connect_id:
        connect_entry = _find_entry(entries, connect_id)
        if connect_entry is not None:
            kit, kit_label = _kit(request, connect_entry), connect_entry.get('label')

    from plugins.installed.agent_mcp.scopes import AVAILABLE_SCOPES

    base = request.build_absolute_uri('/').rstrip('/')
    return render(
        request,
        'agent_mcp/tokens.html',
        {
            'rows': [_row(e) for e in entries],
            'kit': kit,
            'kit_label': kit_label,
            'presets': [
                {'id': key, 'label': label, 'description': desc}
                for key, (label, desc) in PRESETS.items()
            ],
            'admin_rpc_url': f'{base}/mcp/admin/v1/',
            'graphql_url': f'{base}/graphql/',
            'scope_catalog': [
                {'id': sid, 'label': label, 'description': desc}
                for sid, (label, desc) in AVAILABLE_SCOPES.items()
            ],
            'edit': _edit_context(_find_entry(entries, edit_id) if edit_id else None),
            'active_nav': 'apps',
        },
    )


def _scope_summary(scopes: list[str] | None) -> str:
    """Human-friendly label for a scope set, used in the table column."""
    if scopes is None:
        return 'inherits ★ full access'
    if not scopes:
        return 'no access'
    if '*' in scopes:
        return '★ full access'
    return f'{len(scopes)} scope(s)'
