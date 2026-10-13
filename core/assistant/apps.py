from django.apps import AppConfig


class AssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.assistant'
    label = 'assistant'
    verbose_name = 'Linda AI Assistant'

    def ready(self) -> None:
        # Dashboard-home activity feed: pending OpsProposals (staged-changes
        # design §3). Core-owned handler — never gated by a plugin toggle.
        from core.assistant.dashboard import on_activity_feed  # noqa: PLC0415
        from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

        hook_registry.register(MorpheusEvents.ACTIVITY_FEED, on_activity_feed, priority=40)
