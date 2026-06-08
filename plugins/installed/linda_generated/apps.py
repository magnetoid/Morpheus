# ready() uses lazy imports to avoid an app-loading import cycle (the established
# plugin pattern, cf. inventory/apps.py).
# ruff: noqa: PLC0415, I001
from django.apps import AppConfig


class LindaGeneratedConfig(AppConfig):
    name = 'plugins.installed.linda_generated'
    label = 'linda_generated'
    verbose_name = 'Linda Generated'

    def ready(self):
        from plugins.registry import plugin_registry
        from plugins.installed.linda_generated.plugin import LindaGeneratedPlugin

        if 'linda_generated' not in plugin_registry._classes:
            plugin_registry._classes['linda_generated'] = LindaGeneratedPlugin
        # Import any applied tool modules so their @tool decorators run. Empty
        # until Linda's GATED apply (ADR 0014 / Phase 4) lands a file here.
        from plugins.installed.linda_generated.tools import load_generated_tools

        load_generated_tools()


default_app_config = 'plugins.installed.linda_generated.apps.LindaGeneratedConfig'
