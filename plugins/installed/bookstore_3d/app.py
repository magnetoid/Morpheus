"""bookstore_3d — an immersive first-person 3D bookstore walkthrough.

Modular: the page (view + URL + template) and its settings live entirely in
this plugin. The template ``{% extends "storefront/base.html" %}`` so the
walkthrough renders inside the active dot books theme (header, nav, footer) —
a native storefront page at ``/walkthrough/``, with a full-bleed three.js
canvas in the content area. Real catalog books appear on the shelves;
clicking one navigates to its product page.

Three.js loads from a CDN ES-module importmap (unpkg) — fine on the
storefront, whose CSP is report-only and already whitelists unpkg.com
(see core/security_headers.py). No build step.

Disabling the plugin removes the route + the page + the settings panel +
the nav link; deleting the directory (and its line in
MORPHEUS_DEFAULT_APPS) removes every trace.
"""

# ruff: noqa: PLC0415
# Inline imports keep the manifest importable at settings-import time.

from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock


class Bookstore3DPlugin(Plugin):
    name = 'bookstore_3d'
    label = '3D Bookstore'
    version = '0.1.0'
    description = (
        'An immersive first-person 3D bookstore walkthrough on its own storefront '
        'page. Real catalog books line the shelves; click one to open its product '
        'page. Built with three.js (CDN, no build step).'
    )
    has_models = False
    requires = ['storefront', 'catalog']

    def ready(self) -> None:
        # Own the /walkthrough/ storefront route. Only registered while the
        # plugin is active, so disabling it removes the page.
        self.register_urls(
            'plugins.installed.bookstore_3d.urls', prefix='', namespace='bookstore_3d'
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {
                    'type': 'boolean',
                    'title': 'Show the 3D walkthrough',
                    'description': (
                        'When off, /walkthrough/ shows a short "currently closed" '
                        'notice instead of the scene (the plugin itself stays active).'
                    ),
                    'default': True,
                },
                'book_source': {
                    'type': 'string',
                    'title': 'Which books to shelve',
                    'enum': ['featured', 'recent', 'category'],
                    'default': 'featured',
                },
                'source_category': {
                    'type': 'string',
                    'title': 'Category slug (when "Which books" is set to category)',
                    'description': 'e.g. fiction — the slug from /category/<slug>/. Ignored otherwise.',
                    'default': '',
                },
                'max_books': {
                    'type': 'integer',
                    'title': 'Maximum books in the scene',
                    'description': 'Capped at 120 for performance. Default 40.',
                    'default': 40,
                },
                'wall_color': {
                    'type': 'string',
                    'title': 'Wall color (hex)',
                    'default': '#efe7d6',
                },
                'floor_color': {
                    'type': 'string',
                    'title': 'Floor color (hex)',
                    'default': '#6b5436',
                },
                'accent_color': {
                    'type': 'string',
                    'title': 'Accent / shelf color (hex)',
                    'default': '#b08442',
                },
                'ambient_intensity': {
                    'type': 'number',
                    'title': 'Ambient light intensity (0.0–2.0)',
                    'description': 'Higher = brighter, flatter room. 0.6 is a warm default.',
                    'default': 0.6,
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='3D Bookstore',
            description='The /walkthrough/ immersive page — which books to shelve, room colors, lighting.',
            schema=self.get_config_schema(),
            category='storefront',
        )

    def contribute_storefront_blocks(self) -> list:
        # A "3D store" link into the theme's footer slot, so the walkthrough is
        # reachable from the footer. Lives here (not in the theme), so disabling
        # the plugin removes the link too.
        return [
            StorefrontBlock(slot='footer_extra', template='bookstore_3d/blocks/nav_link.html'),
        ]

    def contribute_hardcoded_pages(self) -> list:
        # /walkthrough/ is a code-owned page (view + template); surface it in the
        # CMS Pages list as a locked "managed in code" row.
        return [{'title': '3D bookstore', 'url': '/walkthrough/'}]
