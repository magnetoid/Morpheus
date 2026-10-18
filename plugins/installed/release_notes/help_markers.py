"""A guide's markers, resolved against the live registry.

``[text](kind:target)`` in a guide (plugins/app_help.py) names a place instead of
writing its URL, so a moved or renamed page never leaves a dead link:

* ``page:<slug>``: one of the guide's app's dashboard pages; ``page:<app>/<slug>``
  another app's;
* ``settings:<app>``: the app's settings;
* ``field:<app>.<key>``: one field of those settings, by its live label;
* ``section:<key>``: a sidebar section;
* ``app:<name>``: another app's help.

A marker that names nothing resolves to None: the page shows its text without a
link, and tests/test_help_markers.py fails in CI. Everything is asked of the app
itself, so an app that is off still says where its places are.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Link:
    label: str  # the live name, e.g. "Products › Reviews"
    url: str  # '' when the place cannot be opened now
    off: bool = False  # the place exists, but its app is switched off


def ask_list(inst, method: str) -> list:
    """One of an app's ``contribute_*`` lists; a method that raises gives nothing."""
    try:
        return list(getattr(inst, method)() or [])
    except Exception:  # noqa: BLE001 — help describes an app, it never breaks on one
        return []


def pages_of(inst) -> list:
    return ask_list(inst, 'contribute_dashboard_pages')


def panel_of(inst):
    try:
        return inst.contribute_settings_panel()
    except Exception:  # noqa: BLE001
        return None


def page_link(page, owner: str, active: bool) -> Link:
    """Where a dashboard page is, in the dashboard's own words."""
    from plugins.installed.admin_dashboard import navigation

    page.plugin = owner
    url = navigation.page_url(page) if active else ''
    return Link(f'{navigation.page_section_label(page)} › {page.label}', url, off=not active)


def settings_link(inst, active: bool) -> Link | None:
    """Where an app's settings are: its settings panel, else its first settings page."""
    from plugins.installed.admin_dashboard import navigation
    from plugins.installed.admin_dashboard.settings_categories import get_category

    panel = panel_of(inst)
    if panel is not None:
        cat = get_category(navigation.settings_category_key(panel.category) or 'apps')
        label = f'Settings › {cat.label if cat else "Settings"} › {panel.label or inst.label}'
        url = f'/dashboard/settings/{inst.name}/' if active else ''
        return Link(label, url, off=not active)
    for page in pages_of(inst):
        if page.nav == 'settings':
            return page_link(page, inst.name, active)
    return None


def _registry_find(name: str):
    from plugins.registry import app_registry

    return app_registry.get(name)


def _registry_active(name: str) -> bool:
    from plugins.registry import app_registry

    return app_registry.is_active(name)


def _section(key: str) -> Link | None:
    from plugins.installed.admin_dashboard import navigation

    sec = navigation.section(key)
    if sec is None:
        return None
    url = sec.url or next(
        (t.url for t in navigation.tabs() if t.section == key and t.nav == 'main'), ''
    )
    return Link(sec.label, url)


def resolve(  # noqa: PLR0911 — a dispatcher: one return per marker kind
    kind: str,
    target: str,
    *,
    app: str,
    find: Callable | None = None,
    active: Callable | None = None,
) -> Link | None:
    """The place a marker names, or None. ``find`` and ``active`` default to the
    live registry; the guide checks pass ``app_help.load_manifest`` so a guide of
    an app this store does not install is checked too."""
    find = find or _registry_find
    active = active or _registry_active
    if kind == 'page':
        owner, _sep, slug = target.rpartition('/')
        owner = owner or app
        inst = find(owner)
        page = next((p for p in pages_of(inst) if p.slug == slug), None) if inst else None
        return page_link(page, owner, active(owner)) if page is not None else None
    if kind == 'settings':
        inst = find(target)
        return settings_link(inst, active(target)) if inst is not None else None
    if kind == 'field':
        owner, _sep, key = target.partition('.')
        inst = find(owner) if key else None
        panel = panel_of(inst) if inst is not None else None
        prop = ((panel.schema or {}).get('properties') or {}).get(key) if panel else None
        if prop is None:
            return None
        where = settings_link(inst, active(owner))
        # The settings form's own label rule (admin_dashboard/urls.py).
        label = prop.get('title') or key.replace('_', ' ').title()
        return Link(label, where.url, off=where.off)
    if kind == 'section':
        return _section(target)
    if kind == 'app':
        inst = find(target)
        return Link(inst.label or target, f'/dashboard/help/{target}/') if inst else None
    return None
