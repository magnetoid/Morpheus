"""Theme-aware Django template loader."""

import os

from django.template.loaders.filesystem import Loader as FilesystemLoader


class ThemeLoader(FilesystemLoader):
    """Resolves templates from the active theme directory first."""

    def get_dirs(self):
        from themes.registry import theme_registry

        dirs = []
        theme = theme_registry.active
        if theme:
            theme_templates = theme.templates_dir
            if os.path.isdir(theme_templates):
                dirs.append(theme_templates)
        return dirs
