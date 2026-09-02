"""Token management UI for the MCP admin server.

Lives at /dashboard/apps/agent_mcp/tokens/ (registered as a
DashboardPage with nav='settings' so it surfaces under Settings →
Developer). Lets a merchant generate, label, copy, and revoke Bearer
tokens used by external agents calling /mcp/admin/v1/.

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
    """The MCP-exposed tools flagged ``requires_approval=True`` — the protected
    writes a merchant grants per token (enterprise Phase 1 governance)."""
    from plugins.installed.agent_mcp.views import _public_tools

    out = []
    for t in _public_tools():
        if getattr(t, 'requires_approval', False):
            out.append({'name': t.name, 'description': getattr(t, 'description', '')})
    return sorted(out, key=lambda d: d['name'])


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


@staff_member_required
@require_capability('system.write')
@require_http_methods(['GET', 'POST'])
def tokens_view(request):  # noqa: PLR0912, PLR0915
    """List + create + revoke MCP admin tokens."""
    just_created_token = ''
    just_created_label = ''

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'create':
            label = (request.POST.get('label') or '').strip()[:120] or 'Untitled token'
            entries = _load_entries()
            new_entry = {
                'id': str(uuid.uuid4()),
                'label': label,
                'token': _new_token(),
                'created_at': _dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z',
                'last_used_at': '',
            }
            entries.append(new_entry)
            _save_entries(entries)
            just_created_token = new_entry['token']
            just_created_label = label
            messages.success(
                request,
                'Token created — copy it now. You will not see it again.',
            )
        elif action == 'revoke':
            target_id = (request.POST.get('id') or '').strip()
            target_token = (request.POST.get('token') or '').strip()
            entries = _load_entries()
            kept = [
                e
                for e in entries
                if (target_id and e.get('id') != target_id)
                or (not target_id and e.get('token') != target_token)
            ]
            if len(kept) != len(entries):
                _save_entries(kept)
                messages.success(request, 'Token revoked.')
            else:
                messages.error(request, 'Token not found.')
        elif action == 'save_scopes':
            target_id = (request.POST.get('id') or '').strip()
            entries = _load_entries()
            entry = _find_entry(entries, target_id)
            if entry is None:
                messages.error(request, 'Token not found.')
            else:
                # Wildcard checkbox is a quick "full access on this surface"
                # shortcut. When checked, store ['*']; otherwise store the
                # explicit scope list.
                if request.POST.get('mcp_wildcard') == 'on':
                    entry['mcp_scopes'] = ['*']
                else:
                    entry['mcp_scopes'] = _scope_list_from_form(request.POST, 'mcp')
                if request.POST.get('graphql_wildcard') == 'on':
                    entry['graphql_scopes'] = ['*']
                else:
                    entry['graphql_scopes'] = _scope_list_from_form(request.POST, 'graphql')
                # Approved tools — the per-token grant for requires_approval
                # writes. A checked box means "this token may execute this
                # protected tool over MCP" (enterprise Phase 1 governance).
                entry['approved_tools'] = [
                    t for t in _approval_tool_names() if request.POST.get(f'approve_{t}') == 'on'
                ]
                _save_entries(entries)
                messages.success(
                    request, f'Permissions updated for {entry.get("label") or "(unlabelled)"}.'
                )
            return redirect(request.path)
        else:
            messages.error(request, f'Unknown action {action!r}.')
        # POST/redirect/GET keeps the URL clean — but we want to render
        # the freshly created token ONCE before redirecting. Render
        # inline this time; the page will reload normally on its own.
        if not just_created_token:
            return redirect(request.path)

    entries = _load_entries()
    rows = []
    for e in entries:
        mcp_scopes = list(e.get('mcp_scopes')) if e.get('mcp_scopes') is not None else None
        gql_scopes = list(e.get('graphql_scopes')) if e.get('graphql_scopes') is not None else None
        rows.append(
            {
                'id': e.get('id'),
                'label': e.get('label') or '(unlabelled)',
                'token_masked': _mask(e.get('token', '')),
                'token_full': e.get('token', ''),
                'created_at': e.get('created_at'),
                'last_used_at': e.get('last_used_at'),
                'is_legacy': not e.get('id'),
                'mcp_scopes': mcp_scopes,  # None → wildcard inherited
                'graphql_scopes': gql_scopes,
                'mcp_summary': _scope_summary(mcp_scopes),
                'graphql_summary': _scope_summary(gql_scopes),
            }
        )

    # If ?edit=<token_id> is in the query, render the permissions form
    # inline at the top of the page instead of just the table.
    edit_id = (request.GET.get('edit') or '').strip()
    edit_entry = None
    if edit_id:
        edit_entry = _find_entry(entries, edit_id)

    from plugins.installed.agent_mcp.scopes import AVAILABLE_SCOPES

    scope_catalog = [
        {'id': sid, 'label': label, 'description': desc}
        for sid, (label, desc) in AVAILABLE_SCOPES.items()
    ]

    edit_ctx = None
    if edit_entry is not None:
        mcp_current = edit_entry.get('mcp_scopes')
        gql_current = edit_entry.get('graphql_scopes')
        edit_ctx = {
            'id': edit_entry.get('id'),
            'label': edit_entry.get('label') or '(unlabelled)',
            'mcp_wildcard': mcp_current is None or '*' in (mcp_current or []),
            'graphql_wildcard': gql_current is None or '*' in (gql_current or []),
            'mcp_active': set(mcp_current or []),
            'graphql_active': set(gql_current or []),
            'approval_catalog': _approval_tools(),
            'approved_active': set(edit_entry.get('approved_tools') or []),
        }

    return render(
        request,
        'agent_mcp/tokens.html',
        {
            'rows': rows,
            'just_created_token': just_created_token,
            'just_created_label': just_created_label,
            'admin_rpc_url': '/mcp/admin/v1/',
            'graphql_url': '/graphql/',
            'scope_catalog': scope_catalog,
            'edit': edit_ctx,
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
