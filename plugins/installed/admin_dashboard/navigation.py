"""The dashboard's one navigation taxonomy (docs/plans/dashboard-hubs-2026-10.md).

Everything that tells a merchant where they are reads this module: the
sidebar (sections), the tab strip (the pages of the current section), the
settings sidebar (categories), the breadcrumb, the command palette and the
Apps catalogue. A page is filed once, here or in its app's
``DashboardPage(section=…)``, and every surface agrees on where it lives.

Three kinds of entry:

* **Sections** — the main sidebar, a fixed list owned by the shell.
* **Tabs** — the pages of a section: the shell's own (``CORE_TABS``) plus
  every contributed ``DashboardPage`` with ``nav='main'``. Pages sharing a
  ``group`` fold into one tab with sub-tabs. ``nav='hidden'`` pages belong
  to a section (so the sidebar and breadcrumb still know where you are) but
  get no tab — a card or a link leads to them.
* **Settings tools** — ``nav='settings'`` pages and the shell's own platform
  tools, drawn as cards on their settings category page, never as sidebar
  links.

Old ``section``/``category`` keys keep working through the alias tables; an
unknown key is reported by ``manage.py check`` (see ``checks.py``) and the
page is reachable from the Apps catalogue only.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger('morpheus.admin')


# ── Sections (the main sidebar) ─────────────────────────────────────────────


@dataclass(frozen=True)
class NavSection:
    key: str
    label: str
    icon: str
    url: str = ''  # landing page; '' = the section's first tab
    cards: bool = False  # the landing renders this section's DashboardCards
    always: bool = False  # listed even when no app contributes to it
    avatar: str = ''  # static path drawn instead of the icon


SECTIONS: tuple[NavSection, ...] = (
    NavSection('home', 'Home', 'home', '/dashboard/', always=True),
    NavSection(
        'ai',
        'Linda',
        'sparkles',
        '/dashboard/assistant/',
        always=True,
        avatar='assistant/linda-avatar.jpg',
    ),
    NavSection('orders', 'Orders', 'shopping-bag', '/dashboard/orders/', cards=True, always=True),
    NavSection('products', 'Products', 'package', '/dashboard/products/', cards=True, always=True),
    NavSection('customers', 'Customers', 'users', '/dashboard/customers/', cards=True, always=True),
    NavSection('marketing', 'Marketing', 'megaphone', '/dashboard/marketing/', cards=True),
    NavSection('channels', 'Channels', 'radio-tower'),
    NavSection('content', 'Content', 'book-open'),
    NavSection(
        'analytics', 'Analytics', 'bar-chart-3', '/dashboard/analytics/', cards=True, always=True
    ),
    NavSection('seo', 'SEO', 'search'),
    NavSection('vendors', 'Vendors', 'store'),
)

_SECTION_BY_KEY = {s.key: s for s in SECTIONS}

# Keys apps used before the hubs (v0.81.0). Kept so an app written against an
# older Morpheus lands in the right section instead of nowhere.
SECTION_ALIASES = {
    'growth': 'marketing',
    'marketplace': 'vendors',
    'cms': 'content',
    'catalog': 'products',
    'b2b': 'products',
    'crm': 'customers',
    'sales': 'orders',
}


def section(key: str) -> NavSection | None:
    return _SECTION_BY_KEY.get(key)


def main_section_key(raw: str) -> str | None:
    """The sidebar section a ``DashboardPage``/``DashboardCard`` section names,
    or None when it names none (then only the Apps catalogue lists it)."""
    key = SECTION_ALIASES.get(raw or '', raw or '')
    return key if key in _SECTION_BY_KEY else None


def card_section_keys() -> tuple[str, ...]:
    return tuple(s.key for s in SECTIONS if s.cards)


def settings_category_key(raw: str) -> str | None:
    """The settings category a panel or ``nav='settings'`` page names."""
    from plugins.installed.admin_dashboard.settings_categories import (  # noqa: PLC0415
        CATEGORY_ALIASES,
        get_category,
    )

    key = CATEGORY_ALIASES.get(raw or 'apps', raw or 'apps')
    return key if get_category(key) is not None else None


# ── The shell's own pages ───────────────────────────────────────────────────


@dataclass(frozen=True)
class CoreTab:
    """A dashboard page the shell itself serves, filed like an app's page."""

    section: str
    label: str
    url: str
    order: int
    icon: str = 'circle'
    nav: str = 'main'  # 'main' | 'hidden'
    badge: str = ''  # key into the nav badges
    superuser: bool = False


