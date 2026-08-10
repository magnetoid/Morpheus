"""Feed the active design-token set into every storefront render.

The `global_head` token block has always emitted
``--morpheus-color-primary: {{ tokens.colors.primary|default:'#111' }}`` and
friends, but nothing ever put ``tokens`` in the context — the plugin shipped as
models + a template and no render layer, and its own comment said so ("injected
server-side … in a follow-up render layer"). So every palette and typeface a
merchant configured rendered as the hardcoded default on every page. This is
that layer.

Contributed via ``register_context_processor`` rather than being listed in
``settings.TEMPLATES``: the aggregator skips a contributed processor while its
owning plugin is inactive, so the tokens genuinely disappear on disable. The six
processors hard-wired into the settings list do NOT get that (ADR 0023).
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger('morpheus.brand_kit')

#: Token groups the block template reads. Anything else in `tokens_json` is
#: still passed through — a merchant may add their own groups.
_EXPECTED_GROUPS = ('colors', 'fonts', 'spacing', 'radii')


def brand_kit_tokens(request):
    """Return ``{'tokens': {...}, 'brand_kit_settings': {...}}``.

    Fail-soft in every direction — a malformed ``tokens_json``, a missing table
    (mid-migration) or a DB hiccup must never 500 a storefront page. The block
    template's ``|default:`` filters then supply the built-in palette, which is
    exactly the pre-v0.41 behaviour.
    """
    try:
        from plugins.installed.brand_kit.models import DesignTokenSet

        active = DesignTokenSet.objects.filter(is_active=True).first()
        if active is None:
            return {'tokens': {}, 'brand_kit_settings': {}}

        raw = json.loads(active.tokens_json or '{}')
        if not isinstance(raw, dict):
            logger.warning('brand_kit: token set %s is not a JSON object', active.slug)
            return {'tokens': {}, 'brand_kit_settings': {}}

        # Drop non-dict groups so `tokens.colors.primary` can never explode into
        # a template error on a half-authored set.
        tokens = {k: v for k, v in raw.items() if isinstance(v, dict)}
        return {
            'tokens': tokens,
            'brand_kit_settings': {'active_token_set': active.slug, 'name': active.name},
        }
    except Exception:  # noqa: BLE001 — brand styling must never break a page
        logger.debug('brand_kit: token load skipped', exc_info=True)
        return {'tokens': {}, 'brand_kit_settings': {}}
