from django.apps import AppConfig


class AgentCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.agent_core'
    label = 'agent_core'
    verbose_name = 'Agent Core'

    def ready(self) -> None:
        # Register the fail-closed approval resolver + pending-request recorder
        # into the Django-free kernel seam (core audit S1). Without this, the
        # kernel denies every approval-required tool; with it, denials become a
        # paused run + a human-approvable request. Wrapped so an import hiccup
        # never blocks app startup.
        try:
            from plugins.installed.agent_core.approvals import register

            register()
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.agent_core').warning(
                'agent_core: approval resolver wiring failed', exc_info=True
            )
