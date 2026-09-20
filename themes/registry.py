"""
Morpheus — Theme Registry.

Discovers themes from `themes/library/<name>/theme.py`, validates them, and
chooses one as active (driven by `settings.MORPHEUS_ACTIVE_THEME`, with a
DB-backed override via `themes.models.ThemeConfig`).
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from themes.base import MorpheusTheme

logger = logging.getLogger('morpheus.themes')


class ThemeRegistry:
    def __init__(self) -> None:
        self._themes: dict[str, MorpheusTheme] = {}
        self._active_name: str | None = None

    # ── Discovery ──────────────────────────────────────────────────────────────

    def discover(self, themes_dir: Path) -> None:
        from themes.base import MorpheusTheme

        if not themes_dir.exists():
            logger.warning('themes: themes_dir does not exist: %s', themes_dir)
            return
        for theme_dir in themes_dir.iterdir():
            if not theme_dir.is_dir() or not (theme_dir / 'theme.py').exists():
                continue
            if theme_dir.name.startswith('.'):
                # Never a theme: the per-theme updater stages the new tree and
                # parks the previous one in dot-prefixed siblings during a swap
                # (core/component_updates.py). Discovering one of those would
                # register a duplicate name and shadow the real theme.
                continue
            module_path = f'themes.library.{theme_dir.name}.theme'
            try:
                mod = importlib.import_module(module_path)
            except ImportError as e:
                logger.error('themes: import error %s: %s', module_path, e, exc_info=True)
                continue
            theme_cls = self._find_theme_class(mod, MorpheusTheme)
            if theme_cls is None:
                logger.warning('themes: no MorpheusTheme subclass in %s', module_path)
                continue
            try:
                instance = theme_cls()
            except Exception as e:  # noqa: BLE001 — bad theme should not break boot
                logger.error(
                    'themes: instantiation failed for %s: %s', theme_cls.__name__, e, exc_info=True
                )
                continue
            self._themes[instance.name] = instance
            logger.debug('themes: discovered %s', instance.name)

    @staticmethod
    def _find_theme_class(module, base) -> type | None:
        for attr in dir(module):
            obj = getattr(module, attr)
            if (
                isinstance(obj, type)
                and issubclass(obj, base)
                and obj is not base
                and getattr(obj, 'name', '')
            ):
                return obj
        return None

    # ── Activation ─────────────────────────────────────────────────────────────

    def set_active(self, name: str) -> None:
        """Activate a theme by name. Logs a warning if not discovered."""
        if name in self._themes:
            self._active_name = name
            logger.info('Active theme: %s', name)
            return
        logger.warning(
            'themes: theme %r not found among %s. Keeping current: %s',
            name,
            sorted(self._themes),
            self._active_name,
        )

    def set_active_from_db(self) -> None:
        """Read active theme from DB (ThemeConfig) or fall back to settings."""
        from django.conf import settings
        from django.db import DatabaseError

        row = None
        try:
            from themes.models import ThemeConfig

            row = ThemeConfig.objects.filter(is_active=True).first()
        except (DatabaseError, ImportError, LookupError):
            row = None
        if row and row.theme_name in self._themes:
            self._active_name = row.theme_name
            return
        self._active_name = getattr(settings, 'MORPHEUS_ACTIVE_THEME', '')

    # ── Validation ─────────────────────────────────────────────────────────────

    def validate_active_theme(self) -> list[str]:
        """Return a list of error strings if the active theme is misconfigured."""
        theme = self.active
        if theme is None:
            return ['No active theme.']
        return self.validate_active_theme_for(theme.name)

    def validate_active_theme_for(self, name: str) -> list[str]:
        """Validate a theme by name — whether it may be activated on this store.

        A theme declares `requires_plugins`; activating it without those apps
        installed would render a broken surface (e.g. the montenegro theme's
        homepage loads `{% load booking_tags %}` which only exists in
        `booking_marketplace`). Used by the theme-activation tool so the picker
        is not a trap.
        """
        errors: list[str] = []
        theme = self.get(name)
        if theme is None:
            return [f'Unknown theme: {name!r}.']
        if theme.requires_plugins:
            try:
                from plugins.registry import app_registry

                missing = [p for p in theme.requires_plugins if not app_registry.is_active(p)]
                if missing:
                    errors.append(
                        f'Theme "{theme.name}" requires plugins {missing} which are not active.'
                    )
            except ImportError:
                pass
        return errors

    # ── Accessors ──────────────────────────────────────────────────────────────

    @property
    def active(self) -> MorpheusTheme | None:
        return self._themes.get(self._active_name) if self._active_name else None

    @property
    def active_templates_dir(self) -> str | None:
        theme = self.active
        return theme.templates_dir if theme else None

    def all_themes(self) -> list[MorpheusTheme]:
        return list(self._themes.values())

    def get(self, name: str) -> MorpheusTheme | None:
        return self._themes.get(name)

    def __repr__(self) -> str:
        return f'<ThemeRegistry: {len(self._themes)} themes, active={self._active_name!r}>'


theme_registry = ThemeRegistry()
