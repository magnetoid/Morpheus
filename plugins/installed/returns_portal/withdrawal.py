"""The withdrawal function (EU Consumer Rights Directive, Art. 11a; v0.181.0).

A store that sells to consumers in the EU must offer a "Withdraw from contract
here" function for the whole withdrawal period. This app owns it: the two
settings, the page (views.py), the links (the order email, the account order
page, the footer), the acknowledgement email and Linda's tools. The rule and
the record are orders' (``orders/withdrawal.py``), so every door withdraws the
same way.

The function is off until the merchant switches it on. The setup checklist and
the nightly health check say so while a store in the EU or the EEA has it off.
"""

from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger('morpheus.returns_portal')

#: EU member states and the other EEA states, where the directive applies.
EEA_COUNTRIES = frozenset(
    {
        *('AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU'),
        *('IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'),
        *('IS', 'LI', 'NO'),
    }
)
LINK_LABEL = 'Withdraw from contract here'


def enabled() -> bool:
    """Whether the merchant switched the withdrawal function on."""
    from plugins.registry import app_registry  # noqa: PLC0415

    value = app_registry.config_value('returns_portal', 'withdrawal_function', False)
    if isinstance(value, str):
        return value.strip().lower() in ('true', '1', 'yes', 'on')
    return bool(value)


def days() -> int:
    """The withdrawal period in days: the merchant's, never under the law's 14."""
    from plugins.installed.orders.withdrawal import MIN_DAYS  # noqa: PLC0415
    from plugins.registry import app_registry  # noqa: PLC0415

    try:
        value = int(app_registry.config_value('returns_portal', 'withdrawal_days', MIN_DAYS))
    except (TypeError, ValueError):
        value = MIN_DAYS
    return max(MIN_DAYS, value)


def store_in_eea() -> bool:
    from plugins.installed.returns_portal.seo_graph import _store_country  # noqa: PLC0415

    return _store_country() in EEA_COUNTRIES


def order_url(order) -> str:
    """The withdrawal page for ``order``, already identified by its link token."""
    from core.utils.site import site_base_url  # noqa: PLC0415

    base = site_base_url().rstrip('/')
    return f'{base}/withdraw/?order={order.order_number}&token={order.public_token}'


def on_order_email_links(value, order=None, key='', **kwargs):
    """ORDER_EMAIL_LINKS: the order email links the withdrawal page."""
    if order is not None and enabled() and getattr(order, 'public_token', ''):
        value.append({'label': LINK_LABEL, 'url': order_url(order)})
    return value


def on_setup_steps(value, **kwargs):
    """DASHBOARD_SETUP_STEPS: a store in the EU or the EEA switches the function on."""
    if store_in_eea():
        value.append(
            {
                'key': 'withdrawal_function',
                'label': 'Switch on the withdrawal function',
                'hint': 'EU law asks for a "Withdraw from contract here" link on every order.',
                'url': '/dashboard/settings/returns_portal/',
                'done': enabled(),
            }
        )
    return value


def on_health_checks(value, **kwargs):
    """HEALTH_CHECKS: the same, every night, for a store in the EU or the EEA."""
    if store_in_eea():
        on = enabled()
        value.append(
            {
                'name': 'Customers can withdraw online',
                'ok': on,
                'detail': ''
                if on
                else 'The withdrawal function is off; EU law has asked for it since 19 June '
                '2026. Switch it on in the Returns portal settings.',
            }
        )
    return value


def on_withdrawal_requested(order=None, withdrawal=None, **kwargs):
    """ORDER_WITHDRAWAL_REQUESTED: email the acknowledgement and stamp it on the notice."""
    from core.emails.handlers import send_templated_email  # noqa: PLC0415

    if order is None or withdrawal is None:
        return
    try:
        send_templated_email(
            'withdrawal_received',
            to=withdrawal.email,
            subject=f'We received your withdrawal from order #{order.order_number}',
            ctx={'order': order, 'withdrawal': withdrawal},
        )
    except Exception as e:  # noqa: BLE001 — logged; the notice stays without a stamp
        logger.error('returns_portal: acknowledgement for %s failed: %s', order.order_number, e)
        return
    withdrawal.acknowledged_at = timezone.now()
    withdrawal.save(update_fields=['acknowledged_at'])
