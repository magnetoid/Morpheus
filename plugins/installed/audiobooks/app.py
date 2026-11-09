"""Audiobooks plugin manifest.

Adds an audiobook EDITION to a book as a real, purchasable digital
``catalog.ProductVariant``, attaches the narration audio + a modal player to it,
and narrates the book's PDF with ElevenLabs, ElevenLabs Studio (ready for
ElevenReader) or Qwen TTS (services.py). Requires book_product;
disable it and the player + generation + settings vanish while the variant stays
a plain digital edition. See docs/plans/audiobooks-2026-06.md.
"""

# Hook handlers use lazy imports (load-order-safe; the established plugin pattern).
# ruff: noqa: PLC0415
from __future__ import annotations

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events


class AudiobooksPlugin(Plugin):
    name = 'audiobooks'
    label = 'Audiobooks'
    version = '0.1.0'
    description = (
        'Audiobook editions for books — a priced digital variant with a modal '
        'player on the product page, narrated from the book PDF with ElevenLabs, '
        'ElevenLabs Studio or Qwen TTS. Requires book_product.'
    )
    requires = ['book_product']
    has_models = True

    def ready(self) -> None:
        # Contribute the "Audiobook edition" card into the dashboard product form
        # (modular extension point) and persist it on save. Only book products
        # show the card.
        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=50)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=50)
        # The buyer of an audiobook edition gets its narration (digital_products'
        # library, order pages and emailed links read this).
        self.register_hook(events.DIGITAL_DELIVERY_FILE, self.on_delivery_file, priority=50)
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
        from plugins.installed.audiobooks.narrators import QWEN_VOICES
        from plugins.installed.audiobooks.services import _config

        cfg = _config()
        value.append(
            {
                'template': 'audiobooks/blocks/product_form_card.html',
                'context': {
                    'audiobook': ab,
                    'store_provider': cfg['provider'],
                    'qwen_voices': QWEN_VOICES,
                },
                'order': 45,
            }
        )
        return value

    def on_delivery_file(self, value, variant=None, **kwargs):
        """An audiobook edition delivers its narration once there is one, and until
        then only a file uploaded on the edition itself (digital_products never hands
        an audiobook edition the book's PDF)."""
        if variant is None or getattr(variant, 'variant_type', '') != 'audiobook':
            return value
        from plugins.installed.audiobooks.models import Audiobook

        audiobook = Audiobook.objects.filter(variant=variant).first()
        if audiobook is not None and audiobook.is_ready:
            return audiobook.audio_file
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
            provider = post.get('audiobook_provider', '')
            if provider in dict(ab.PROVIDER_CHOICES):
                ab.provider = provider
            ab.voice = (post.get('audiobook_voice') or '').strip()[:80]
            files = files or {}
            uploaded = bool(files.get('audiobook_audio'))
            if uploaded:
                ab.audio_file = files['audiobook_audio']
                ab.source = 'uploaded'
                ab.status = 'ready'
            if files.get('audiobook_sample'):
                ab.sample_file = files['audiobook_sample']
            if files.get('audiobook_source_pdf'):
                ab.source_pdf = files['audiobook_source_pdf']
            ab.save()
            if uploaded:
                from plugins.installed.audiobooks.services import announce_ready

                announce_ready(ab)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.audiobooks').warning(
                'audiobook product-form save failed: %s', exc, exc_info=True
            )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.audiobooks.agent_tools import (
            audiobooks_generate_tool,
            audiobooks_status_tool,
        )

        return [audiobooks_status_tool, audiobooks_generate_tool]

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
            description='Narration services and voices for audiobook editions.',
            schema=self.get_config_schema(),
            category='general',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'elevenlabs_api_key': {
                    'type': 'string',
                    'format': 'password',
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
                    'title': 'ElevenLabs model',
                },
                'narration_provider': {
                    'type': 'string',
                    'enum': ['elevenlabs', 'studio', 'qwen'],
                    'default': 'elevenlabs',
                    'title': 'Narration service',
                    'description': (
                        'Used when a book does not pick its own. elevenlabs: ElevenLabs '
                        'text-to-speech. studio: an ElevenLabs Studio project you can publish '
                        'to ElevenReader. qwen: Qwen TTS, with the Qwen key from Settings → AI.'
                    ),
                },
                'qwen_voice': {
                    'type': 'string',
                    'default': 'Jennifer',
                    'title': 'Qwen voice',
                    'description': 'A Qwen TTS voice name, such as Jennifer, Ryan, Cherry or Ethan.',
                },
                'qwen_model': {
                    'type': 'string',
                    'default': 'qwen3-tts-flash',
                    'title': 'Qwen TTS model',
                },
            },
        }
