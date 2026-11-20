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
#: The acknowledgement email's tag (core.emails), followed by the notice's id.
_TAG = 'withdrawal:'


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
    """HEALTH_CHECKS: the same, every night, for a store in the EU or the EEA, and
    whether the acknowledgement the law asks for can reach the customer."""
    from core.email import real_transport  # noqa: PLC0415

    if store_in_eea():
        on = enabled()
        mails = real_transport()
        detail = ''
        if not on:
            detail = (
                'The withdrawal function is off; EU law has asked for it since 19 June '
                '2026. Switch it on in the Returns portal settings.'
            )
        elif not mails:
            detail = (
                'The store has no sending email, so withdrawal acknowledgements go to the '
                'log instead of the customer. Set one in Settings, Email.'
            )
        value.append(
            {'name': 'Customers can withdraw online', 'ok': on and mails, 'detail': detail}
        )
    return value


def on_withdrawal_requested(order=None, withdrawal=None, **kwargs):
    """ORDER_WITHDRAWAL_REQUESTED: email the acknowledgement. The notice is stamped
    only once the email is sent (``on_email_delivered``): sending is fail-soft and
    queued, so returning from it proves nothing."""
    from core.emails.handlers import send_templated_email  # noqa: PLC0415

    if order is None or withdrawal is None:
        return
    try:
        send_templated_email(
            'withdrawal_received',
            to=withdrawal.email,
            subject=f'We received your withdrawal from order #{order.order_number}',
            ctx={'order': order, 'withdrawal': withdrawal},
            tag=f'{_TAG}{withdrawal.pk}',
        )
    except Exception as e:  # noqa: BLE001 — logged; the notice stays without a stamp
        logger.error('returns_portal: acknowledgement for %s failed: %s', order.order_number, e)


def on_email_delivered(tag='', reached_inbox=False, **kwargs):
    """EMAIL_DELIVERED: stamp a withdrawal's acknowledgement once it reached an inbox.
    A store with no sending email leaves it unstamped, since nobody received it."""
    from plugins.installed.orders.models import WithdrawalNotice  # noqa: PLC0415

    if not str(tag).startswith(_TAG):
        return
    pk = str(tag)[len(_TAG) :]
    if not reached_inbox:
        logger.warning('returns_portal: acknowledgement %s went to the log: no sending email', pk)
        return
    WithdrawalNotice.objects.filter(pk=pk, acknowledged_at__isnull=True).update(
        acknowledged_at=timezone.now()
    )
