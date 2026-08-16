"""System pages for the admin dashboard — the updating-system UI.

**Updates** page: the component version inventory (core / apps / themes) from
``core.versioning``, the platform update status, and the per-app / per-theme
updates the signed release channel publishes for what is installed here.
Applying wraps the same guarded engines the CLI uses (``core.updates`` for the
platform, ``core.component_updates`` for one app or theme).
"""

# ruff: noqa: PLC0415, I001
# Inline imports match the views_split convention.

from __future__ import annotations

from core.authz import require_capability
from morpheus.app.views import (
    HttpRequest,
    HttpResponse,
    messages,
    redirect,
    render,
    staff_member_required,
)


@staff_member_required
def updates_page(request: HttpRequest) -> HttpResponse:
    from django.conf import settings as dj_settings

    from core.updates import cached_update_status, platform_update_status
    from core.versioning import component_versions

    data = component_versions()
    plugins = data.get('plugins') or []
    platform = platform_update_status(fetch=False)
    # Per-app/theme updates come from the last check (daily beat, or the
    # "Check for updates" button) — never a network call on page load.
    components = platform.get('components')
    if components is None:
        components = (cached_update_status() or {}).get('components') or []
    return render(
        request,
        'admin_dashboard/updates.html',
        {
            'core_version': data.get('core', 'unknown'),
            'plugins': plugins,
            'themes': data.get('themes') or [],
            'plugin_enabled_count': sum(1 for p in plugins if p.get('enabled')),
            'platform': platform,
            'component_updates': components,
            'self_update_enabled': bool(
                getattr(dj_settings, 'MORPHEUS_SELF_UPDATE_ENABLED', False)
            ),
            'active_nav': 'updates',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Updates'},
            ],
        },
    )


@staff_member_required
def updates_check(request: HttpRequest) -> HttpResponse:
    """Fetch remote refs / the release source, recompute the status, and cache
    it — so the page (and the activity feed) reflect the check without waiting
    for the daily beat."""
    if request.method != 'POST':
        return redirect('admin_dashboard:updates')
    from core.updates import refresh_update_status

    status = refresh_update_status()
    avail = status.get('available')
    if avail == 'yes':
        behind = status.get('behind')
        detail = (
            f'{behind} commit(s) behind upstream'
            if behind is not None
            else f'{status.get("latest")} is published'
        )
        messages.success(request, f'Update available — {detail}.')
    elif avail == 'no':
        messages.success(request, 'You are on the latest version.')
    elif avail == 'unavailable':
        messages.info(
            request, status.get('reason') or 'Update check unavailable in this deployment.'
        )
    else:
        messages.info(request, status.get('reason') or 'Could not determine update status.')
    n = len(status.get('components') or [])
    if n:
        messages.info(request, f'{n} app/theme update(s) available — see below.')
    return redirect('admin_dashboard:updates')


@staff_member_required
@require_capability('system.write')
def updates_apply_component(request: HttpRequest) -> HttpResponse:
    """Update one app or theme from the signed manifest — wraps
    ``core.component_updates.apply_component_update`` (same opt-in, verified
    artifact, boot probe, rollback as the CLI)."""
    if request.method != 'POST':
        return redirect('admin_dashboard:updates')
    from core.component_updates import apply_component_update

    kind = (request.POST.get('kind') or '').strip()
    name = (request.POST.get('name') or '').strip()
    result = apply_component_update(kind, name, confirm=True)
    status = result.get('status')
    label = f'{kind} {name}'.strip()
    if status == 'applied':
        messages.success(
            request,
            f'{label} updated {result.get("from")} → {result.get("to")}. '
            'Restart the web and worker processes to load the new code.',
        )
    elif status == 'noop':
        messages.success(request, f'{label} is already current.')
    elif status == 'rolled_back':
        messages.error(request, result.get('reason') or f'{label}: update failed — rolled back.')
    elif status == 'disabled':
        messages.info(request, result.get('reason') or 'Self-update is disabled.')
    else:
        messages.error(request, result.get('reason') or f'{label}: update {status}.')
    return redirect('admin_dashboard:updates')


@staff_member_required
@require_capability('system.write')
def updates_apply(request: HttpRequest) -> HttpResponse:
    """Apply the pending platform update from the dashboard — wraps the same
    guarded core.updates.apply_platform_update the CLI uses (opt-in via
    MORPHEUS_SELF_UPDATE_ENABLED, ff-only, backup, auto-rollback)."""
    if request.method != 'POST':
        return redirect('admin_dashboard:updates')
    from core.updates import apply_platform_update

    result = apply_platform_update(confirm=True)
    status = result.get('status')
    if status == 'applied':
        messages.success(
            request,
            f'Updated {result.get("from")} → {result.get("to")}. '
            'Migrations ran and the healthcheck passed.',
        )
    elif status == 'noop':
        messages.success(request, 'Already up to date.')
    elif status == 'rolled_back':
        messages.error(
            request, result.get('reason') or 'Update failed — rolled back to the prior version.'
        )
    elif status in ('diverged', 'apply_failed'):
        messages.error(request, result.get('reason') or 'Update could not be applied.')
    elif status == 'deps_changed':
        messages.error(
            request,
            result.get('reason')
            or 'This update changes dependencies — rebuild/redeploy the image instead.',
        )
    elif status == 'disabled':
        messages.info(request, result.get('reason') or 'Self-update is disabled.')
    elif status == 'unavailable':
        messages.info(request, result.get('reason') or 'Update unavailable in this deployment.')
    else:
        messages.info(
            request, result.get('reason') or result.get('message') or 'Update status unknown.'
        )
    return redirect('admin_dashboard:updates')
