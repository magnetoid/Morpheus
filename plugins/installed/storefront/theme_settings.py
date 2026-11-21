"""The active theme's settings, on a Theme card under Settings, Storefront (v0.185.0).

A theme declares its settings in `get_config_schema()`; this page renders them the
way an app's settings card does and saves them through `MorpheusTheme.set_config`.
Linda reads and changes the same settings with `theme.describe` and `theme.set`.
"""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from core.authz import require_capability


@staff_member_required
@require_capability('system.write')
def theme_settings(request: HttpRequest) -> HttpResponse:
    from plugins import config_schema
    from themes.registry import theme_registry

    theme = theme_registry.active
    if theme is None:
        raise Http404('No active theme.')
    schema = theme.get_config_schema() or {}

    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        saved = config_schema.save_posted(theme, schema, request.POST, ajax=is_ajax)
        if is_ajax:
            return JsonResponse({'ok': True, 'saved': saved})
        return redirect(request.path)

    return render(
        request,
        'admin_dashboard/plugin_settings.html',
        {
            'panel': {'label': f'Theme: {theme.label}', 'description': theme.description},
            'plugin_name': 'theme',
            'fields': config_schema.form_fields(theme, schema),
            'empty_text': f'The active theme, {theme.label}, has no settings.',
            'active_nav': 'settings',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Settings', 'url': '/dashboard/settings/'},
                {'label': 'Storefront', 'url': '/dashboard/settings/storefront/'},
                {'label': 'Theme'},
            ],
        },
    )
