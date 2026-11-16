"""Auto-split from the legacy admin_dashboard/views.py monolith."""

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
from plugins.installed.admin_dashboard.views_split._shared import (
    logger,
)


@staff_member_required
@require_capability('system.write')
def apps_view(request: HttpRequest) -> HttpResponse:
    from plugins.registry import app_registry

    if request.method == 'POST':
        return _toggle_plugin(request)

    # The stored switch (PluginConfig) is what the merchant set; every process
    # follows it before its next request or task (`AppRegistry.reconcile`), so
    # this worker already runs on it.
    db_enabled: dict[str, bool] = {}
    try:
        from plugins.models import PluginConfig

        db_enabled = dict(PluginConfig.objects.values_list('plugin_name', 'is_enabled'))
    except Exception:  # noqa: BLE001, S110
        pass

    from morpheus.core import MorpheusEvents, hook_registry
    from plugins import app_help
    from plugins.installed.admin_dashboard import navigation

    def help_link(name):
        try:
            link = hook_registry.filter(
                MorpheusEvents.DASHBOARD_PAGE_HELP, value=None, app=name, request=request
            )
        except Exception:  # noqa: BLE001 — a Help link never breaks the catalogue
            return None
        return link if isinstance(link, dict) and link.get('url') else None

    plugins = []
    for name, cls in sorted(app_registry._classes.items()):
        if is_system(name):
            # Hide system plugins from the apps catalog — they belong
            # to a higher-level concept the merchant edits elsewhere
            # (Linda for agent_core, etc.).
            continue
        db_intends_on = db_enabled.get(name, True)
        instance = app_registry.get(name)
        # Where the app lives and what it adds, in the menu's own words —
        # asked of the app, so one that is off still says what it would add.
        described = (
            navigation.describe_app(instance)
            if instance is not None
            else {'area': 'platform', 'area_label': 'Platform', 'adds': []}
        )
        # "Active" is what the merchant sees in the button label: the stored switch.
        plugins.append(
            {
                'name': name,
                'label': getattr(cls, 'label', name),
                'description': getattr(cls, 'description', ''),
                # The app's one sentence for staff (its help.md), else the
                # developer description; and its Help link.
                'summary': app_help.summary(name) or getattr(cls, 'description', ''),
                'help': help_link(name),
                'version': getattr(cls, 'version', ''),
                'active': db_intends_on,
                # On for the store, but its start-up failed in the worker serving
                # this page; reconcile never retries it there, a restart does.
                'start_failed': db_intends_on and name in app_registry._failed,
                'pages': [
                    {'label': p.label, 'icon': p.icon, 'url': navigation.page_url(p)}
                    for p in app_registry.dashboard_pages()
                    if p.plugin == name and p.nav != 'hidden'
                ],
                'has_settings': app_registry.settings_panel(name) is not None,
                'area': described['area'],
                'adds': described['adds'],
            }
        )
    # Grouped the way the dashboard is: one heading per area, in menu order.
    order = {key: i for i, (key, _label) in enumerate(navigation.CATALOGUE_AREAS)}
    labels = dict(navigation.CATALOGUE_AREAS)
    groups: dict[str, list] = {}
    for app in plugins:
        groups.setdefault(app['area'], []).append(app)
    areas = [
        {'key': key, 'label': labels.get(key, key.title()), 'apps': apps}
        for key, apps in sorted(groups.items(), key=lambda kv: order.get(kv[0], len(order)))
    ]
    return render(
        request,
        'admin_dashboard/apps.html',
        {
            'plugins': plugins,
            'areas': areas,
            'active_count': sum(1 for p in plugins if p['active']),
            'active_nav': 'apps',
        },
    )


