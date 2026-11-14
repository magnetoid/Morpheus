"""Cmd+K search: the dashboard's one search box, across every app.

The shell lists what the registry knows: every dashboard page (the navigation's
tabs and settings tools), every app (to its settings, its first page, or its card
in the Apps catalogue while it is off), every field of every app's settings, and
every email the store sends. Every app adds the records it owns through
``DASHBOARD_SEARCH`` (orders, products, coupons, reviews, its guide…), so a
switched-off app's records leave with it. Matching and ranking are
``plugins/dashboard_search.py``; the best section comes first, and a hit whose
capability the user lacks is dropped while roles are enforced.

Each hit carries ``section``, ``kind``, ``label``, ``hint``, ``url``, ``icon``.
Every source is fail-soft: one that raises contributes nothing.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from core.authz import MODE_ENFORCE, enforcement_mode, has_capability, require_capability
from morpheus.app.views import (
    HttpRequest,
    HttpResponse,
    staff_member_required,
)
from plugins import dashboard_search as ds

logger = logging.getLogger('morpheus.admin')

# High-value create/jump actions that aren't registered DashboardPages.
_ACTIONS = [
    ('Home', 'Dashboard overview', '/dashboard/', 'home'),
    ('New order', 'Create a draft order', '/dashboard/orders/new/', 'plus'),
    ('New product', 'Create a product', '/dashboard/products/new/', 'plus'),
    ('New customer', 'Create a customer', '/dashboard/customers/new/', 'plus'),
    ('All orders', 'Open the orders list', '/dashboard/orders/', 'shopping-bag'),
    ('All products', 'Open the products list', '/dashboard/products/', 'package'),
    ('Customers', 'Open the customers list', '/dashboard/customers/', 'users'),
    ('Settings', 'Store configuration', '/dashboard/settings/', 'settings'),
]

#: Sections the shell fills, in the order they win a tie; records come after
#: them, then emails and guides.
_FIRST = ('Go to', 'Apps', 'Settings')
_LAST = ('Emails', 'Help')
_CAP = {'Go to': 6}
_PER_SECTION = 5
_TOTAL = 60
_EMPTY_QUERY = 12
#: Records are asked for from this many characters on.
_MIN_RECORD_QUERY = 2


def _app_labels() -> dict[str, str]:
    from plugins.registry import app_registry  # noqa: PLC0415

    return {inst.name: inst.label or inst.name for inst in app_registry.all_plugins()}


def _nav_hits(words: list[str], user=None, labels: dict | None = None) -> list[dict]:
    """Every dashboard page + core actions. Pages come from the navigation
    (admin_dashboard/navigation.py) — the shell's tabs, every app's pages including
    the ones only a card links to, and every settings tool — so a page is findable
    even when no menu lists it, and by the name of the app it belongs to."""
    labels = labels if labels is not None else _app_labels()
    hits: list[dict] = []

    def add(label, hint, url, icon, *more):
        score = ds.score(words, label, hint, *more) if words else 1
        if score:
            hits.append(
                {
                    'section': 'Go to',
                    'kind': 'nav',
                    'label': label,
                    'hint': hint,
                    'url': url,
                    'icon': icon,
                    'score': score,
                }
            )

    for label, hint, url, icon in _ACTIONS:
        add(label, hint, url, icon)

    try:
        from plugins.installed.admin_dashboard import navigation  # noqa: PLC0415
        from plugins.installed.admin_dashboard.settings_categories import (  # noqa: PLC0415
            get_category,
        )

        for tab in navigation.tabs(user):
            where = navigation.section_label(tab.section)
            owner = tab.plugin or tab.app
            add(
                tab.label,
                f'{where} › {tab.group}' if tab.group else where,
                tab.url,
                tab.icon,
                tab.hint,
                labels.get(owner, ''),
            )
        for tool in navigation.tools():
            cat = get_category(tool.category)
            add(
                tool.label,
                f'Settings › {cat.label}' if cat else 'Settings',
                tool.url,
                tool.icon,
                tool.hint,
                labels.get(tool.plugin, ''),
            )
    except Exception:  # noqa: BLE001 — the palette must answer even if the nav can't
        logger.warning('palette: navigation entries failed', exc_info=True)
    return hits


def _first_pages(user) -> dict[str, str]:
    """Each app's first page in the menu, else its first settings page."""
    from plugins.installed.admin_dashboard import navigation  # noqa: PLC0415

    first: dict[str, str] = {}
    for tab in navigation.tabs(user):
        if tab.plugin and tab.nav == 'main':
            first.setdefault(tab.plugin, tab.url)
    for tool in navigation.tools():
        if tool.plugin:
            first.setdefault(tool.plugin, tool.url)
    return first


