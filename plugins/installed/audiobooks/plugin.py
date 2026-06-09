"""Audiobooks plugin manifest.

Adds an audiobook EDITION to a book as a real, purchasable digital
``catalog.ProductVariant``, attaches the narration audio + a modal player to it,
and (next step) generates the narration with ElevenLabs. Requires book_product;
disable it and the player + generation + settings vanish while the variant stays
a plain digital edition. See docs/plans/audiobooks-2026-06.md.
"""

from __future__ import annotations

from morpheus import Plugin, SettingsPanel


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
        # Storefront PDP player block + the admin "Audiobook edition" field are
        # wired in the next phases (docs/plans/audiobooks-2026-06.md).
        pass

    def contribute_settings_panel(self) -> SettingsPanel:
        # Settings → Product Types → Audiobooks. The ElevenLabs key is a secret;
        # the settings surface redacts it. Disabling the plugin removes the panel.
        return SettingsPanel(
            label='Audiobooks',
            description='ElevenLabs narration + audiobook-edition defaults.',
            schema=self.get_config_schema(),
            category='product_types',
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