@staff_member_required
@require_capability('system.read')
def apps_store_view(request: HttpRequest) -> HttpResponse:
    """Browse + install surface for community apps.

    Reads from a static registry today
    (`plugins/installed/admin_dashboard/data/apps_registry.json`); future
    iterations point this at a remote index. Each entry carries enough
    metadata for the merchant to decide + a copy-pasteable install
    command. Auto-install via pip + manifest mutation is a separate PR;
    this is the MVP browse surface.

    Installed apps (status='installed') are detected against the live
    plugin registry so the UI shows a green badge instead of an install
    button. Anything in the JSON that's not yet a real plugin renders
    with 'planned' or 'available' status.
    """
    import json
    import os

    from plugins.registry import app_registry

    registry_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data',
        'apps_registry.json',
    )
    apps_data = {'apps': []}
    try:
        with open(registry_path) as fh:
            apps_data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning('apps_store: registry read failed: %s', exc)

    installed_plugin_names = set(app_registry._classes.keys())
    # Installed themes are detected by directory presence under
    # themes/library/<slug>/ — themes don't go through the plugin registry.
    installed_theme_dirs: set[str] = set()
    try:
        themes_root = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            ),
            'themes',
            'library',
        )
        if os.path.isdir(themes_root):
            installed_theme_dirs = {
                d
                for d in os.listdir(themes_root)
                if os.path.isdir(os.path.join(themes_root, d)) and not d.startswith('_')
            }
    except OSError:
        pass

    rows = []
    for app in apps_data.get('apps', []):
        slug = (app.get('slug') or '').strip()
        app_type = (app.get('type') or 'plugin').lower()
        if app_type == 'theme':
            # Slug → directory name conventions: strip the -theme suffix.
            dir_candidate = slug.replace('-theme', '').replace('-', '_')
            is_installed = (
                dir_candidate in installed_theme_dirs
                or slug.replace('-', '_') in installed_theme_dirs
            )
        else:
            # Plugins: registry match on slug (kebab → snake).
            is_installed = slug.replace('-', '_') in installed_plugin_names
        rows.append({**app, 'type': app_type, 'is_installed': is_installed})

    # Group by category for the page layout.
    categories: dict[str, list] = {}
    for r in rows:
        cat = r.get('category') or 'Other'
        categories.setdefault(cat, []).append(r)

    return render(
        request,
        'admin_dashboard/apps_store.html',
        {
            'categories': sorted(categories.items()),
            'total': len(rows),
            'installed_count': sum(1 for r in rows if r['is_installed']),
            'registry_version': apps_data.get('version', '?'),
            'registry_updated_at': apps_data.get('updated_at', ''),
            'active_nav': 'apps',
        },
    )


# Both classifications used to live here as hardcoded frozensets — a shell
# holding a list of facts about *other* apps. They now come from one place
# each: `core.safety.is_plugin_protected` (shared with Linda's disable tools,
# which previously used a different, shorter list) and the app's own
# `system` manifest flag. Kept as thin wrappers so this module keeps a single
# vocabulary and callers don't each re-derive it.


def is_protected(name: str) -> bool:
    """True if this app may not be disabled (soft-brick risk)."""
    from core.safety import is_plugin_protected

    return is_plugin_protected(name)


def is_system(name: str) -> bool:
    """True if this app is never listed in the Apps catalogue."""
    from plugins.registry import app_registry

    cls = app_registry._classes.get(name)
    return bool(cls is not None and getattr(cls, 'system', False))


def _toggle_plugin(request: HttpRequest):
    """POST handler on the apps page: switch an app on or off for the whole store.

    `plugins.services.set_enabled` decides (the app exists, what it needs is on,
    nothing that needs it is on, the store can run without it: a protected app,
    such as this dashboard's own, is refused) and carries it out. The change
    applies here at once and in every other web and Celery worker at its next
    request or task, so nothing waits for a restart.
    """
    from plugins.services import AppSwitchRefused, set_enabled

    name = request.POST.get('plugin', '').strip()
    desired = request.POST.get('enabled') == '1'
    try:
        switch = set_enabled(name, desired, actor=request.user)
    except AppSwitchRefused as e:
        messages.error(request, str(e))
    except Exception as e:  # noqa: BLE001 — a failed switch must not crash the page
        logger.warning('admin_dashboard: toggle %s failed: %s', name, e, exc_info=True)
        messages.error(request, f'{name!r} could not be switched. The error log has the details.')
    else:
        messages.success(request, f'{switch.label} {"is on" if desired else "is off"}.')
    return redirect('admin_dashboard:apps')


# ── Settings ──────────────────────────────────────────────────────────────────
