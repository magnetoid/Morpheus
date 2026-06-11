from django.apps import AppConfig


class I18nConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.i18n'
    label = 'morph_i18n'
    verbose_name = 'Morpheus i18n'

    def ready(self):
        # Auto-register the i18n agent tools on the agent kernel so any
        # plugin-contributed agent with the right scope can call them.
        try:
            from core.agents import agent_registry
            from core.i18n.agent_tools import (
                list_translations_tool,
                translate_product_tool,
            )

            agent_registry.register_tool(translate_product_tool, plugin='core.i18n')
            agent_registry.register_tool(list_translations_tool, plugin='core.i18n')
        except Exception:  # noqa: BLE001, S110
            pass
