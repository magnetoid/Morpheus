"""Seed the storefront navigation menus (header + mobile) to match the theme's
built-in default nav, so merchants start from the live layout and can edit it in
the dashboard (CMS → Menus).

Idempotent: creates each Menu if missing and only populates items when the menu
is empty — re-running never clobbers merchant edits.
"""

from __future__ import annotations

import contextlib

from django.core.cache import cache
from django.core.management.base import BaseCommand

from plugins.installed.cms.models import Menu, MenuItem

_HEADER = [
    ('All books', '/products/', MenuItem.KIND_LINK),
    ('Genres', '/categories/', MenuItem.KIND_MEGA_CATEGORIES),
    ('Authors', '/products/', MenuItem.KIND_MEGA_AUTHORS),
    ('Staff picks', '/staff-picks/', MenuItem.KIND_LINK),
    ('Journal', '/journal/', MenuItem.KIND_LINK),
]
_MOBILE = [
    ('All books', '/products/', MenuItem.KIND_LINK),
    ('New & notable', '/products/?featured=true', MenuItem.KIND_LINK),
    ('Genres', '/categories/', MenuItem.KIND_MEGA_CATEGORIES),
    ('Staff picks', '/staff-picks/', MenuItem.KIND_LINK),
    ('Journal', '/journal/', MenuItem.KIND_LINK),
]


class Command(BaseCommand):
    help = 'Create the header + mobile navigation menus (idempotent).'

    def _seed(self, key, label, items):
        menu, created = Menu.objects.get_or_create(key=key, defaults={'label': label})
        if menu.items.exists():
            self.stdout.write(f'  {key}: {menu.items.count()} item(s) already — left untouched.')
            return
        for i, (lbl, url, kind) in enumerate(items, start=1):
            MenuItem.objects.create(menu=menu, label=lbl, url=url, kind=kind, order=i * 10)
        verb = 'created' if created else 'populated'
        self.stdout.write(self.style.SUCCESS(f'  {key}: {verb} with {len(items)} item(s).'))

    def handle(self, *args, **options):
        self._seed('header', 'Header navigation', _HEADER)
        self._seed('mobile', 'Mobile navigation', _MOBILE)
        # Bust the storefront nav cache so the new menus show immediately.
        with contextlib.suppress(Exception):
            cache.delete_many(['storefront:nav_menu:header:v1', 'storefront:nav_menu:mobile:v1'])
        self.stdout.write(self.style.SUCCESS('Navigation menus seeded.'))
