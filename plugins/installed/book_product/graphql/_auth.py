"""Scope/staff auth for book_product mutations (mirrors catalog's pattern)."""

from __future__ import annotations


def _request(info):
    ctx = info.context
    return getattr(ctx, 'request', None) or (ctx.get('request') if isinstance(ctx, dict) else None)


def _is_staff(info) -> bool:
    req = _request(info)
    user = getattr(req, 'user', None) if req else None
    return bool(user and getattr(user, 'is_staff', False))


def check_scope(info, required: list[str]) -> str:
    """'' when authorised; otherwise a human-readable error.

    Session-authenticated staff bypass scope checks; Bearer-token requests must
    carry one of the required GraphQL scopes (or wildcard)."""
    if not _is_staff(info):
        return 'Forbidden — staff only.'
    req = _request(info)
    granted = getattr(req, '_morph_token_scopes_graphql', None)
    if granted is None:
        return ''  # session staff → no token scope restriction
    try:
        from plugins.installed.agent_mcp.scopes import has_any  # noqa: PLC0415
    except Exception:  # noqa: BLE001 — scopes util absent → don't hard-block staff
        return ''
    if not has_any(granted, required):
        return f'token missing scope: needs one of {sorted(required)}'
    return ''
