"""Project the cash-on-delivery and test-payment settings onto ``PaymentGatewayConfig``.

The platform decides a gateway is live via ``payments.models.is_enabled()``,
which reads ``PaymentGatewayConfig``, while the settings panel saves to the
payments ``PluginConfig``. Whenever the panel is saved or migrations run, the
``cod``/``test`` rows are rewritten to match the panel toggles, and the COD
instructions are mirrored into the ``cod`` row's ``config['instructions']``,
which the checkout picker renders (the same bridge ``paypal.sync_gateway_row``
is for PayPal).

``stripe``/``manual`` rows are never touched. Fail-soft: a projection error is
logged, never crashes a save or boot.
"""

# ruff: noqa: PLC0415
# Inline imports keep this module importable before the app registry is ready.

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.payments.offline')


def sync_offline_gateways(*args, **kwargs) -> None:
    """Upsert the ``cod``/``test`` PaymentGatewayConfig rows from the panel."""
    try:
        from plugins.installed.payments.models import PaymentGatewayConfig
        from plugins.registry import app_registry

        plugin = app_registry.get('payments')
        if plugin is None:
            return
        plugin.invalidate_config_cache()
        test_enabled = bool(plugin.get_config_value('test_enabled', False))
        cod_enabled = bool(plugin.get_config_value('cod_enabled', True))
        cod_instructions = str(plugin.get_config_value('cod_instructions', '') or '')

        PaymentGatewayConfig.objects.update_or_create(
            slug='test', defaults={'enabled': test_enabled}
        )
        row, _ = PaymentGatewayConfig.objects.get_or_create(slug='cod')
        cfg = row.config if isinstance(row.config, dict) else {}
        cfg['instructions'] = cod_instructions
        row.enabled = cod_enabled
        row.config = cfg
        row.save(update_fields=['enabled', 'config', 'updated_at'])
    except Exception:  # noqa: BLE001 — never break a save/boot over the projection
        logger.warning('payments: cod/test gateway config sync failed', exc_info=True)
