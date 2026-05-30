"""Image variant generation pipeline.

When a ProductImage is saved, this module resizes + re-encodes the
source into the variant stored on ``ProductImage.webp_image`` (despite
the field name, the variant can be WebP / AVIF / JPG depending on the
store's image defaults).

Defaults come from the catalog plugin's settings panel
(Settings → General → Image defaults, see
``plugins.installed.catalog.plugin.CatalogPlugin.get_config_schema``).
Falls back to sane hardcoded values when the panel hasn't been
configured yet.

Phase 4 of docs/plans/product-slider.md.
"""

from __future__ import annotations

import logging
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import features as _pil_features

logger = logging.getLogger('morpheus.catalog.image_pipeline')


# Sane fallbacks — match the schema defaults in CatalogPlugin.
_DEFAULTS = {
    'default_image_format': 'webp',
    'pdp_image_width': 800,
    'pdp_image_height': 1200,
    'enable_avif_variant': True,
}


def _pillow_supports_avif() -> bool:
    """True iff this Pillow build can encode AVIF.

    AVIF support requires Pillow >= 11 plus a build linked against
    libavif. Older / minimal builds raise at save() time, which would
    poison the variant-gen for the entire image. Cheap one-shot check
    so callers can downgrade to WebP transparently.
    """
    try:
        return bool(_pil_features.check('avif'))
    except Exception:  # noqa: BLE001
        return False


def _settings() -> dict:
    """Pull the catalog plugin's image defaults from PluginConfig.

    Returns the schema defaults when the panel hasn't been configured
    yet or the registry isn't ready (early boot / tests). Never raises.
    """
    out = dict(_DEFAULTS)
    try:
        from plugins.registry import plugin_registry  # noqa: PLC0415

        # Both `.get` and `.get_plugin` show up in different builds —
        # try both. (Same pattern as ai_assistant/services/config.py.)
        plugin = None
        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    plugin = fn('catalog')
                except Exception:  # noqa: BLE001, S112
                    continue
                if plugin is not None:
                    break
        if plugin is None:
            return out
        try:
            cfg = plugin.get_config() or {}
        except Exception:  # noqa: BLE001
            return out
        # Pull recognised keys, skip empty values so defaults survive.
        for key in (
            'default_image_format',
            'pdp_image_width',
            'pdp_image_height',
            'enable_avif_variant',
        ):
            v = cfg.get(key)
            if v not in (None, ''):
                out[key] = v
    except Exception:  # noqa: BLE001, S110
        pass
    # Coerce numeric fields and clamp to sane ranges.
    try:
        out['pdp_image_width'] = max(200, min(int(out['pdp_image_width']), 2400))
        out['pdp_image_height'] = max(200, min(int(out['pdp_image_height']), 3600))
    except (TypeError, ValueError):
        out['pdp_image_width'] = _DEFAULTS['pdp_image_width']
        out['pdp_image_height'] = _DEFAULTS['pdp_image_height']
    fmt = str(out['default_image_format'] or 'webp').lower()
    if fmt not in {'webp', 'avif', 'jpg', 'jpeg'}:
        fmt = 'webp'
    if fmt == 'jpeg':
        fmt = 'jpg'
    out['default_image_format'] = fmt
    _downgrade_avif_if_unsupported(out)
    return out


def _downgrade_avif_if_unsupported(out: dict) -> None:
    """AVIF needs a Pillow build linked against libavif. Fall back to WebP
    silently so an under-built image doesn't 500 the upload pipeline.
    Mutates `out` in place.
    """
    if _pillow_supports_avif():
        return
    if out.get('default_image_format') == 'avif':
        out['default_image_format'] = 'webp'
    out['enable_avif_variant'] = False


def _ext_for(fmt: str) -> str:
    return {'webp': 'webp', 'avif': 'avif', 'jpg': 'jpg'}.get(fmt, 'webp')


def _pil_format(fmt: str) -> str:
    return {'webp': 'WEBP', 'avif': 'AVIF', 'jpg': 'JPEG'}.get(fmt, 'WEBP')


def generate_pdp_variant(product_image) -> None:
    """Resize + re-encode `product_image.image` and store it on
    `product_image.webp_image`. Saves the parent model with
    `update_fields=['webp_image']` so the call is cheap.

    Raises on PIL / IO failure — callers wrap in try/except so a bad
    upload doesn't block the user-facing save.
    """
    from PIL import Image as PILImage  # noqa: PLC0415

    settings_ = _settings()
    fmt = settings_['default_image_format']
    target_w = settings_['pdp_image_width']
    target_h = settings_['pdp_image_height']

    src_field = product_image.image
    if not src_field:
        return

    src_field.open('rb')
    try:
        pil = PILImage.open(src_field)
        pil.load()
    finally:
        src_field.close()

    # Normalise unusual modes (palette + CMYK don't survive WebP/AVIF;
    # RGBA does for WebP/AVIF but not for JPEG).
    if pil.mode in ('P', 'CMYK'):
        pil = pil.convert('RGB')
    elif pil.mode == 'RGBA' and fmt == 'jpg':
        # JPEG has no alpha — flatten on white.
        flat = PILImage.new('RGB', pil.size, (255, 255, 255))
        flat.paste(pil, mask=pil.split()[-1])
        pil = flat

    # Resize using a max-fit so we never UPscale a small original.
    # Pillow's `thumbnail()` is in-place and preserves aspect ratio.
    if pil.width > target_w or pil.height > target_h:
        pil.thumbnail((target_w, target_h), PILImage.LANCZOS)

    buf = BytesIO()
    save_kwargs: dict = {'format': _pil_format(fmt)}
    if fmt == 'webp':
        save_kwargs['quality'] = 82
        save_kwargs['method'] = 4
    elif fmt == 'avif':
        save_kwargs['quality'] = 60  # AVIF compresses better at lower quality
    elif fmt == 'jpg':
        save_kwargs['quality'] = 85
        save_kwargs['optimize'] = True
        save_kwargs['progressive'] = True
    pil.save(buf, **save_kwargs)
    buf.seek(0)

    base = (src_field.name or '').rsplit('/', 1)[-1].rsplit('.', 1)[0] or 'image'
    out_name = f'{base}.{_ext_for(fmt)}'
    product_image.webp_image.save(out_name, ContentFile(buf.read()), save=False)
    # `update_fields` keeps this write surgical — won't re-fire the
    # outer ProductImage.save() variant-gen branch (it short-circuits
    # when webp_image already matches the expected filename).
    product_image.__class__.objects.filter(pk=product_image.pk).update(
        webp_image=product_image.webp_image.name,
    )
    logger.info(
        'pdp variant: pk=%s fmt=%s %dx%d → %dx%d',
        product_image.pk,
        fmt,
        pil.width,
        pil.height,
        target_w,
        target_h,
    )
