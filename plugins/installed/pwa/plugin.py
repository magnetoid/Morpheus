"""Progressive Web App plugin.

Owns the whole PWA surface so the storefront is installable + works
offline:

  * /manifest.webmanifest  — Web App Manifest (name, icons, colors).
  * /sw.js                 — service worker (cache-first static,
                             network-first pages, offline fallback).
  * /offline/              — branded offline fallback page.
  * a storefront block that registers the service worker + links the
    manifest into <head> on every storefront page.

Replaces the seo plugin's old /manifest.json (which had no service
worker — so it was never actually installable — and pointed at icon
files that 404'd). Reads the store name + theme color from
core.StoreSettings, never from another plugin's models.
"""

from __future__ import annotations

import logging

from morpheus import Plugin, SettingsPanel, StorefrontBlock

logger = logging.getLogger('morpheus.pwa')


class PwaPlugin(Plugin):
    name = 'pwa'
    label = 'Progressive Web App'
    version = '0.1.0'
    description = (
        'Makes the storefront installable + offline-capable: web app '
        'manifest, service worker (cache-first assets, offline page), '
        'and app icons. No models — purely a delivery + caching layer.'
    )
    has_models = False

    def ready(self) -> None:
        # Root-mounted: the service worker MUST live at /sw.js so its
        # scope covers the whole origin; the manifest + offline page
        # sit at root too.
        self.register_urls(
            'plugins.installed.pwa.urls',
            prefix='',
            namespace='pwa',
        )

    def contribute_storefront_blocks(self) -> list:
        # Injected near </body> on every storefront page: links the
        # manifest, sets apple-touch-icon, and registers the service
        # worker. Kept in a block (not a theme edit) so it travels with
        # the plugin per the storefront-integration contract.
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='pwa/blocks/register.html',
                priority=20,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Progressive Web App',
            description=(
                'Installability + offline behaviour. Theme color + name '
                'come from Settings → General; toggles below tune the '
                'service worker.'
            ),
            schema=self.get_config_schema(),
            category='developer',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enabled': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Enable service worker',
                    'description': 'Master switch. Off = manifest still served (installable) but no offline caching / SW registration.',
                },
                'offline_enabled': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Offline fallback page',
                    'description': 'Serve /offline/ when a navigation request fails with no cached copy.',
                },
                'theme_color': {
                    'type': 'string',
                    'default': '#f6f1e7',
                    'title': 'Theme color',
                    'description': 'Browser UI tint when installed. Defaults to the warm-paper storefront background.',
                },
            },
        }
