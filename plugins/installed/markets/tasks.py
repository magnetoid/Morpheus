"""Celery tasks of the markets app (autodiscovery imports only ``<app>.tasks``)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.markets')


def rate_source() -> str:
    """The merchant's choice, read fresh (a plugin config cache is per-process)."""
    try:
        from plugins.registry import app_registry

        return str(app_registry.get('markets').get_config_value('rate_source', 'ecb'))
    except Exception:  # noqa: BLE001 — a config problem must not stop the fetch
        return 'ecb'


@shared_task(name='markets.fetch_exchange_rates')
def fetch_exchange_rates() -> dict | None:
    """Refresh rates from the ECB, unless rates are typed by hand or no active
    market needs one."""
    from plugins.installed.markets import rates

    if rate_source() == 'manual' or not rates.foreign_currencies():
        return None
    try:
        return rates.fetch_ecb()
    except Exception:  # noqa: BLE001 — the health check names a rate that stays old
        logger.warning('exchange rate fetch failed', exc_info=True)
        return None
