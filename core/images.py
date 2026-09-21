"""Store-wide image display settings — one answer both shells read.

The shape an image is shown in is a *display* decision, and it was hardcoded
in the wrong places. `catalog/image_pipeline.py` resizes with Pillow's
`thumbnail()`, which preserves the source aspect ratio and never reshapes
anything, so the stored file has whatever proportions the merchant uploaded.
Everything a shopper or a merchant actually sees came from a CSS frame — and
every one of those frames was written `2 / 3`, a book cover, because the first
store on this platform sold books. Six of them in the dashboard alone
(`products.html` at `h-10 w-7`, the media uploader's tile and modal, the cover
slot, the variant modal), plus the theme card frames.

So a store selling soap, tours or wine displayed square photographs inside
portrait frames, in the merchant's own product list, and no setting could
change it: the panel's `grid_image_*` and `og_image_*` keys had **zero**
consumers anywhere in the tree.

This module is the single resolver. It lives in core because both shells need
it and neither may import the other's plugin; it reads the catalog plugin's
config by name, the same inversion `core/agents/guardrails.py` uses for
agent_core. Fail-soft in every direction: an unconfigured, unmigrated or
half-broken store gets the defaults rather than a broken page.
"""

from __future__ import annotations

# (css aspect-ratio, human label). `original` means "impose no frame" — the
# image keeps the proportions it was uploaded with.
ASPECT_RATIOS: dict[str, tuple[str, str]] = {
    'square': ('1 / 1', 'Square (1:1)'),
    'portrait': ('2 / 3', 'Portrait (2:3)'),
    'tall': ('3 / 4', 'Tall (3:4)'),
    'landscape': ('3 / 2', 'Landscape (3:2)'),
    'wide': ('16 / 9', 'Wide (16:9)'),
    'original': ('auto', "Original (don't crop the frame)"),
}

FIT_MODES = {
    'cover': 'Fill the frame (crops the edges)',
    'contain': 'Fit inside the frame (shows the whole image)',
}

# Square, not portrait. A general commerce platform's neutral default; the book
# vertical is a plugin and sets `portrait` for itself.
DEFAULT_ASPECT_RATIO = 'square'
DEFAULT_FIT = 'cover'
DEFAULT_QUALITY = 82
MIN_QUALITY = 40
MAX_QUALITY = 100


def _config(key: str, default):
    """Read one catalog image setting, cross-process fresh. Never raises.

    Cross-process fresh matters for the same reason it does in
    `core/agents/guardrails.py`: a plugin's `_config_cache` is per-process, so
    a worker or a second gunicorn process would keep serving the old shape
    after a merchant changes it.
    """
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('catalog')
        if plugin is None:
            return default
        plugin.invalidate_config_cache()
        return plugin.get_config_value(key, default)
    except Exception:  # noqa: BLE001 — a config glitch must never break rendering
        return default


def aspect_ratio_key() -> str:
    """The configured ratio key, guaranteed to be one of `ASPECT_RATIOS`."""
    value = str(_config('image_aspect_ratio', DEFAULT_ASPECT_RATIO) or '').strip().lower()
    return value if value in ASPECT_RATIOS else DEFAULT_ASPECT_RATIO


def aspect_ratio_css() -> str:
    """The CSS `aspect-ratio` value, e.g. `'1 / 1'`."""
    return ASPECT_RATIOS[aspect_ratio_key()][0]


def aspect_ratio_float() -> float | None:
    """Width / height, or None for `original` (no imposed ratio)."""
    css = aspect_ratio_css()
    if css == 'auto':
        return None
    w, _, h = css.partition('/')
    try:
        return float(w.strip()) / float(h.strip())
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def fit_mode() -> str:
    """`'cover'` or `'contain'` — how the image sits inside the frame."""
    value = str(_config('image_fit', DEFAULT_FIT) or '').strip().lower()
    return value if value in FIT_MODES else DEFAULT_FIT


def quality() -> int:
    """Encoder quality for generated variants, clamped to a sane band.

    Was hardcoded per format in the pipeline (82 WebP / 60 AVIF / 85 JPEG), so
    a merchant on a slow connection had no way to trade sharpness for bytes.
    """
    try:
        value = int(_config('image_quality', DEFAULT_QUALITY))
    except (TypeError, ValueError):
        return DEFAULT_QUALITY
    return max(MIN_QUALITY, min(value, MAX_QUALITY))


def crop_to_ratio() -> bool:
    """True when generated variants should be CROPPED to the ratio.

    Off by default: cropping is destructive to the variant, and a frame with
    `object-fit: cover` already shows the same result without touching the
    file. Worth turning on when the bytes matter more than the margins.
    """
    return bool(_config('crop_to_aspect_ratio', False))


def _raw_config() -> dict:
    """The stored catalog config dict, or {} — so callers can tell an explicit
    choice from a default. Never raises."""
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('catalog')
        if plugin is None:
            return {}
        plugin.invalidate_config_cache()
        return plugin.get_config() or {}
    except Exception:  # noqa: BLE001
        return {}


def configured_display_settings() -> dict | None:
    """The merchant's EXPLICIT frame choice, or None if they have not made one.

    The distinction is load-bearing. Publishing the default to every surface
    would silently reshape every storefront already running — dot_books sells
    books and its portrait frames are correct. So an unconfigured store keeps
    whatever each surface already does (the dashboard falls back to square,
    which is the fix; a theme falls back to its own CSS, which is no change),
    and the moment a merchant picks a shape it wins everywhere at once.
    """
    cfg = _raw_config()
    if not any(cfg.get(k) for k in ('image_aspect_ratio', 'image_fit')):
        return None
    return display_settings()


def display_settings() -> dict:
    """Everything a template needs, in one read.

    Callers render these as CSS custom properties rather than branching in
    markup, so a frame is `aspect-ratio: var(--img-ratio)` and changing the
    setting restyles every frame at once.
    """
    key = aspect_ratio_key()
    return {
        'key': key,
        'ratio': ASPECT_RATIOS[key][0],
        'label': ASPECT_RATIOS[key][1],
        'fit': fit_mode(),
    }
