"""Dashboard navigation section registry — the single source of truth for the
admin sidebar's top-level groups (ADR 0012's concrete mechanism).

A ``DashboardPage.section`` value is resolved against this registry:
  - a known canonical key            → that group
  - a known legacy alias             → its canonical group
  - anything else (incl. empty)      → the ``apps`` catch-all

So an unrecognised section can NEVER mint a stray top-level header (the old
behaviour, which produced lonely headers like a bare "b2b"). Adding a new
top-level group is deliberate: edit ``SECTION_REGISTRY`` here + record an ADR —
plugins cannot register a group at runtime (the registry is immutable).

Pure Python — NO Django imports. This module is read while the plugin registry
is assembled, before Django is fully initialised.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavSection:
    key: str  # machine key; DashboardPage.section resolves to one of these
    label: str  # sidebar header text
    icon: str  # Lucide icon name
    order: int  # sort position; lower renders first


# The canonical top-level groups. Shopify-style, plus an AI group (Morpheus is
# AI-first) and the perpetual ``apps`` catch-all. Main-rail groups order < 100;
# settings-rail domains 100-199; ``apps`` always last.
SECTION_REGISTRY: tuple[NavSection, ...] = (
    NavSection('home', 'Home', 'home', 10),
    NavSection('ai', 'AI & agents', 'sparkles', 15),  # defining surface — kept prominent
    NavSection('orders', 'Orders', 'shopping-cart', 20),
    NavSection('products', 'Products', 'package', 30),
    NavSection('customers', 'Customers', 'users', 40),
    NavSection('marketing', 'Marketing', 'megaphone', 50),
    NavSection('content', 'Content', 'book-open', 60),
    NavSection('analytics', 'Analytics', 'bar-chart-3', 70),
    # Settings-rail domains (pages with nav='settings').
    NavSection('settings', 'Settings', 'settings', 100),
    NavSection('shipping', 'Shipping', 'truck', 105),
    NavSection('taxes', 'Taxes', 'percent', 106),
    NavSection('developer', 'Developer tools', 'terminal', 110),
    NavSection('access', 'Access & roles', 'shield', 120),
    NavSection('data', 'Data tools', 'database', 130),
    # Perpetual catch-all — uncategorised / unknown sections land here.
    NavSection('apps', 'Apps', 'grid-3x3', 999),
)

_BY_KEY: dict[str, NavSection] = {s.key: s for s in SECTION_REGISTRY}

# Legacy section keys → canonical group. Lets the ~21 historical sections
# collapse onto the canonical set without editing every plugin's plugin.py
# (the long-tail remap is a mechanical follow-up; aliases keep it safe today).
SECTION_ALIASES: dict[str, str] = {
    'catalog': 'products',
    'sales': 'orders',
    'crm': 'customers',
    'growth': 'marketing',
    'marketplace': 'marketing',
    'cms': 'content',
    'seo': 'content',
    'plugins': 'apps',
}

CATCH_ALL = 'apps'


def resolve_section(key: str | None) -> str:
    """Map any ``DashboardPage.section`` to a canonical registry key.
    Known key → itself; known alias → canonical; everything else → ``apps``.
    Never raises; never returns an unregistered key."""
    k = (key or '').strip()
    if k in _BY_KEY:
        return k
    if k in SECTION_ALIASES:
        return SECTION_ALIASES[k]
    return CATCH_ALL


def section_meta(key: str) -> NavSection:
    """The NavSection for a (resolved) key; falls back to the catch-all."""
    return _BY_KEY.get(key, _BY_KEY[CATCH_ALL])


def ordered_keys() -> list[str]:
    """Canonical keys in render order (ascending ``order``)."""
    return [s.key for s in sorted(SECTION_REGISTRY, key=lambda s: s.order)]
