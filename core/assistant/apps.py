import contextlib

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

        # Register Linda's self-authored (learned) skills into the skill_registry
        # so they survive restarts. Fail-soft: a fresh DB / early boot / tests
        # where the table isn't migrated yet simply loads nothing.
        from django.db.models.signals import post_migrate  # noqa: PLC0415

        def _load(**_kwargs):
            from core.assistant.tools.skills import load_learned_skills  # noqa: PLC0415

            load_learned_skills()

        # post_migrate fires after the app registry + DB are ready, avoiding the
        # "DB access during app init" warning; also load opportunistically now.
        post_migrate.connect(_load, sender=self, dispatch_uid='assistant.load_learned_skills')
        with contextlib.suppress(Exception):  # DB may not be ready at import time
            _load()
