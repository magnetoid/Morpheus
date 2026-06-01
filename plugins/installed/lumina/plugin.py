"""Lumina — a storefront landing page promoting the Lumina Book Creator.

Modular: the page (view + URL + template) lives entirely in this plugin.
The template ``{% extends "storefront/base.html" %}`` so it renders inside
the active dot books theme (header, nav, footer, fonts, tokens) — a native
storefront page at ``/create/``, not a separate site. Disabling the plugin
removes the route + the page.
"""

# ruff: noqa: PLC0415
# Inline imports keep the manifest importable at settings-import time.

from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock


class LuminaPlugin(Plugin):
    name = 'lumina'
    label = 'Lumina'
    version = '0.1.0'
    description = (
        'Storefront landing page for the Lumina Book Creator — write with AI + voice, '
        'auto-translate to 100 languages, and sell on dot books.'
    )
    has_models = False
    requires = ['storefront']

    def ready(self) -> None:
        # Own the /create/ storefront route. Only registered while the
        # plugin is active, so disabling it removes the page.
        self.register_urls('plugins.installed.lumina.urls', prefix='', namespace='lumina')

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'app_url': {
                    'type': 'string',
                    'title': 'Lumina app URL',
                    'description': "Where the page's CTAs send authors (the Lumina book-creator app).",
                    'default': '',
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Lumina',
            description='The /create/ landing page and where its "Start creating" buttons link.',
            schema=self.get_config_schema(),
            category='marketing',
        )

    def contribute_storefront_blocks(self) -> list:
        # A "Write a book" link into the theme's nav + footer slots, so
        # /create/ is reachable from both. Lives here (not in the theme),
        # so disabling the plugin removes the links too.
        return [
            StorefrontBlock(slot='nav_primary_extra', template='lumina/blocks/nav_link.html'),
            StorefrontBlock(slot='footer_extra', template='lumina/blocks/nav_link.html'),
        ]