CORE_TABS: tuple[CoreTab, ...] = (
    CoreTab('ai', 'Chat', '/dashboard/assistant/', 10, 'message-circle'),
    CoreTab('ai', 'Insights', '/dashboard/ai-insights/', 60, 'lightbulb', badge='insights'),
    CoreTab(
        'ai', 'Proposals', '/dashboard/assistant/proposals/', 90, 'git-pull-request', superuser=True
    ),
    CoreTab('orders', 'All orders', '/dashboard/orders/', 10, 'shopping-bag'),
    CoreTab('orders', 'Returns', '/dashboard/returns/', 30, 'undo-2', badge='returns'),
    CoreTab('products', 'All products', '/dashboard/products/', 10, 'package'),
    CoreTab('products', 'Categories', '/dashboard/categories/', 20, 'folder-tree'),
    CoreTab('products', 'Collections', '/dashboard/collections/', 30, 'layers'),
    CoreTab('products', 'Tags', '/dashboard/tags/descriptions/', 40, 'tags'),
    CoreTab(
        'products',
        'Content audit',
        '/dashboard/products/content-audit/',
        95,
        'clipboard-check',
        nav='hidden',
    ),
    CoreTab('customers', 'All customers', '/dashboard/customers/', 10, 'users'),
    CoreTab('marketing', 'Overview', '/dashboard/marketing/', 5, 'layout-grid'),
    CoreTab('analytics', 'Overview', '/dashboard/analytics/', 10, 'bar-chart-3'),
)


@dataclass(frozen=True)
class CoreTool:
    """A platform page the shell serves, drawn as a settings tool card."""

    category: str
    label: str
    url: str
    icon: str
    hint: str
    order: int = 100
    unless: str = ''  # an app that, while active, contributes this page itself


CORE_TOOLS: tuple[CoreTool, ...] = (
    CoreTool(
        'notifications',
        'Email templates',
        '/dashboard/settings/email-templates/',
        'mail',
        'Order, refund, welcome and download emails',
        10,
    ),
    CoreTool(
        'developer',
        'Errors',
        '/dashboard/errors/',
        'alert-circle',
        'Server and browser error log',
        80,
    ),
    CoreTool(
        'developer',
        'Version & updates',
        '/dashboard/updates/',
        'git-commit-horizontal',
        'Running version, updates and changelog',
        85,
        unless='release_notes',
    ),
    CoreTool(
        'developer',
        'Caching',
        '/dashboard/settings/caching/',
        'zap',
        'Page cache, Redis and the Cloudflare edge',
        90,
    ),
)

# Settings sub-paths that are pages of a category rather than a category.
_SETTINGS_PATH_CATEGORY = {'email-templates': 'notifications', 'caching': 'developer'}


# ── Entries built per request ───────────────────────────────────────────────


@dataclass
class Tab:
    section: str
    label: str
    url: str
    order: int
    icon: str = 'circle'
    nav: str = 'main'
    plugin: str = ''  # '' = the shell
    slug: str = ''
    group: str = ''
    badge: str = ''
    hint: str = ''


@dataclass
class Tool:
    category: str
    label: str
    url: str
    icon: str
    hint: str
    order: int = 100
    plugin: str = ''
    slug: str = ''


@dataclass
class Location:
    mode: str = ''  # 'main' | 'settings' | ''
    section: str = ''  # a main section key, or a settings category slug
    tab: Tab | None = None
    tool: Tool | None = None
    exact: bool = False  # the path IS the tab's page (not a record below it)
    leftover: list[str] = field(default_factory=list)


def page_url(page) -> str:
    return getattr(page, 'url', '') or f'/dashboard/apps/{page.plugin}/{page.slug}/'


def _is_superuser(user) -> bool:
    return bool(getattr(user, 'is_superuser', False))


