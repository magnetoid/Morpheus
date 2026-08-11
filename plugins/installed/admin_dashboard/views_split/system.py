"""System pages for the admin dashboard — the updating-system UI (phase 2).

Read-only **Updates** page: surfaces the component version inventory
(core / plugins / themes) from ``core.versioning``. Remote update-checks +
apply land in later phases (docs/plans/updating-system-2026-06.md).
"""

# ruff: noqa: PLC0415, I001
# Inline imports match the views_split convention.

from __future__ import annotations

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

    from core.updates import platform_update_status
    from core.versioning import component_versions

    data = component_versions()
    plugins = data.get('plugins') or []
    return render(
        request,
        'admin_dashboard/updates.html',
        {
            'core_version': data.get('core', 'unknown'),
            'plugins': plugins,
            'themes': data.get('themes') or [],
            'plugin_enabled_count': sum(1 for p in plugins if p.get('enabled')),
            'platform': platform_update_status(fetch=False),
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
    """Fetch remote refs + recompute platform update status (best-effort)."""
    if request.method != 'POST':
        return redirect('admin_dashboard:updates')
    from core.updates import platform_update_status

    status = platform_update_status(fetch=True)
    avail = status.get('available')
    if avail == 'yes':
        messages.success(
            request, f'Update available — {status.get("behind")} commit(s) behind upstream.'
        )
    elif avail == 'no':
        messages.success(request, 'You are on the latest version.')
    elif avail == 'unavailable':
        messages.info(
            request, status.get('reason') or 'Update check unavailable in this deployment.'
        )
    else:
        messages.info(request, status.get('reason') or 'Could not determine update status.')
    return redirect('admin_dashboard:updates')


@staff_member_required
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
