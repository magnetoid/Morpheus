"""Project the advanced_payments settings panel onto ``PaymentGatewayConfig``.

The platform decides a gateway is live via ``payments.models.is_enabled()``,
which reads ``PaymentGatewayConfig`` — NOT this plugin's ``PluginConfig``.
The settings panel, however, saves to ``PluginConfig`` (the generic
schema-panel save path). Without a bridge the panel toggles do nothing —
the documented "flip it in Settings → Payments" never reaches checkout.

This module is that bridge. Whenever the panel is saved (``post_save`` on
``PluginConfig``) or migrations run (``post_migrate``), the ``cod``/``test``
rows in ``PaymentGatewayConfig`` are rewritten to match the panel toggles,
and the COD instructions are mirrored into the ``cod`` row's
``config['instructions']`` — which the checkout picker already renders.

``PaymentGatewayConfig`` stays the single runtime source of truth; this
keeps the ``cod``/``test`` rows a faithful projection of the panel.
``stripe``/``manual`` rows are never touched. Fail-soft: a projection error
is logged, never crashes a save or boot.
"""

# ruff: noqa: PLC0415
# Inline imports keep this module importable before the app registry +
# sibling payments plugin are ready (signals connect at app-ready time).

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.advanced_payments')

PLUGIN_NAME = 'advanced_payments'


def sync_gateway_config(*args, **kwargs) -> None:
    """Upsert the ``cod``/``test`` PaymentGatewayConfig rows from the panel."""
    try:
        from plugins.installed.payments.models import PaymentGatewayConfig
        from plugins.registry import app_registry

        plugin = app_registry.get(PLUGIN_NAME)
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
        logger.warning('advanced_payments: gateway config sync failed', exc_info=True)


def _on_plugin_config_saved(sender, instance, **kwargs) -> None:
    """post_save(PluginConfig) receiver — resync only on our own row."""
    if getattr(instance, 'plugin_name', None) == PLUGIN_NAME:
        sync_gateway_config()