def tabs(user=None) -> list[Tab]:
    """Every main-namespace entry: the shell's tabs and every contributed
    page with ``nav`` main or hidden whose section resolves."""
    from plugins.registry import app_registry  # noqa: PLC0415

    out = [
        Tab(t.section, t.label, t.url, t.order, t.icon, t.nav, badge=t.badge)
        for t in CORE_TABS
        if not t.superuser or _is_superuser(user)
    ]
    for page in app_registry.dashboard_pages():
        if page.nav not in ('main', 'hidden'):
            continue
        key = main_section_key(page.section)
        if key is None:
            continue
        out.append(
            Tab(
                key,
                page.label,
                page_url(page),
                page.order,
                page.icon or 'circle',
                page.nav,
                plugin=page.plugin,
                slug=page.slug,
                group=getattr(page, 'group', '') or '',
                hint=getattr(page, 'hint', '') or '',
            )
        )
    out.sort(key=lambda t: (t.order, t.label))
    return out


def tools() -> list[Tool]:
    """Every settings tool card: contributed ``nav='settings'`` pages and the
    shell's platform tools."""
    from plugins.registry import app_registry  # noqa: PLC0415

    out = [
        Tool(t.category, t.label, t.url, t.icon, t.hint, t.order)
        for t in CORE_TOOLS
        if not (t.unless and app_registry.is_active(t.unless))
    ]
    for page in app_registry.dashboard_pages():
        if page.nav != 'settings':
            continue
        key = settings_category_key(page.section) or 'apps'
        out.append(
            Tool(
                key,
                page.label,
                page_url(page),
                page.icon or 'circle',
                getattr(page, 'hint', '') or '',
                page.order,
                plugin=page.plugin,
                slug=page.slug,
            )
        )
    out.sort(key=lambda t: (t.order, t.label))
    return out


# ── Where am I ──────────────────────────────────────────────────────────────


def _mounts() -> list[tuple[str, str]]:
    from plugins.registry import app_registry  # noqa: PLC0415

    return app_registry.dashboard_url_mounts()


def _settings_head(path: str) -> str:
    """``x`` of ``/dashboard/settings/x/…`` or of the legacy
    ``/dashboard/apps/x/settings/`` deep link; '' for any other path."""
    if path.startswith('/dashboard/settings/'):
        return path[len('/dashboard/settings/') :].split('/', 1)[0]
    segs = [s for s in path.split('/') if s]
    if len(segs) == 4 and segs[:2] == ['dashboard', 'apps'] and segs[3] == 'settings':
        return segs[2]
    return ''


def settings_category_for(head: str) -> str:
    """The category ``/dashboard/settings/<head>/`` belongs to: the category
    itself (or the one an old slug is aliased to), the page that lives under
    settings (email templates, caching), or the category of the app whose
    settings form it is. '' when it is none of these."""
    from plugins.installed.admin_dashboard.settings_categories import (  # noqa: PLC0415
        CATEGORY_ALIASES,
        get_category,
    )
    from plugins.registry import app_registry  # noqa: PLC0415

    if head in _SETTINGS_PATH_CATEGORY:
        return _SETTINGS_PATH_CATEGORY[head]
    if get_category(head) is not None:
        return head
    if head in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[head]
    panel = app_registry.settings_panel(head)
    if panel is not None:
        return settings_category_key(panel.category) or 'apps'
    return ''


def _settings_location(path: str, all_tools: list[Tool]) -> Location | None:
    """Settings-mode pages that are not tool pages: the hub, a category, a
    plugin's settings form, the Apps catalogue."""
    if path == '/dashboard/settings/':
        return Location('settings', '', exact=True)
    if path in ('/dashboard/apps/', '/dashboard/apps/store/'):
        return Location('settings', 'apps-catalogue', exact=True)
    head = _settings_head(path)
    if not head:
        return None
    # A tool page served under /dashboard/settings/ (email templates, caching).
    under = [t for t in all_tools if path.startswith(t.url)]
    if under:
        tool = max(under, key=lambda t: len(t.url))
        return Location('settings', tool.category, tool=tool, exact=path == tool.url)
    category = settings_category_for(head)
    return Location('settings', category, exact=path == f'/dashboard/settings/{head}/')


