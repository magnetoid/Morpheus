from morpheus import Plugin
from morpheus import events
import logging

logger = logging.getLogger('morpheus.ai_content')

class AIContentPlugin(Plugin):
    name = "ai_content"
    label = "AI Content & Assets Studio"
    version = "1.0.0"
    description = "Autonomously generates high-converting product descriptions, SEO tags, and even product lifestyle images."
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
        By defining this JSON schema, the Morpheus Admin Dashboard can dynamically
        render a Settings Form for this plugin!
        """
        return {
            "type": "object",
            "properties": {
                "auto_generate_text": {
                    "type": "boolean",
                    "default": True,
                    "title": "Auto-Generate Product Descriptions & SEO"
                },
                "auto_generate_images": {
                    "type": "boolean",
                    "default": False,
                    "title": "Auto-Generate Lifestyle Images (Requires Stable Diffusion API)"
                },
                "tone_of_voice": {
                    "type": "string",
                    "enum": ["professional", "playful", "luxury", "minimalist"],
                    "default": "luxury",
                    "title": "Brand Tone of Voice"
                }
            }
        }
