"""
Morpheus — MorpheusTheme base class.

Every theme in `themes/library/<name>/` subclasses `MorpheusTheme`. The base
class:

* Validates required metadata at subclass time (`name`, `version`, `label`).
* Exposes a single, well-documented surface: a config schema and a
  design-tokens schema.
* Owns the convention for `templates/` and `static/` lookup so theme
  authors can't accidentally diverge.

For a developer guide see `docs/THEME_DEVELOPMENT.md`.
For step-by-step skills see `SKILLS.md` (theming section).
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger('morpheus.themes')

_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')
_VERSION_RE = re.compile(r'^\d+(\.\d+)*([a-z][0-9]*)?$')


class ThemeConfigurationError(TypeError):
    """Raised when a theme's metadata is invalid at class-definition time."""


class MorpheusTheme:
    """
    Base class for all Morph themes.

    A minimal theme looks like::

        from themes.base import MorpheusTheme

        class DotBooksTheme(MorpheusTheme):
            name = "dot_books"
            label = "dot books"
            version = "1.0.0"
            description = "Editorial bookstore theme."
            preview_image = "preview.png"     # under <theme>/static/<name>/
            supports_plugins = ["storefront", "catalog", "orders"]

            def get_design_tokens(self) -> dict:
                return {
                    "colors": {"paper": "#f6f1e7", "ink": "#0e0e0e"},
                    "fonts":  {"display": "Fraunces", "body": "Inter"},
                    "radii":  {"sm": "4px", "md": "8px"},
                }

    Lifecycle
    ---------
    1. `theme_registry.discover(MORPHEUS_THEMES_DIR)` imports
       `themes.library.<name>.theme` and instantiates each subclass.
    2. `set_active(MORPHEUS_ACTIVE_THEME)` selects which theme is live.
    3. The `ThemeLoader` resolves Django templates from the active theme's
       `templates/` directory FIRST, then falls back to plugin templates.

    Conventions
    -----------
    * **Templates** override storefront/dashboard/admin templates by name.
      Drop a file at `themes/library/<name>/templates/storefront/<page>.html`
      to override the storefront plugin's page.
    * **Static** files live under `themes/library/<name>/static/<name>/`.
    * **Preview** image: place at `static/<name>/preview.png` (1280×720).
    * **Design tokens** are a flat tree of category → key/value pairs.
      The dashboard renders a live editor for each declared token.
    """

    # ── Required metadata ──────────────────────────────────────────────────────
    name: str = ''  # snake_case — must equal directory name
    label: str = ''  # human-readable
    version: str = '1.0.0'  # PEP 440-style
    description: str = ''
    author: str = 'Morph Team'
    url: str = ''  # homepage / docs

    # ── Capabilities ──────────────────────────────────────────────────────────
    preview_image: str = ''  # relative path inside static/<name>/
    supports_plugins: list[str] = []  # plugin names this theme styles
    requires_plugins: list[str] = []  # plugins that MUST be active

    # Which version of the `<head>` contract this theme implements.
    #   0 — legacy: the theme emits its own <title>/canonical/OG, or calls the
    #       per-tag `{% seo_* %}` helpers. Still works; nothing is enforced.
    #   1 — the theme calls `{% storefront_head %}` exactly once inside <head>
    #       and emits NO title/canonical/robots/og:*/JSON-LD of its own.
    # Declaring 1 opts the theme into the contract test, which is the point:
    # SEO regressions in a theme are invisible until traffic disappears.
    head_contract: int = 0

    # Topic for the demo_data random product generator. Built-ins:
    # 'bookstore' | 'apparel' | 'general'. Empty falls back to 'general'.
    demo_topic: str = ''

    # ── Internal ──────────────────────────────────────────────────────────────
    _config_cache: dict | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            return
        cls._validate_metadata()

    @classmethod
    def _validate_metadata(cls) -> None:
        if not isinstance(cls.name, str) or not _NAME_RE.match(cls.name):
            raise ThemeConfigurationError(
                f'{cls.__name__}.name must be snake_case (letters, digits, underscores; '
                f'start with a letter). Got {cls.name!r}.'
            )
        if not cls.label:
            raise ThemeConfigurationError(
                f'{cls.__name__}.label is required (human-readable name).'
            )
        if not isinstance(cls.version, str) or not _VERSION_RE.match(cls.version):
            raise ThemeConfigurationError(
                f'{cls.__name__}.version must be PEP 440-style (e.g. 1.2.3). Got {cls.version!r}.'
            )
        for attr in ('supports_plugins', 'requires_plugins'):
            value = getattr(cls, attr)
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                raise ThemeConfigurationError(
                    f'{cls.__name__}.{attr} must be a list of plugin name strings.'
                )

    # ── Configuration ──────────────────────────────────────────────────────────

    def get_config_schema(self) -> dict:
        """JSON Schema for *behavioral* settings (e.g. show/hide a section)."""
        return {}

    def get_design_tokens(self) -> dict:
        """
        Design-token surface. Returned dict is a flat tree of token
        categories → key/value pairs. Used by the dashboard's theme editor
        and (future) export-as-CSS-variables tool.

        Recommended categories: `colors`, `fonts`, `radii`, `spacing`,
        `shadows`, `motion`.
        """
        return {}

    def get_config(self) -> dict:
        from django.db import DatabaseError

        if self._config_cache is None:
            try:
                from themes.models import ThemeConfig

                row = ThemeConfig.objects.get(theme_name=self.name)
                self._config_cache = row.config or {}
            except (DatabaseError, ImportError, LookupError):
                self._config_cache = {}
            except Exception:  # noqa: BLE001 — DoesNotExist on the dynamic ORM
                self._config_cache = {}
        return self._config_cache

    def get_config_value(self, key: str, default: Any = None) -> Any:
        config = self.get_config()
        if key in config:
            return config[key]
        schema = self.get_config_schema()
        return schema.get('properties', {}).get(key, {}).get('default', default)

    def invalidate_config_cache(self) -> None:
        self._config_cache = None

    # ── Paths ─────────────────────────────────────────────────────────────────

    @property
    def templates_dir(self) -> str:
        from django.conf import settings

        return str(settings.MORPHEUS_THEMES_DIR / self.name / 'templates')

    @property
    def static_dir(self) -> str:
        from django.conf import settings

        return str(settings.MORPHEUS_THEMES_DIR / self.name / 'static')

    @property
    def preview_url(self) -> str:
        """Static URL of this theme's preview image, or '' if unset."""
        if not self.preview_image:
            return ''
        from django.templatetags.static import static

        return static(f'{self.name}/{self.preview_image.lstrip("/")}')

    # ── Info ──────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f'<MorpheusTheme: {self.name} v{self.version}>'