def locate(path: str, all_tabs: list[Tab], all_tools: list[Tool]) -> Location:
    """The entry ``path`` belongs to: the longest tab or tool URL it starts
    with, or failing that the longest app URL mount (``/dashboard/crm/…``
    belongs to the crm app's page whose slug follows the mount, else to its
    first page). Detail pages below a tab therefore resolve to that tab."""
    if not path.startswith('/dashboard/'):
        return Location()
    if path == '/dashboard/':
        return Location('main', 'home', exact=True)
    settings_loc = _settings_location(path, all_tools)
    if settings_loc is not None:
        return settings_loc

    candidates: list[tuple[float, Location]] = [
        (len(url), _entry_location(path, url, entry))
        for entry in [*all_tabs, *all_tools]
        for url in _urls_of(entry)
        if path.startswith(url)
    ]
    for plugin, prefix in _mounts():
        if path.startswith(prefix):
            loc = _mount_location(path, plugin, prefix, all_tabs, all_tools)
            if loc is not None:
                # A mount wins only when it is longer than every page URL, so
                # a page's own URL beats the app prefix it lives under.
                candidates.append((len(prefix) - 0.5, loc))
    if not candidates:
        return Location()
    return max(candidates, key=lambda c: c[0])[1]


def _entry_location(path: str, url: str, entry) -> Location:
    """Where ``path`` is when it lives at or below ``entry``'s ``url``."""
    if isinstance(entry, Tool):
        loc = Location('settings', entry.category, tool=entry, exact=path == url)
    else:
        loc = Location('main', entry.section, tab=entry, exact=path == url)
    loc.leftover = [s for s in path[len(url) :].split('/') if s]
    return loc


def _urls_of(entry) -> tuple[str, ...]:
    """The URLs an entry answers at: its own, and — for an app page whose
    `url` points elsewhere — the router path `/dashboard/apps/<app>/<slug>/`
    that serves it too (old bookmarks, the Apps catalogue's history)."""
    if entry.plugin and entry.slug:
        router = f'/dashboard/apps/{entry.plugin}/{entry.slug}/'
        if router != entry.url:
            return (entry.url, router)
    return (entry.url,)


def _mount_location(path, plugin, prefix, all_tabs, all_tools) -> Location | None:
    """The page of ``plugin`` a path under its URL mount belongs to: the one
    whose slug follows the mount (``/dashboard/marketplace/vendors/<id>/`` →
    Vendors), else the app's first listed page."""
    rest = [s for s in path[len(prefix) :].split('/') if s]
    nxt = rest[0] if rest else ''
    own_tabs = [t for t in all_tabs if t.plugin == plugin]
    own_tools = [t for t in all_tools if t.plugin == plugin]
    tab = next((t for t in own_tabs if t.slug == nxt), None)
    if tab is not None:
        return Location('main', tab.section, tab=tab)
    tool = next((t for t in own_tools if t.slug == nxt), None)
    if tool is not None:
        return Location('settings', tool.category, tool=tool)
    tab = next((t for t in own_tabs if t.nav == 'main'), own_tabs[0] if own_tabs else None)
    if tab is not None:
        return Location('main', tab.section, tab=tab)
    return Location('settings', own_tools[0].category, tool=own_tools[0]) if own_tools else None


# ── What the templates get ──────────────────────────────────────────────────


def _tab_entry(tab: Tab, current: Tab | None, badges: dict) -> dict:
    return {
        'label': tab.label,
        'url': tab.url,
        'icon': tab.icon,
        'active': current is not None and current.url == tab.url,
        'badge': badges.get(tab.badge, 0) if tab.badge else 0,
    }


def tab_strip(section_tabs: list[Tab], current: Tab | None, badges: dict) -> tuple[list, list]:
    """(top-level tabs, sub-tabs of the active group). A group with one live
    member is just that page's tab."""
    groups: dict[str, list[Tab]] = {}
    for tab in section_tabs:
        if tab.group:
            groups.setdefault(tab.group, []).append(tab)
    items: list[dict] = []
    seen_groups: set[str] = set()
    subtabs: list[dict] = []
    for tab in section_tabs:
        members = groups.get(tab.group) if tab.group else None
        if not members or len(members) == 1:
            items.append(_tab_entry(tab, current, badges))
            continue
        if tab.group in seen_groups:
            continue
        seen_groups.add(tab.group)
        children = [_tab_entry(m, current, badges) for m in members]
        active = any(c['active'] for c in children)
        items.append(
            {
                'label': tab.group,
                'url': members[0].url,
                'icon': members[0].icon,
                'active': active,
                'badge': sum(c['badge'] for c in children),
            }
        )
        if active:
            subtabs = children
    return items, subtabs


