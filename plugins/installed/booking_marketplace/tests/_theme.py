"""Activate the Montenegro theme for tests that assert on rendered storefront HTML.

booking_marketplace is a per-store vertical and its storefront tests assert on
the Montenegro theme's own markup — Serbian nav labels, place sections, the stay
booking widget. They were written when that theme was the only one in the tree,
so they passed on a bare run and broke the moment the app was folded into a repo
whose default theme is dot_books.

Forcing the theme globally is not an option: `MORPHEUS_ACTIVE_THEME=montenegro`
for the whole suite fails 16 storefront/seo tests that assert on the default
theme. So the classes that need it opt in here.

Both halves are load-bearing. Setting the registry alone is NOT enough: on the
first request of each test `ThemeMiddleware` calls `set_active_from_db()`, which
finds no ThemeConfig row and falls back to `settings.MORPHEUS_ACTIVE_THEME` —
silently putting the default theme back, so the flip only appears to work until
a template is rendered through the client. Overriding the setting alone is not
enough either: a direct `get_template()` render never goes through a request.

The registry is process-global, so the previous *value* is saved and restored —
`set_active()` cannot put the name back to empty, and assuming removal is the
inverse of registration is how a process-global mutation leaks into whatever
runs next (CLAUDE.md).
"""

from __future__ import annotations

from django.test import override_settings

from themes.registry import theme_registry

THEME = 'montenegro'


class MontenegroThemeMixin:
    """Mix in BEFORE the TestCase base: `class T(MontenegroThemeMixin, TestCase)`.

    Cleanup is registered with `addClassCleanup`, not written as `tearDownClass`.
    unittest runs class cleanups even when setUpClass raises part-way and even
    when a tearDown chain breaks; a `tearDownClass` body does not. The first cut
    of this mixin used tearDownClass and leaked BOTH the registry name and the
    overridden setting into every test that ran afterwards in the same process —
    the storefront suite then rendered the Montenegro theme and 11 of its tests
    failed, which is exactly the process-global trap this file exists to avoid.
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        override = override_settings(MORPHEUS_ACTIVE_THEME=THEME)
        override.enable()
        previous = theme_registry._active_name
        theme_registry.set_active(THEME)

        def _restore() -> None:
            theme_registry._active_name = previous
            override.disable()

        cls.addClassCleanup(_restore)
