import logging

from django.apps import AppConfig

logger = logging.getLogger('morpheus.gdpr')


def _seed_legal_pages_on_migrate(*args, **kwargs) -> None:
    """Idempotently (re)seed the legal CMS pages after every migrate.

    The ``0002_seed_legal_pages`` data migration seeds them, but its ``seed()``
    is deliberately fail-soft — a content hiccup must never wedge the prod
    ``migrate`` — so a seed that threw once (e.g. mid store-cutover, before the
    cms schema settled) leaves 0002 marked *applied* yet zero pages created, and
    every footer legal link 404s forever. A migration never re-runs once
    applied; this runs on the next deploy's ``migrate`` and heals it.
    ``seed_legal_pages(force=False)`` skips slugs that already exist, so the
    steady-state cost is six SELECTs.
    """
    try:
        from plugins.installed.gdpr.services import seed_legal_pages

        seed_legal_pages(force=False)
    except Exception:  # noqa: BLE001 — never break migrate over a content seed
        logger.warning('gdpr: post-migrate legal-page seed skipped', exc_info=True)


class GdprConfig(AppConfig):
    name = 'plugins.installed.gdpr'
    label = 'gdpr'
    verbose_name = 'GDPR / Privacy'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:
        from django.db.models.signals import post_migrate

        from plugins.installed.gdpr.app import GdprPlugin
        from plugins.registry import app_registry

        if 'gdpr' not in app_registry._classes:
            app_registry._classes['gdpr'] = GdprPlugin

        # Self-heal a swallowed legal-page seed on the next migrate (see the
        # handler docstring). A module-level handler keeps a strong reference,
        # so the default weak signal connection can't garbage-collect it.
        post_migrate.connect(
            _seed_legal_pages_on_migrate,
            sender=self,
            dispatch_uid='gdpr.seed_legal_pages_on_migrate',
        )
