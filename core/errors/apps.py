from django.apps import AppConfig


class ErrorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.errors'
    label = 'morph_errors'
    verbose_name = 'Morpheus error log'

    def ready(self):
        # The error report as agent tools (errors.recent / errors.get), so Janus
        # and external agents read what "Copy for Claude Code" hands over.
        try:
            from core.agents import agent_registry
            from core.errors.agent_tools import errors_get_tool, errors_recent_tool

            agent_registry.register_tool(errors_recent_tool, plugin='core.errors')
            agent_registry.register_tool(errors_get_tool, plugin='core.errors')
        except Exception:  # noqa: BLE001, S110 — the error log works without them
            pass
