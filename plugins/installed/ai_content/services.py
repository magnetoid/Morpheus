"""Brand-voice helper read by every AI generation surface in the platform.

Auto product-description generation lives in
``plugins.installed.ai_assistant.tasks.generate_product_description``;
the previous ``ContentGenerationService`` here was a stub that logged
"success" without writing to the DB. Deleted in favour of a single
canonical path.
"""
import logging

from plugins.registry import plugin_registry

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