def _app_hits(words: list[str], user=None) -> list[dict]:
    """Every app by its name: to its settings, else its first page; one that is
    switched off, to its card in the Apps catalogue, where it is switched on."""
    from plugins.registry import app_registry  # noqa: PLC0415

    hits: list[dict] = []
    try:
        first = _first_pages(user)
        for inst in app_registry.all_plugins():
            label = inst.label or inst.name
            score = ds.score(words, label, inst.name.replace('_', ' '))
            if not score:
                continue
            active = app_registry.is_active(inst.name)
            if active and app_registry.settings_panel(inst.name) is not None:
                url, hint = f'/dashboard/settings/{inst.name}/', 'App · its settings'
            elif active and inst.name in first:
                url, hint = first[inst.name], 'App · its pages'
            elif getattr(inst, 'system', False):
                continue  # the catalogue does not list it
            else:
                url = f'/dashboard/apps/#app-{inst.name}'
                hint = 'App · switched on' if active else 'App · switched off, open it in Apps'
            hits.append(
                {
                    'section': 'Apps',
                    'kind': 'app',
                    'label': label,
                    'hint': hint,
                    'url': url,
                    'icon': 'puzzle',
                    'score': score,
                }
            )
    except Exception:  # noqa: BLE001
        logger.warning('palette: app entries failed', exc_info=True)
    return hits


def _setting_hits(words: list[str], labels: dict) -> list[dict]:
    """Every field of every app's settings, by its label, its description or its
    key, to the field itself; an app's name narrows ("audiobooks voice") but never
    lists a field on its own."""
    from plugins.registry import app_registry  # noqa: PLC0415

    hits: list[dict] = []
    try:
        for row in app_registry.all_settings_panels():
            name, panel = row['plugin'], row['panel']
            title = panel.label or labels.get(name, name)
            url = f'/dashboard/settings/{name}/'
            score = ds.score(words, title, panel.description or '')
            if score:
                hits.append(
                    {
                        'section': 'Settings',
                        'kind': 'settings',
                        'label': f'{title} settings',
                        'hint': panel.description or '',
                        'url': url,
                        'icon': 'settings',
                        'score': score,
                    }
                )
            for key, prop in ((panel.schema or {}).get('properties') or {}).items():
                field = prop.get('title') or key.replace('_', ' ').title()
                own = (field, prop.get('description') or '', key.replace('_', ' '))
                if not any(ds.score([w], *own) for w in words):
                    continue
                score = ds.score(words, *own, title, labels.get(name, ''))
                if score:
                    hits.append(
                        {
                            'section': 'Settings',
                            'kind': 'setting',
                            'label': field,
                            'hint': f'{title} settings',
                            'url': f'{url}#f-{name}-{key}',
                            'icon': 'sliders-horizontal',
                            'score': score,
                        }
                    )
    except Exception:  # noqa: BLE001
        logger.warning('palette: settings entries failed', exc_info=True)
    return hits


