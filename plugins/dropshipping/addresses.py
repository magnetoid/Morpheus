"""A shipping address the way a supplier's order form will accept it.

Checkout stores whatever the form collected (``address_line1`` on one theme,
``line1`` on another; a two-letter country code or a typed name), and
suppliers reject the rest: DSers wants no special characters in address lines
and a phone of digits and ``+`` only; every supplier wants the full country
name. One normaliser, read by every supplier app.
"""

from __future__ import annotations

import re

from plugins.dropshipping.countries import country_name

_UNSAFE = re.compile(r'[^\w\s,./#-]', re.UNICODE)
_SPACES = re.compile(r'\s+')


def clean_text(value) -> str:
    """Letters, digits, space and ,./#- only; runs of whitespace collapsed."""
    text = _UNSAFE.sub('', str(value or ''))
    return _SPACES.sub(' ', text).strip()


def clean_phone(value) -> str:
    text = str(value or '').strip()
    digits = re.sub(r'\D', '', text)
    return ('+' if text.startswith('+') else '') + digits


def _first(addr: dict, *keys: str) -> str:
    for key in keys:
        if addr.get(key):
            return str(addr[key])
    return ''


def normalised_address(order) -> dict:
    """The order's shipping address as flat, cleaned, supplier-ready strings."""
    addr = order.shipping_address if isinstance(order.shipping_address, dict) else {}
    contact = f'{addr.get("first_name", "")} {addr.get("last_name", "")}'.strip() or _first(
        addr, 'name', 'full_name'
    )
    return {
        'contact': contact,
        'phone': clean_phone(_first(addr, 'phone', 'mobile')),
        'email': order.email or '',
        'line1': clean_text(_first(addr, 'address_line1', 'line1', 'address1', 'street')),
        'line2': clean_text(_first(addr, 'address_line2', 'line2', 'address2')),
        'province': clean_text(_first(addr, 'state', 'province', 'region')),
        'city': clean_text(_first(addr, 'city')),
        'zip': _first(addr, 'postal_code', 'zip', 'postcode').strip(),
        'country': country_name(_first(addr, 'country', 'country_code')),
    }
