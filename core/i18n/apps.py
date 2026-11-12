from django.apps import AppConfig


class I18nConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.i18n'
    label = 'morph_i18n'
    verbose_name = 'Morpheus i18n'

    def ready(self):
        # A view shows a translation on the instance it renders; before any save
        # the default-language text goes back (services.restore_untranslated).
        from django.db.models.signals import pre_save

        from core.i18n.services import restore_untranslated

        pre_save.connect(restore_untranslated, dispatch_uid='core.i18n.restore_untranslated')

        # Auto-register the i18n agent tools on the agent kernel so any
        # plugin-contributed agent with the right scope can call them.
        try:
            from core.agents import agent_registry
            from core.i18n.agent_tools import (
                approve_translation_tool,
                get_translations_tool,
                list_languages_tool,
                set_translation_tool,
                translation_status_tool,
            )

            # Generic, any-object translation tools (external translators / tools).
            # i18n.translate_product / i18n.list_translations moved to the catalog
            # plugin (they query catalog.Product) and are contributed there;
            # i18n.draft_translations is the localization app's (it queues its task).
            for tool in (
                list_languages_tool,
                get_translations_tool,
                set_translation_tool,
                translation_status_tool,
                approve_translation_tool,
            ):
                agent_registry.register_tool(tool, plugin='core.i18n')
        except Exception:  # noqa: BLE001, S110
            pass
