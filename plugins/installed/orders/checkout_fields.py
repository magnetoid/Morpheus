"""What orders asks for at checkout, and who may check out.

Each field answers CHECKOUT_FIELDS (core/checkout_fields.py) only while its setting is
on (Settings → Checkout, cart & invoices): an order note (``order_notes``, stored as
``Order.customer_notes``), a gift message (``gift_message``, on the packing slip) and the
terms tick (``terms_accepted``, required while ``checkout_terms_url`` is set; the order
keeps the link and the time it was accepted). ``guest_checkout_allowed`` is the one
reader of ``allow_guest_checkout``, for the checkout views, ``completeOrder`` and the
cart's wallet buttons.
"""

from __future__ import annotations

from django.utils import timezone
from django.utils.translation import gettext as _

from plugins.registry import app_registry


def _setting(key: str, default):
    return app_registry.config_value('orders', key, default)


def guest_checkout_allowed() -> bool:
    """Whether a shopper who is not signed in may place an order (default yes)."""
    return _setting('allow_guest_checkout', True) is not False


def terms_url() -> str:
    """The terms a shopper must accept, or '' when the store asks for none."""
    return str(_setting('checkout_terms_url', '') or '').strip()


def on_checkout_fields(value, user=None, **kwargs):
    """CHECKOUT_FIELDS: the note, the gift message and the terms tick, when on."""
    value = list(value or [])
    if _setting('checkout_order_notes', False):
        value.append(
            {
                'key': 'order_notes',
                'label': _('Notes for your order'),
                'kind': 'textarea',
                'help': _('Delivery instructions, or anything else we should know.'),
                'max_length': 1000,
                'order': 10,
            }
        )
    if _setting('checkout_gift_message', False):
        value.append(
            {
                'key': 'gift_message',
                'label': _('Gift message'),
                'kind': 'textarea',
                'help': _('We print it on the packing slip, which shows no prices.'),
                'max_length': 300,
                'order': 20,
            }
        )
    url = terms_url()
    if url:
        value.append(
            {
                'key': 'terms_accepted',
                'label': _('I have read and accept the terms and conditions.'),
                'kind': 'checkbox',
                'required': True,
                'link_url': url,
                'link_text': _('Read the terms'),
                'error': _('Please accept the terms and conditions to place your order.'),
                'order': 90,
            }
        )
    return value


def order_fields(answers: dict | None) -> tuple[str, dict]:
    """The note for ``Order.customer_notes`` and the metadata to store, from the
    answers ``completeOrder`` kept."""
    answers = dict(answers or {})
    if not answers:
        return '', {}
    extra: dict = {'checkout_fields': answers}
    if answers.get('terms_accepted'):
        extra['terms_accepted'] = {'url': terms_url(), 'at': timezone.now().isoformat()}
    return str(answers.get('order_notes') or ''), extra
