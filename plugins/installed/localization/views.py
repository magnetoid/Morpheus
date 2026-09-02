"""Localization plugin views.

Thin wrapper over core.i18n services. The heavy lifting (DB schema,
fallback chain, agent auto-translate) lives in core; these views just
shape data for the admin templates.
"""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from core.authz import require_capability


@staff_member_required
@require_capability('system.read')
def translations_index(request):
    """Top-level table of translatable rows + their per-language status."""
    rows: list[dict] = []
    enabled_languages: list[str] = []
    try:
        from core.i18n.models import Translation

        # One row per (content_type, object_id) the platform has any
        # translation for. Aggregate counts per language so the UI can
        # show "fully translated / partial / missing" badges.
        qs = Translation.objects.all().order_by('-updated_at')[:200]
        agg: dict[tuple, dict] = {}
        for t in qs:
            key = (t.content_type_id, t.object_id)
            row = agg.setdefault(
                key,
                {
                    'content_type': t.content_type,
                    'object_id': t.object_id,
                    'languages': set(),
                    'updated_at': t.updated_at,
                },
            )
            row['languages'].add(t.language)
        for r in agg.values():
            r['languages'] = sorted(r['languages'])
            rows.append(r)
    except Exception:  # noqa: BLE001 — core.i18n may not be migrated yet
        rows = []
    try:
        from core.i18n.services import list_enabled_languages

        enabled_languages = list_enabled_languages()
    except Exception:  # noqa: BLE001
        enabled_languages = []
    return render(
        request,
        'localization/translations.html',
        {
            'rows': rows,
            'enabled_languages': enabled_languages,
            'active_nav': 'apps',
            'active_apps_slug': 'localization/translations',
        },
    )


@staff_member_required
@require_capability('system.write')
def languages_index(request):
    """Pick which target languages the store ships to. POST persists."""
    enabled: list[str] = []
    try:
        from core.i18n.services import list_enabled_languages, set_enabled_languages

        enabled = list_enabled_languages()
        if request.method == 'POST':
            codes = [
                c.strip().lower() for c in (request.POST.get('codes') or '').split(',') if c.strip()
            ]
            set_enabled_languages(codes)
            enabled = codes
    except Exception:  # noqa: BLE001
        # core.i18n.services may not expose the setter helpers yet;
        # render the form anyway so the admin sees what would persist.
        enabled = []
    return render(
        request,
        'localization/languages.html',
        {
            'enabled': enabled,
            'enabled_csv': ', '.join(enabled),
            'active_nav': 'apps',
            'active_apps_slug': 'localization/languages',
        },
    )
