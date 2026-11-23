"""The "Email customer" action's helpers: who receives it and what it says.

A merchant writes the subject and body in the workflow, so they are never a
template: only the five placeholders below are replaced, from a fixed map, and
nothing reads an attribute the merchant names.
"""

from __future__ import annotations

PLACEHOLDERS = (
    'customer_first_name',
    'customer_name',
    'order_number',
    'order_total',
    'store_name',
)


def _email(obj) -> str:
    return (getattr(obj, 'email', '') or '').strip()


def recipient(payload: dict) -> tuple[str, object | None]:
    """``(email, order)``: the event's customer, then the order's customer, then the
    order's own address (a guest), then a bare ``email`` in the event."""
    order = payload.get('order')
    customer = payload.get('customer')
    for candidate in (
        _email(customer),
        _email(getattr(order, 'customer', None)),
        _email(order),
        (payload.get('email') or '').strip() if isinstance(payload.get('email'), str) else '',
    ):
        if candidate:
            return candidate, order
    return '', order


def _values(payload: dict) -> dict[str, str]:
    from core.utils.site import store_name

    order = payload.get('order')
    customer = payload.get('customer') or getattr(order, 'customer', None)
    email, _ = recipient(payload)
    first = (getattr(customer, 'first_name', '') or '').strip()
    full = ' '.join(p for p in (first, (getattr(customer, 'last_name', '') or '').strip()) if p)
    return {
        'customer_first_name': first,
        'customer_name': full or email.split('@')[0],
        'order_number': str(getattr(order, 'order_number', '') or ''),
        'order_total': str(getattr(order, 'total', '') or ''),
        'store_name': store_name(),
    }


def fill(text: str, payload: dict) -> str:
    """Replace the known placeholders; anything else stays as typed."""
    for name, value in _values(payload).items():
        text = text.replace('{' + name + '}', value)
    return text


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.replace('\r\n', '\n').split('\n\n') if p.strip()]