def _has_cards(section_key: str) -> bool:
    from plugins.registry import app_registry  # noqa: PLC0415

    return any(main_section_key(c.section) == section_key for c in app_registry.dashboard_cards())


def build(request) -> dict:
    """Everything the dashboard shell renders for navigation, once per request."""
    cached = getattr(request, '_morph_nav', None)
    if cached is not None:
        return cached
    user = getattr(request, 'user', None)
    all_tabs = tabs(user)
    all_tools = tools()
    loc = locate(getattr(request, 'path', '') or '', all_tabs, all_tools)
    from plugins.context_processors import _compute_nav_badges  # noqa: PLC0415

    badges = _compute_nav_badges(request)

    sections = []
    for sec in SECTIONS:
        sec_tabs = [t for t in all_tabs if t.section == sec.key]
        listed = [t for t in sec_tabs if t.nav == 'main']
        contributed = any(t.plugin for t in listed) or (sec.cards and _has_cards(sec.key))
        if not (sec.always or contributed):
            continue
        url = sec.url or (listed[0].url if listed else '')
        if not url:
            continue
        badge = sum(badges.get(t.badge, 0) for t in listed if t.badge)
        sections.append(
            {
                'key': sec.key,
                'label': sec.label,
                'icon': sec.icon,
                'avatar': sec.avatar,
                'url': url,
                'active': loc.mode == 'main' and loc.section == sec.key,
                'badge': badge,
            }
        )

    strip, subtabs = [], []
    if loc.mode == 'main':
        listed = [t for t in all_tabs if t.section == loc.section and t.nav == 'main']
        strip, subtabs = tab_strip(listed, loc.tab, badges)
        if len(strip) < 2 and not subtabs:
            strip = []

    nav = {
        'sections': sections,
        'mode': loc.mode,
        'section': loc.section if loc.mode == 'main' else '',
        'section_label': section_label(loc.section) if loc.mode == 'main' else '',
        'category': loc.section if loc.mode == 'settings' else '',
        'tabs': strip,
        'subtabs': subtabs,
        'tab_root': bool(loc.tab and loc.exact),
        'location': loc,
        'badges': badges,
        'categories': settings_categories_nav(loc, all_tools),
        'settings_prefixes': sorted({t.url for t in all_tools}),
    }
    # A request object that refuses attributes just recomputes next time.
    with contextlib.suppress(Exception):
        request._morph_nav = nav
    return nav


def settings_categories_nav(loc: Location, all_tools: list[Tool]) -> list[dict]:
    """The settings sidebar: every category with something in it (General and
    Notifications always — they carry core forms)."""
    from plugins.installed.admin_dashboard.settings_categories import (  # noqa: PLC0415
        SETTINGS_CATEGORIES,
    )
    from plugins.registry import app_registry  # noqa: PLC0415

    counts: dict[str, int] = {}
    for entry in app_registry.all_settings_panels():
        key = settings_category_key(getattr(entry['panel'], 'category', '')) or 'apps'
        counts[key] = counts.get(key, 0) + 1
    for tool in all_tools:
        counts[tool.category] = counts.get(tool.category, 0) + 1
    out = []
    for cat in SETTINGS_CATEGORIES:
        if not counts.get(cat.slug) and cat.slug not in ('general', 'notifications'):
            continue
        out.append(
            {
                'slug': cat.slug,
                'label': cat.label,
                'icon': cat.icon,
                'active': loc.mode == 'settings' and loc.section == cat.slug,
            }
        )
    return out


def section_label(key: str) -> str:
    sec = _SECTION_BY_KEY.get(key)
    return sec.label if sec else key.replace('_', ' ').title()


def page_section_label(page) -> str:
    """Where a contributed page is filed, in words — for the palette and the
    Apps catalogue ("Marketing", "Settings › Developer")."""
    if page.nav == 'settings':
        from plugins.installed.admin_dashboard.settings_categories import (  # noqa: PLC0415
            get_category,
        )

        cat = get_category(settings_category_key(page.section) or 'apps')
        return f'Settings › {cat.label}' if cat else 'Settings'
    key = main_section_key(page.section)
    return section_label(key) if key else 'Apps'


# ── The Apps catalogue speaks the same taxonomy ─────────────────────────────

