"""The Help area: /dashboard/help/ and /dashboard/help/<app>/.

Every staff member may read help, whatever their role: no capability is held by
every role (rbac's templates), and help shows documentation, not store data. The
screens it links to still check access themselves.
Spec: docs/superpowers/specs/2026-10-18-help-system-design.md.
"""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import render

from plugins import app_help
from plugins.installed.release_notes import help_facts, help_render, help_search


def _entries() -> list[dict]:
    """One row per installed app, for the index."""
    from plugins.installed.admin_dashboard import navigation
    from plugins.registry import app_registry

    rows = []
    for inst in app_registry.all_plugins():
        rows.append(
            {
                'name': inst.name,
                'label': inst.label or inst.name,
                'summary': app_help.summary(inst.name) or inst.description,
                'area': navigation.describe_app(inst)['area'],
                'active': app_registry.is_active(inst.name),
            }
        )
    return rows


def _groups(rows: list[dict]) -> list[dict]:
    """``[{'label', 'apps'}]`` in the Apps catalogue's area order."""
    from plugins.installed.admin_dashboard import navigation

    order = {key: i for i, (key, _label) in enumerate(navigation.CATALOGUE_AREAS)}
    labels = dict(navigation.CATALOGUE_AREAS)
    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(row['area'], []).append(row)
    return [
        {
            'label': labels.get(key, key.title()),
            'apps': sorted(apps, key=lambda r: r['label'].casefold()),
        }
        for key, apps in sorted(groups.items(), key=lambda kv: order.get(kv[0], len(order)))
    ]


@staff_member_required
def help_index(request):
    rows = _entries()
    query = (request.GET.get('q') or '').strip()[:100]
    return render(
        request,
        'release_notes/help_index.html',
        {
            'q': query,
            'results': help_search.search(query) if query else [],
            'groups': _groups([r for r in rows if r['active']]),
            'off': sorted(
                (r for r in rows if not r['active']), key=lambda r: r['label'].casefold()
            ),
            'active_nav': 'settings',
        },
    )


@staff_member_required
def help_app(request, app: str):
    found = help_facts.facts(app)
    if found is None:
        raise Http404('No such app.')
    guide = app_help.guide(app)
    return render(
        request,
        'release_notes/help_app.html',
        {
            'facts': found,
            'summary': guide.summary if guide else found['description'],
            'guide_html': help_render.render(guide.body, app=app) if guide else '',
            'active_nav': 'settings',
        },
    )


@staff_member_required
def help_redirect(request):
    """The Help card's old address, /dashboard/apps/release_notes/help/."""
    return HttpResponsePermanentRedirect('/dashboard/help/')
