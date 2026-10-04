import logging

from morpheus.app import Plugin, SettingsPanel

logger = logging.getLogger('morpheus.ai_content')


class AIContentPlugin(Plugin):
    name = 'ai_content'
    label = 'AI Content & Assets Studio'
    version = '1.1.0'
    description = (
        'Carries the store-wide brand-voice config (tone, audience, '
        'guidelines) that every AI generation in the platform reads '
        'from via `services.get_brand_voice()`. The canonical product-'
        'description auto-generation path lives in the ai_assistant '
        "plugin's PRODUCT_CREATED hook (`generate_product_description` "
        'Celery task).'
    )
    has_models = False
    requires = ['catalog', 'ai_assistant']

    def ready(self) -> None:
        from morpheus.core import events  # noqa: PLC0415

        # Prepend the brand voice to every agent/Linda system prompt. Core
        # fires AGENT_SYSTEM_PROMPT as the last assembly step; while this
        # plugin is disabled the bus skips the handler and the plain prompt
        # flows through (the ADR 0017 inversion of the old core→plugin import).
        self.register_hook(events.AGENT_SYSTEM_PROMPT, self.on_agent_system_prompt, priority=50)

    def on_agent_system_prompt(self, value, **kwargs):
        """AGENT_SYSTEM_PROMPT filter — return the prompt with brand voice first."""
        from plugins.installed.ai_content.services import with_brand_voice  # noqa: PLC0415

        return with_brand_voice(value if isinstance(value, str) else '')

    def get_config_schema(self):
        """
        Settings rendered into `/dashboard/settings/ai/` (category=ai).

        The brand-voice fields (`brand_name`, `brand_audience`,
        `brand_tone`, `brand_voice_guidelines`) feed every AI
        generation in the platform via `services.get_brand_voice()`,
        so a single store-wide style edit propagates everywhere
        — product descriptions, email rewrites, SEO drafts.
        """
        return {
            'type': 'object',
            'properties': {
                # ── Brand voice — the merchant's style preserved across all AI
                # generation in the platform.
                'brand_name': {
                    'type': 'string',
                    'default': '',
                    'title': 'Brand name',
                    'description': 'How AI-written copy should refer to your store. Leave blank to fall back to the platform store name.',
                },
                'brand_audience': {
                    'type': 'string',
                    'default': '',
                    'title': 'Target audience',
                    'description': "One short line — e.g. 'Independent bookstore shoppers, mid-30s, design-conscious'.",
                },
                'brand_tone': {
                    'type': 'string',
                    'default': 'professional, warm, concrete',
                    'title': 'Tone keywords',
                    'description': "Comma-separated adjectives the AI should hit. e.g. 'playful, irreverent, technical'.",
                },
                'brand_voice_guidelines': {
                    'type': 'string',
                    'default': '',
                    'title': 'Voice guidelines',
                    'description': 'Free-form rules: words to avoid, signature phrases, sentence length, formality. Prepended to every AI prompt as a system message.',
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Brand voice & AI content',
            description=(
                'Store-wide brand voice that every AI generation in the '
                'platform reads from — product descriptions, email '
                'rewrites, SEO drafts. Edit once, propagate everywhere.'
            ),
            schema=self.get_config_schema(),
            category='ai',
        )
