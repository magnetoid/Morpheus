"""Central scope catalog for Bearer-token permissions.

Each token entry stored under ``PluginConfig['agent_mcp']['public_keys']``
can carry two independent scope lists:

* ``mcp_scopes``     — gates calls to /mcp/admin/v1/ (and the cluster).
* ``graphql_scopes`` — gates calls to /graphql/ (and /graphql/agent/).

A token entry without a scope key inherits the wildcard ``*`` —
backward-compatible with any token that existed before this feature.
An explicitly empty list ``[]`` means "no access on this surface".

The catalog below is the canonical set of scope names the dashboard
permissions sub-page exposes as checkboxes. New scopes must be added
here AND wired into the matching @tool decorator (MCP) or mutation
guard (GraphQL).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

# Wildcard "everything" scope. Stored as a string so JSON serialisation
# round-trips cleanly. Tokens that hold this scope bypass every
# fine-grain check.
WILDCARD = '*'


# Catalog of scopes. Keys are the scope id used in the token's scope
# list AND in @tool(scopes=[...]). Values are dashboard-facing
# (label, description). Order here drives the order in the permissions
# UI, grouped by domain.
AVAILABLE_SCOPES: dict[str, tuple[str, str]] = {
    # Catalog
    'catalog.read': (
        'Catalog · read',
        'List + search products, categories, view product detail.',
    ),
    'catalog.write': (
        'Catalog · write',
        'Create + update products, categories, images. Includes publishing PDF books.',
    ),
    'catalog.delete': (
        'Catalog · destructive',
        'Hard-delete products + categories. Bypass with archive when possible.',
    ),
    # Inventory
    'inventory.read': (
        'Inventory · read',
        'View stock levels per variant/warehouse.',
    ),
    'inventory.write': (
        'Inventory · write',
        'Set + adjust stock quantities.',
    ),
    # Orders
    'orders.read': (
        'Orders · read',
        'List recent orders, view order detail.',
    ),
    'orders.write': (
        'Orders · write',
        'Mark fulfilled, mark shipped, update tracking.',
    ),
    'orders.cancel': (
        'Orders · cancel/refund',
        'Cancel orders, mark refunded. Destructive — affects payments + audit.',
    ),
    # Cart
    'cart.read': (
        'Cart · read',
        'Inspect cart contents (for assistant + agent flows).',
    ),
    'cart.write': (
        'Cart · write',
        'Add to cart, update, remove items.',
    ),
    # Analytics
    'analytics.read': (
        'Analytics · read',
        'Revenue, top products, time-window summaries.',
    ),
    # Content
    'content.write': (
        'Content · write',
        'AI content generation (product descriptions, etc.).',
    ),
    # Diagnostics — sensitive, opt-in
    'diagnostics.read': (
        'Diagnostics · read (sensitive)',
        'Logs, filesystem, plugin state. Grant carefully — exposes server internals.',
    ),
}


# Default scope set granted to a freshly created token (UI default).
# Lean toward "useful but not destructive" — wildcards on the destructive
# scopes opt them out by default.
DEFAULT_SCOPES: frozenset[str] = frozenset(
    {
        'catalog.read',
        'catalog.write',
        'inventory.read',
        'inventory.write',
        'orders.read',
        'orders.write',
        'cart.read',
        'analytics.read',
        'content.write',
    }
)


def token_scopes(entry: Any, surface: str) -> set[str]:
    """Return the active scope set for a token entry on a given surface.

    ``entry`` is whatever was stored in ``public_keys`` — a dict for
    UI-created tokens, or a raw string for legacy entries. ``surface``
    is ``'mcp'`` or ``'graphql'``.

    Legacy raw-string entries → wildcard. Dict entries without the
    surface-specific scope key → wildcard. Explicitly empty list → no
    access.
    """
    if not isinstance(entry, dict):
        # Legacy raw-string token — full access.
        return {WILDCARD}
    key = f'{surface}_scopes'
    if key not in entry:
        return {WILDCARD}
    val = entry.get(key)
    if val is None:
        return {WILDCARD}
    if not isinstance(val, (list, tuple, set)):
        return {WILDCARD}
    return {str(s).strip() for s in val if s}


def has_any(granted: Iterable[str], required: Iterable[str]) -> bool:
    """True iff the granted set contains the wildcard OR at least one
    of the required scopes. ``required=[]`` is interpreted as a public
    op — no scope check needed."""
    granted_set = set(granted)
    if WILDCARD in granted_set:
        return True
    needed = [r for r in required if r]
    if not needed:
        return True
    return any(r in granted_set for r in needed)


def find_entry_for_token(token: str) -> dict | None:
    """Look up the full entry dict for a presented token. Returns None
    for unknown tokens or for legacy raw-string entries (those have no
    metadata to fetch)."""
    if not token:
        return None
    try:
        from plugins.models import PluginConfig

        cfg = PluginConfig.objects.filter(plugin_name='agent_mcp').first()
        if cfg is None:
            return None
        for k in (cfg.config or {}).get('public_keys', []):
            if isinstance(k, dict) and (k.get('token') or '').strip() == token:
                return k
    except Exception:  # noqa: BLE001
        return None
    return None