# Areas, in catalogue order: the sidebar sections, then the settings
# categories that are not sections. An app is filed under the area its first
# surface lands in, so the catalogue groups apps the way the menu does.
CATALOGUE_AREAS: tuple[tuple[str, str], ...] = (
    ('orders', 'Orders'),
    ('products', 'Products'),
    ('customers', 'Customers'),
    ('marketing', 'Marketing'),
    ('channels', 'Sales channels'),
    ('content', 'Content'),
    ('analytics', 'Analytics'),
    ('seo', 'SEO'),
    ('vendors', 'Vendors'),
    ('ai', 'AI'),
    ('payments', 'Payments & checkout'),
    ('shipping', 'Shipping & tax'),
    ('storefront', 'Storefront'),
    ('team', 'Team & security'),
    ('developer', 'Developer'),
    ('data', 'Data'),
    ('general', 'General'),
    ('platform', 'Platform'),
)
_AREA_LABELS = dict(CATALOGUE_AREAS)
# Settings categories that have no area of their own.
_CATEGORY_AREA = {'notifications': 'general', 'apps': 'platform'}


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else f'{n} {many}'


def _contributions(instance) -> dict:
    """What an app adds, asked of the app itself — so an app that is off can
    still say what turning it on would bring. contribute_* methods return
    plain dataclasses; one that raises just reports nothing."""
    out = {'pages': [], 'cards': [], 'blocks': [], 'panel': None}
    for key, method in (
        ('pages', 'contribute_dashboard_pages'),
        ('cards', 'contribute_dashboard_cards'),
        ('blocks', 'contribute_storefront_blocks'),
    ):
        try:
            out[key] = list(getattr(instance, method)() or [])
        except Exception:  # noqa: BLE001 — the catalogue describes, it never breaks
            logger.debug('catalogue: %s.%s failed', instance.name, method, exc_info=True)
    try:
        out['panel'] = instance.contribute_settings_panel()
    except Exception:  # noqa: BLE001
        logger.debug('catalogue: %s.contribute_settings_panel failed', instance.name, exc_info=True)
    return out


def _app_area(c: dict) -> str:
    """The area an app's first surface lands in: a listed page's section, a
    card's section, a settings page's or panel's category, the storefront
    for a blocks-only app, else 'platform'."""
    for page in c['pages']:
        if page.nav in ('main', 'hidden') and main_section_key(page.section):
            key = main_section_key(page.section)
            return 'platform' if key == 'home' else key
    for card in c['cards']:
        if main_section_key(card.section):
            return main_section_key(card.section)
    cats = [settings_category_key(p.section) for p in c['pages'] if p.nav == 'settings']
    if c['panel'] is not None:
        cats.append(settings_category_key(getattr(c['panel'], 'category', '')))
    cat = next((k for k in cats if k), '')
    if cat:
        return _CATEGORY_AREA.get(cat, cat)
    return 'storefront' if c['blocks'] else 'platform'


def _app_adds(c: dict) -> list[str]:
    """Everything an app adds to the dashboard and storefront, in words."""
    from plugins.installed.admin_dashboard.settings_categories import (  # noqa: PLC0415
        get_category,
    )

    by_section: dict[str, int] = {}
    for page in c['pages']:
        key = main_section_key(page.section) if page.nav in ('main', 'hidden') else None
        if key:
            by_section[key] = by_section.get(key, 0) + 1
    adds = [
        f'{_plural(n, "a page", "pages")} in {section_label(key)}' for key, n in by_section.items()
    ]
    adds += [
        f'a card on {section_label(main_section_key(card.section))}'
        for card in c['cards']
        if main_section_key(card.section)
    ]
    cats = {settings_category_key(p.section) or 'apps' for p in c['pages'] if p.nav == 'settings'}
    if c['panel'] is not None:
        cats.add(settings_category_key(getattr(c['panel'], 'category', '')) or 'apps')
    for cat_key in sorted(cats):
        cat = get_category(cat_key)
        adds.append(f'settings in {cat.label if cat else "Settings"}')
    if c['blocks']:
        adds.append(_plural(len(c['blocks']), 'a storefront block', 'storefront blocks'))
    return adds


def describe_app(instance) -> dict:
    """``{'area', 'area_label', 'adds'}`` for the Apps catalogue: where the app
    lives in the dashboard and, in words, everything it adds there."""
    c = _contributions(instance)
    area = _app_area(c)
    return {'area': area, 'area_label': _AREA_LABELS.get(area, area.title()), 'adds': _app_adds(c)}