def _email_hits(words: list[str]) -> list[dict]:
    """Every email the store sends, to its editor (the list while the CMS app,
    which keeps the edits, is off)."""
    from plugins.registry import app_registry  # noqa: PLC0415

    from .settings import _email_template_defs  # noqa: PLC0415

    hits: list[dict] = []
    try:
        editable = app_registry.is_active('cms')
        for key, label, subject, group in _email_template_defs():
            score = ds.score(words, label, subject, group, 'email')
            if not score:
                continue
            hits.append(
                {
                    'section': 'Emails',
                    'kind': 'email',
                    'label': label,
                    'hint': f'{group} · {subject}',
                    'url': (
                        f'/dashboard/settings/email-templates/{key}/'
                        if editable
                        else '/dashboard/settings/email-templates/'
                    ),
                    'icon': 'mail',
                    'capability': 'system.write' if editable else 'system.read',
                    'score': score,
                }
            )
    except Exception:  # noqa: BLE001
        logger.warning('palette: email entries failed', exc_info=True)
    return hits


def _record_hits(query: str, words: list[str], user) -> list[dict]:
    """What every app owns: DASHBOARD_SEARCH. A hit must open a dashboard page."""
    from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415

    answered = hook_registry.filter(
        MorpheusEvents.DASHBOARD_SEARCH, value=[], query=query, words=words, user=user
    )
    return [
        h
        for h in answered or []
        if isinstance(h, dict)
        and str(h.get('url') or '').startswith('/')
        and not str(h.get('url')).startswith('//')
        and h.get('label')
    ]


def _allowed(user, h: dict, enforcing: bool) -> bool:
    """A hit the person may open. Pages deny only while roles are enforced (rbac's
    ``enforcement_mode``), so the search hides only then."""
    cap = h.get('capability') or ''
    return not (enforcing and cap) or has_capability(user, cap)


def _rank(hits: list[dict]) -> list[dict]:
    """Group into sections, best section first; each section best hit first, one
    hit per address."""
    seen: set[str] = set()
    groups: dict[str, list[dict]] = {}
    for h in sorted(hits, key=lambda h: (-int(h.get('score') or 0), str(h['label']).casefold())):
        if h['url'] in seen:
            continue
        seen.add(h['url'])
        groups.setdefault(h['section'], []).append(h)

    def tie(section: str) -> int:
        if section in _FIRST:
            return _FIRST.index(section)
        return len(_FIRST) + 1 + _LAST.index(section) if section in _LAST else len(_FIRST)

    order = sorted(groups, key=lambda s: (-int(groups[s][0].get('score') or 0), tie(s), s))
    out: list[dict] = []
    for section in order:
        for h in groups[section][: _CAP.get(section, _PER_SECTION)]:
            out.append({k: h[k] for k in ('section', 'kind', 'label', 'hint', 'url', 'icon')})
    return out[:_TOTAL]


@staff_member_required
@require_capability('system.read')
def palette_search(request: HttpRequest) -> HttpResponse:
    """JSON endpoint backing the Cmd+K palette. See module docstring."""
    from django.http import JsonResponse  # noqa: PLC0415

    q = (request.GET.get('q') or '').strip()[:200]
    user = getattr(request, 'user', None)
    words = ds.words(q)
    labels = _app_labels()

    if not words:  # the menu's first places, in its own order
        seen: set[str] = set()
        start = []
        for h in _nav_hits([], user, labels):
            if h['url'] not in seen:
                seen.add(h['url'])
                start.append({k: v for k, v in h.items() if k != 'score'})
        return JsonResponse({'hits': start[:_EMPTY_QUERY]})

    hits = (
        _nav_hits(words, user, labels)
        + _app_hits(words, user)
        + _setting_hits(words, labels)
        + _email_hits(words)
    )
    if len(q) >= _MIN_RECORD_QUERY:
        hits += _record_hits(q, words, user)
    enforcing = enforcement_mode() == MODE_ENFORCE
    hits = _rank([h for h in hits if _allowed(user, h, enforcing)])
    # Always offer a storefront search escape hatch for the raw query.
    hits.append(
        {
            'section': 'Storefront',
            'kind': 'shop',
            'label': f'Search the shop for “{q}”',
            'hint': 'Open the storefront search',
            'url': f'/products/?q={quote(q)}',
            'icon': 'store',
        }
    )
    return JsonResponse({'hits': hits})
