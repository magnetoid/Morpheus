"""Immersive PDP — the page every other vibe-coding surface lands on.

Pieces contributed (via `StorefrontBlock(slot=…)`):

  * `pdp_above_price`    — video hero (YouTube/Vimeo/RAW MP4) with a
    `prefers-reduced-motion` aware poster fallback.
  * `pdp_below_gallery`  — 3D/AR preview slot (consumed by the
    `media_3d` plugin if enabled; otherwise a graceful "tap to enlarge"
    fallback).
  * `pdp_above_long_description` — scroll-snap story blocks (the
    "tap-to-see-why" pattern from Allbirds/Gymshark), each a small
    CMS block the merchant authors from the journal.
  * `pdp_below_form`     — sticky "buy box" with on-page variant picker
    and a one-tap add-to-cart that posts to the existing
    `mutateAddToCart` GraphQL.

No models — pure delivery + UX. Disable it and the existing PDP
template reverts to its baseline render.
"""
from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock


class ImmersivePdpPlugin(Plugin):
    name = 'immersive_pdp'
    label = 'Immersive PDP'
    version = '1.0.0'
    description = (
        'Video hero, 3D/AR preview slot, scroll-snap story blocks, sticky '
        'buy box. Consumes the same catalog + cart + reviews data the '
        'storefront already renders — wraps it in a vibe-coded layout.'
    )
    has_models = False
    requires = ['catalog', 'orders', 'product_videos']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_above_price',
                template='immersive_pdp/blocks/video_hero.html',
                priority=5,
                context_keys=['product'],
            ),
            StorefrontBlock(
                slot='pdp_below_gallery',
                template='immersive_pdp/blocks/story_rail.html',
                priority=20,
                context_keys=['product'],
            ),
            StorefrontBlock(
                slot='pdp_below_form',
                template='immersive_pdp/blocks/sticky_buybox.html',
                priority=10,
                context_keys=['product', 'variants'],
            ),
            StorefrontBlock(
                slot='global_below_body',
                template='immersive_pdp/blocks/buybox_runtime.html',
                priority=10,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Immersive PDP',
            description='Layout density, motion preferences, story-block count.',
            category='general',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'story_block_count': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 8,
                    'default': 3,
                    'title': 'Scroll-snap story blocks per product',
                },
                'sticky_buybox': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Sticky buy box (mobile + desktop)',
                },
                'reduced_motion_default': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Default to reduced motion (server-side hint; client prefers-reduced-motion always wins)',
                },
            },
        }
