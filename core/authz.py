"""The authorization seam — one place that answers "may this user do X?".

Why this lives in core
----------------------
The *answer* comes from the `rbac` app (roles, bindings, channel scoping); the
*question* is asked by the dashboard, GraphQL resolvers, and anything else that
performs a sensitive action. Wiring those together with a direct import would
be a plugin→plugin dependency — the thing `scripts/check_plugin_boundary.py`
exists to stop. So core owns the seam, rbac subscribes to it, and a deployment
without rbac degrades to the historical behaviour instead of breaking.

Same shape as `core/pricing.py:apply_price_filter` and the
`AGENT_SYSTEM_PROMPT` seam: core fires, a plugin answers, absence is safe.

Fail-open, on purpose
---------------------
If nothing answers the filter — rbac absent, disabled, or mid-boot — this
returns the pre-RBAC behaviour: staff pass, everyone else doesn't. An
authorization layer that fails *closed* on its own absence would lock every
merchant out of their own dashboard the first time the app hiccups. Denial is
opt-in and explicit (see `enforcement_mode`), never an accident.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.authz')

# Enforcement modes, least to most strict.
#   off     — do not check at all (the seam is inert; zero overhead)
#   log     — check, record what WOULD be denied, allow it anyway  ← default
#   enforce — check, and actually deny
MODE_OFF = 'off'
MODE_LOG = 'log'
MODE_ENFORCE = 'enforce'
_MODES = (MODE_OFF, MODE_LOG, MODE_ENFORCE)

_DEFAULT_MODE = MODE_LOG


def enforcement_mode() -> str:
    """Read the merchant's enforcement setting, fresh.

    Read through the registry (`plugins.registry`, not `plugins.installed.*`) —
    the same route `core/agents/guardrails.py` uses for agent_core's config, and
    the only one the core-boundary ratchet permits.

    The cache is invalidated before the read for the reason documented in
    CLAUDE.md: a plugin's `_config_cache` is per-process, so a celery worker
    would otherwise never see a mode a merchant just flipped in the dashboard.
    One indexed query is cheap next to the request it guards.
    """
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('rbac')
        if plugin is None:
            return _DEFAULT_MODE
        plugin.invalidate_config_cache()
        mode = str(plugin.get_config_value('enforcement_mode', _DEFAULT_MODE) or '').strip()
        return mode if mode in _MODES else _DEFAULT_MODE
    except Exception:  # noqa: BLE001 — a config hiccup must never deny a request
        logger.debug('authz: enforcement_mode lookup failed; using default', exc_info=True)
        return _DEFAULT_MODE


def has_capability(user, capability: str, *, channel=None) -> bool:
    """True if `user` holds `capability` (optionally on `channel`).

    Superusers always pass — the escape hatch that makes a misconfigured role
    recoverable without a shell.

    Everyone else is decided by whoever answers `AUTHZ_CAPABILITY_CHECK`. The
    filter carries `value=None` meaning "nobody has answered yet"; a subscriber
    returns True or False. `None` surviving the filter means no authority is
    installed, so we fall back to `is_staff`.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True

    try:
        from core.hooks import MorpheusEvents, hook_registry

        answer = hook_registry.filter(
            MorpheusEvents.AUTHZ_CAPABILITY_CHECK,
            value=None,
            user=user,
            capability=capability,
            channel=channel,
        )
    except Exception:  # noqa: BLE001 — see module docstring: never fail closed by accident
        logger.warning('authz: capability check errored for %s; falling back', capability)
        answer = None

    if answer is None:
        return bool(getattr(user, 'is_staff', False))
    return bool(answer)


def check(user, capability: str, *, channel=None, target: str = '') -> bool:
    """Run a capability check under the current enforcement mode.

    Returns True when the caller may proceed. In `log` mode a *failed* check
    still returns True — but records the would-be denial, which is the whole
    point: the merchant gets a list of what enforcement would break before it
    breaks anything.
    """
    mode = enforcement_mode()
    if mode == MODE_OFF:
        return True

    allowed = has_capability(user, capability, channel=channel)
    if allowed:
        return True

    _audit_denial(user, capability, target=target, enforced=(mode == MODE_ENFORCE))
    return mode != MODE_ENFORCE


def _audit_denial(user, capability: str, *, target: str, enforced: bool) -> None:
    """Record a denial (or a would-be denial) — never raise from the audit path."""
    verb = 'denied' if enforced else 'would deny'
    logger.warning(
        'authz: %s %s for user=%s capability=%s target=%s',
        verb,
        'request' if enforced else '(log-only)',
        getattr(user, 'pk', None),
        capability,
        target or '-',
    )
    try:
        from core.audit import record

        record(
            event_type='authz.denied' if enforced else 'authz.would_deny',
            actor=user,
            target=target or capability,
            metadata={'capability': capability, 'enforced': enforced},
            severity='warning' if enforced else 'info',
        )
    except Exception:  # noqa: BLE001 — auditing must not break the request
        logger.debug('authz: audit record failed', exc_info=True)


def require_capability(capability: str, *, channel=None):
    """View decorator: gate a view on one capability.

    Stacks *under* the existing auth decorator, so the login/staff check still
    runs first::

        @staff_member_required
        @require_capability('orders.refund')
        def order_refund(request, order_id): ...

    In `enforce` mode a failed check returns 403 (HTML) or a JSON error for an
    AJAX/JSON request — the dashboard's fetch endpoints must return JSON on
    failure too, or the JS reports a false success (see CLAUDE.md).
    """
    from functools import wraps

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if check(
                getattr(request, 'user', None),
                capability,
                channel=getattr(request, 'channel', None) if channel is None else channel,
                target=request.path,
            ):
                return view(request, *args, **kwargs)
            return _forbidden(request, capability)

        wrapped.required_capability = capability  # introspectable by tests + tooling
        return wrapped

    return decorator


def _forbidden(request, capability: str):
    from django.http import HttpResponseForbidden, JsonResponse

    wants_json = request.headers.get(
        'x-requested-with'
    ) == 'XMLHttpRequest' or 'application/json' in (request.headers.get('accept', '') or '')
    if wants_json:
        return JsonResponse(
            {'ok': False, 'error': f'You do not have permission to do this ({capability}).'},
            status=403,
        )
    return HttpResponseForbidden(
        f'You do not have permission to do this. Missing capability: {capability}'
    )
