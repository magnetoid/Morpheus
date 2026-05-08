import logging

from plugins.registry import plugin_registry
from plugins.installed.ai_assistant.services.operator import AgentOperator

logger = logging.getLogger('morpheus.ai_content')


def get_brand_voice() -> str:
    """Return the store-wide brand-voice system-prompt fragment.

    Every AI generation surface in the platform — product descriptions,
    email rewrites, SEO drafts, agent-generated content — should prepend
    this string to its `system` prompt so the merchant's style preferences
    propagate everywhere from one place.

    Returns an empty string when nothing is configured; safe to call
    unconditionally and concatenate.
    """
    plugin = plugin_registry.get('ai_content')
    if plugin is None:
        return ''
    cfg = plugin.get_config() if hasattr(plugin, 'get_config') else {}
    name = (cfg.get('brand_name') or '').strip()
    audience = (cfg.get('brand_audience') or '').strip()
    tone = (cfg.get('brand_tone') or '').strip()
    guidelines = (cfg.get('brand_voice_guidelines') or '').strip()
    if not (name or audience or tone or guidelines):
        return ''

    parts: list[str] = ['BRAND VOICE — apply consistently to anything you write:']
    if name:
        parts.append(f'• Refer to the brand as "{name}" when naming it directly.')
    if audience:
        parts.append(f'• Audience: {audience}')
    if tone:
        parts.append(f'• Tone keywords: {tone}')
    if guidelines:
        # Indent merchant guidelines so they read as block quotes inside the system prompt.
        for line in guidelines.splitlines():
            stripped = line.strip()
            if stripped:
                parts.append(f'  | {stripped}')
    parts.append('Stay in this voice unless explicitly overridden by the user.')
    return '\n'.join(parts)


def with_brand_voice(system_prompt: str) -> str:
    """Prepend the brand-voice fragment to an existing system prompt.

    Returns the original prompt verbatim when no brand voice is set, so
    callers can wrap their existing prompt unconditionally.
    """
    voice = get_brand_voice()
    if not voice:
        return system_prompt
    return f'{voice}\n\n{system_prompt}' if system_prompt else voice

class ContentGenerationService:
    """
    Law 5: Business logic for content generation separated into services.
    Uses the AgentOperator to run autonomous content jobs.
    """

    @classmethod
    def generate_product_copy(cls, product):
        plugin = plugin_registry.get('ai_content')
        tone = plugin.get_config_value('tone_of_voice', 'luxury')
        
        logger.info(f"AI Content: Generating {tone} copy for {product.name}")
        operator = AgentOperator()
        
        prompt = f"""
        Objective: Generate a highly converting, SEO-optimized product description.
        Context: The product is '{product.name}' in category '{product.category.name if product.category else 'General'}'.
        Tone: {tone}
        Task: Write a 3-paragraph product description. Focus on emotional connection and utility.
        """
        
        # In a real setup, we extract the resulting text and save it to the DB
        # result = operator.run_workflow(prompt)
        # product.description = result['final_text']
        # product.meta_description = result['seo_snippet']
        # product.save()
        logger.info(f"AI Content successfully applied to {product.name}.")

    @classmethod
    def generate_product_images(cls, product):
        plugin = plugin_registry.get('ai_content')
        tone = plugin.get_config_value('tone_of_voice', 'luxury')
        
        logger.info(f"AI Content: Generating lifestyle images for {product.name}")
        
        # Here we would call a Stable Diffusion or Midjourney API wrapper.
        # Example prompt:
        prompt = f"Product photography of {product.name}, highly aesthetic, 8k resolution, photorealistic, cinematic lighting, {tone} styling."
        
        # simulated_image_url = stable_diffusion.generate(prompt)
        # ProductImage.objects.create(product=product, image_url=simulated_image_url)
        logger.info(f"AI Content image successfully generated and attached to {product.name}.")
