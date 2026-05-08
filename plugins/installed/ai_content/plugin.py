from morpheus import Plugin, SettingsPanel
from morpheus import events
import logging

logger = logging.getLogger('morpheus.ai_content')

class AIContentPlugin(Plugin):
    name = "ai_content"
    label = "AI Content & Assets Studio"
    version = "1.1.0"
    description = "Autonomously generates high-converting product descriptions, SEO tags, and lifestyle images. Carries the brand voice config that every AI generation in the platform reads from."
    has_models = False
    requires = ["catalog", "ai_assistant"]

    def ready(self):
        # We hook into product creation to autonomously generate content
        self.register_hook(events.PRODUCT_CREATED, self.on_product_created, priority=90)

    def on_product_created(self, product, **kwargs):
        """Trigger background tasks to generate text and images for the new product."""
        if self.get_config_value('auto_generate_text', True):
            from plugins.installed.ai_content.services import ContentGenerationService
            # In a real environment, this should be a Celery task.
            # Using the service directly here for MVP illustration.
            ContentGenerationService.generate_product_copy(product)

        if self.get_config_value('auto_generate_images', False):
            from plugins.installed.ai_content.services import ContentGenerationService
            ContentGenerationService.generate_product_images(product)

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
            "type": "object",
            "properties": {
                # ── Brand voice — the merchant's style preserved across all AI
                # generation in the platform.
                "brand_name": {
                    "type": "string",
                    "default": "",
                    "title": "Brand name",
                    "description": "How AI-written copy should refer to your store. Leave blank to fall back to the platform store name.",
                },
                "brand_audience": {
                    "type": "string",
                    "default": "",
                    "title": "Target audience",
                    "description": "One short line — e.g. 'Independent bookstore shoppers, mid-30s, design-conscious'.",
                },
                "brand_tone": {
                    "type": "string",
                    "default": "professional, warm, concrete",
                    "title": "Tone keywords",
                    "description": "Comma-separated adjectives the AI should hit. e.g. 'playful, irreverent, technical'.",
                },
                "brand_voice_guidelines": {
                    "type": "string",
                    "default": "",
                    "title": "Voice guidelines",
                    "description": "Free-form rules: words to avoid, signature phrases, sentence length, formality. Prepended to every AI prompt as a system message.",
                },
                # ── Auto-generation toggles (Celery-backed) ─────────────
                "auto_generate_text": {
                    "type": "boolean",
                    "default": True,
                    "title": "Auto-generate product descriptions on create",
                },
                "auto_generate_images": {
                    "type": "boolean",
                    "default": False,
                    "title": "Auto-generate lifestyle images (requires image API)",
                },
                # Legacy field — kept for back-compat. New copy uses brand_tone.
                "tone_of_voice": {
                    "type": "string",
                    "enum": ["professional", "playful", "luxury", "minimalist"],
                    "default": "luxury",
                    "title": "Legacy preset tone",
                    "description": "Kept for back-compat with older code paths. Prefer `brand_tone` for new generation.",
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Brand voice & AI content',
            description=(
                "Store-wide brand voice that every AI generation in the "
                "platform reads from — product descriptions, email "
                "rewrites, SEO drafts. Edit once, propagate everywhere."
            ),
            schema=self.get_config_schema(),
            category='ai',
        )
