"""Audiobooks plugin manifest.

Adds an audiobook EDITION to a book as a real, purchasable digital
``catalog.ProductVariant``, attaches the narration audio + a modal player to it,
and generates the narration with ElevenLabs. Requires book_product;
disable it and the player + generation + settings vanish while the variant stays
a plain digital edition. See docs/plans/audiobooks-2026-06.md.
"""

# Hook handlers use lazy imports (load-order-safe; the established plugin pattern).
# ruff: noqa: PLC0415
from __future__ import annotations

from morpheus import Plugin, SettingsPanel, StorefrontBlock, events


class AudiobooksPlugin(Plugin):
    name = 'audiobooks'
    label = 'Audiobooks'
    version = '0.1.0'
    description = (
        'Audiobook editions for books — a priced digital variant with a modal '
        'player on the product page, plus ElevenLabs narration. Requires '
        'book_product.'
    )
    requires = ['book_product']
    has_models = True

    def ready(self) -> None:
        # Contribute the "Audiobook edition" card into the dashboard product form
        # (modular extension point) and persist it on save. Only book products
        # show the card.
        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=50)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=50)
        # ElevenLabs narration: the dashboard "Generate" button enqueues a task.
        self.register_urls(
            'plugins.installed.audiobooks.urls',
            prefix='dashboard/audiobooks/',
            namespace='audiobooks',
        )
        self.register_celery_tasks('plugins.installed.audiobooks.tasks')

    def on_product_form_cards(self, value, product=None, **kwargs):
        """Contribute the 'Audiobook edition' card for book products."""
        if product is None or not getattr(product, 'book', None):
            return value
        ab = None
        try:
            from plugins.installed.audiobooks.models import Audiobook

            ab = Audiobook.for_product(product)
        except Exception:  # noqa: BLE001
            ab = None
        value.append(
            {
                'template': 'audiobooks/blocks/product_form_card.html',
                'context': {'audiobook': ab},
                'order': 45,
            }
        )
        return value

    def on_product_form_saved(self, product=None, post=None, files=None, **kwargs):
        """Create/update the audiobook EDITION (a digital variant) + its audio."""
        if product is None or post is None or post.get('audiobook_enabled') != '1':
            return
        if not getattr(product, 'book', None):
            return
        try:
            from decimal import Decimal

            from djmoney.money import Money

            from plugins.installed.audiobooks.services import get_or_create_audiobook_edition

            fallback_sku = f'{product.sku or product.id}-AUDIO'
            ab = get_or_create_audiobook_edition(
                product, sku=(post.get('audiobook_sku') or fallback_sku)
            )
            variant = ab.variant

            price = (post.get('audiobook_price') or '').strip()
            if price:
                currency = str(product.price.currency) if product.price else 'USD'
                variant.price = Money(Decimal(price), currency)
                variant.save(update_fields=['price'])

            ab.narrator = (post.get('audiobook_narrator') or '')[:200]
            files = files or {}
            if files.get('audiobook_audio'):
                ab.audio_file = files['audiobook_audio']
                ab.source = 'uploaded'
                ab.status = 'ready'
            if files.get('audiobook_sample'):
                ab.sample_file = files['audiobook_sample']
            if files.get('audiobook_source_pdf'):
                ab.source_pdf = files['audiobook_source_pdf']
            ab.save()
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.audiobooks').warning(
                'audiobook product-form save failed: %s', exc, exc_info=True
            )

    def contribute_storefront_blocks(self) -> list:
        # PDP "Listen to a sample" modal player — self-gates on a ready audiobook
        # (renders nothing otherwise), so it disappears when the plugin is disabled.
        return [
            StorefrontBlock(
                slot='pdp_below_form',
                template='audiobooks/blocks/pdp_player.html',
                priority=30,
                context_keys=['product'],
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        # Settings → Product Types → Audiobooks. The ElevenLabs key is a secret;
        # the settings surface redacts it. Disabling the plugin removes the panel.
        return SettingsPanel(
            label='Audiobooks',
            description='ElevenLabs narration + audiobook-edition defaults.',
            schema=self.get_config_schema(),
            category='general',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'elevenlabs_api_key': {
                    'type': 'string',
                    'default': '',
                    'title': 'ElevenLabs API key',
                    'description': 'Secret key used to generate narration. Stored server-side; redacted from the assistant.',
                },
                'elevenlabs_voice_id': {
                    'type': 'string',
                    'default': '',
                    'title': 'Default voice ID',
                    'description': 'ElevenLabs voice used when generating a new audiobook.',
                },
                'elevenlabs_model': {
                    'type': 'string',
                    'default': 'eleven_multilingual_v2',
                    'title': 'Model',
                },
                'auto_generate': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Auto-generate narration when an audiobook edition is added',
                },
            },
        }
