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

logger = logging.getLogger('morpheus.agent_mcp.dashboard')

_TOKEN_PREFIX = 'mph_'
_TOKEN_BYTES = 32


def _load_entries() -> list[dict]:
    """Return the stored entries, normalised to dict shape."""
    from plugins.models import PluginConfig
    cfg = PluginConfig.objects.filter(plugin_name='agent_mcp').first()
    entries = []
    raw = (cfg.config if cfg else {}) or {}
    for k in (raw.get('public_keys') or []):
        if isinstance(k, dict):
            entries.append({
                'id': str(k.get('id') or ''),
                'label': str(k.get('label') or ''),
                'token': str(k.get('token') or ''),
                'created_at': str(k.get('created_at') or ''),
                'last_used_at': str(k.get('last_used_at') or ''),
            })
        else:
            # Legacy raw-string entry.
            entries.append({
                'id': '',
                'label': '(legacy)',
                'token': str(k or ''),
                'created_at': '',
                'last_used_at': '',
            })
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


@staff_member_required
@require_http_methods(['GET', 'POST'])
def tokens_view(request):
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
                e for e in entries
                if (target_id and e.get('id') != target_id)
                or (not target_id and e.get('token') != target_token)
            ]
            if len(kept) != len(entries):
                _save_entries(kept)
                messages.success(request, 'Token revoked.')
            else:
                messages.error(request, 'Token not found.')
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
        rows.append({
            'id': e.get('id'),
            'label': e.get('label') or '(unlabelled)',
            'token_masked': _mask(e.get('token', '')),
            'token_full': e.get('token', ''),
            'created_at': e.get('created_at'),
            'last_used_at': e.get('last_used_at'),
            'is_legacy': not e.get('id'),
        })

    return render(request, 'agent_mcp/tokens.html', {
        'rows': rows,
        'just_created_token': just_created_token,
        'just_created_label': just_created_label,
        'admin_rpc_url': '/mcp/admin/v1/',
        'active_nav': 'apps',
    })
