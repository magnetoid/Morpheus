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

    # Read the intended-enabled state from the DB (PluginConfig) — that's
    # the source of truth a merchant just edited. The in-memory
    # `app_registry.is_active()` only reflects boot-time state, so it
    # lags behind by one container restart for newly-enabled plugins.
    # For disables, _toggle_plugin calls .deactivate() which tears down
    # contributions in-place, so the runtime DOES match. The "needs
    # restart to take effect" hint shows up only on plugins flipped ON.
    db_enabled: dict[str, bool] = {}
    try:
        from plugins.models import PluginConfig

        db_enabled = dict(PluginConfig.objects.values_list('plugin_name', 'is_enabled'))
    except Exception:  # noqa: BLE001, S110
        pass

    plugins = []
    for name, cls in sorted(app_registry._classes.items()):
        if is_system(name):
            # Hide system plugins from the apps catalog — they belong
            # to a higher-level concept the merchant edits elsewhere
            # (Linda for agent_core, etc.).
            continue
        runtime_active = app_registry.is_active(name)
        db_intends_on = db_enabled.get(name, True)
        # "Active" is what the merchant sees in the button label.
        # We prefer the DB intent (matches what they just clicked).
        plugins.append(
            {
                'name': name,
                'label': getattr(cls, 'label', name),
                'description': getattr(cls, 'description', ''),
                'version': getattr(cls, 'version', ''),
                'active': db_intends_on,
                # When the DB says "on" but the runtime didn't pick it up at
                # boot, we show a "Restart to take effect" hint so the
                # merchant isn't confused why their just-enabled plugin
                # doesn't surface its dashboard pages yet.
                'needs_restart': db_intends_on and not runtime_active,
                'pages': [p for p in app_registry.dashboard_pages() if p.plugin == name],
                'has_settings': app_registry.settings_panel(name) is not None,
            }
        )
    return render(
        request,
        'admin_dashboard/apps.html',
        {
            'plugins': plugins,
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
    """POST handler on the apps page: flip a plugin's enabled state.

    On DISABLE — writes PluginConfig.is_enabled=False AND immediately
    calls app_registry.deactivate() so URLs / hooks / dashboard
    pages drop out of the running process. The merchant sees the
    change instantly without a container restart.

    On ENABLE — writes PluginConfig.is_enabled=True AND immediately calls
    app_registry.activate() so ready() runs, URLs re-mount, and the
    settings panel / storefront blocks / nav entries appear without a
    restart. Only if runtime activation fails (e.g. a plugin needing
    boot-level config like middleware) does the apps view keep the
    "Restart to take effect" pill.

    Refuses to disable protected plugins — the dashboard plugin's own
    UI lives in admin_dashboard, so disabling it would lock the
    merchant out of every dashboard page (including this one).
    """
    name = request.POST.get('plugin', '').strip()
    desired = request.POST.get('enabled') == '1'
    if not desired and is_protected(name):
        messages.error(
            request,
            f'{name!r} cannot be disabled — it is required for the dashboard to function.',
        )
        return redirect('admin_dashboard:apps')
    try:
        from plugins.models import PluginConfig

        row, _ = PluginConfig.objects.get_or_create(plugin_name=name)
        row.is_enabled = desired
        row.save(update_fields=['is_enabled', 'updated_at'])
    except Exception as e:  # noqa: BLE001 — DB outage shouldn't crash the page
        logger.warning('admin_dashboard: toggle %s failed: %s', name, e, exc_info=True)
        return redirect('admin_dashboard:apps')

    # Apply the runtime side of the change.
    try:
        from plugins.registry import app_registry

        if not desired:
            # registry.deactivate runs on_disable + drops contributions +
            # removes the plugin from _active. Idempotent — safe to call
            # on a plugin that's already inactive.
            app_registry.deactivate(name)
            messages.success(request, f'{name!r} disabled.')
        elif app_registry.activate(name):
            # registry.activate runs ready() (first time), re-mounts URLs and
            # re-collects contributions so the plugin lights up immediately.
            messages.success(request, f'{name!r} enabled.')
        else:
            # Activation failed (e.g. a plugin needing boot-level config). The
            # DB write stands; the apps view keeps the "restart" pill.
            messages.warning(
                request,
                f'{name!r} enabled, but it needs a web-container restart to fully load.',
            )
    except Exception as e:  # noqa: BLE001 — never let a runtime hiccup hide the DB write
        logger.warning('admin_dashboard: runtime toggle for %s failed: %s', name, e, exc_info=True)
    return redirect('admin_dashboard:apps')


# ── Settings ──────────────────────────────────────────────────────────────────
