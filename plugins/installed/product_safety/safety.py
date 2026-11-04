"""A product's safety details (EU General Product Safety Regulation, GPSR).

A listing of a consumer product names its manufacturer (name, postal address, email
or website), the person responsible for it in the EU when the manufacturer is outside
the EU, and its warnings and safety information. Each value is a metafield in the
``gpsr`` namespace on the product; this app has no table of its own.

A store that makes, imports or answers for its goods sets its own details once (this
app's settings). A product that sells goods and names no manufacturer, or no
responsible person, of its own shows the store's. A party comes whole from one
source: a product's own manufacturer name never sits beside the store's address.

The product's codes (GTIN, MPN, ISBN) are the metafields app's identifiers, which the
page and its structured data already show.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import transaction

NAMESPACE = 'gpsr'

# (key, label, longest value kept). The two parties are also the store's settings.
MANUFACTURER = (
    ('manufacturer_name', 'Manufacturer', 200),
    ('manufacturer_address', "Manufacturer's postal address", 500),
    ('manufacturer_contact', "Manufacturer's email or website", 254),
)
RESPONSIBLE = (
    ('responsible_name', 'Responsible person in the EU', 200),
    ('responsible_address', "Responsible person's postal address", 500),
    ('responsible_contact', "Responsible person's email or website", 254),
)
PRODUCT_ONLY = (
    ('warnings', 'Warnings and safety information', 5000),
    ('safety_url', 'Link to instructions or a safety sheet', 500),
)
FIELDS = MANUFACTURER + RESPONSIBLE + PRODUCT_ONLY
KEYS = tuple(key for key, _label, _limit in FIELDS)
CONTACT_KEYS = ('manufacturer_contact', 'responsible_contact')

# A service (booked) or a digital download is not a product the regulation covers,
# so the store's details are never claimed for one.
_NOT_GOODS = ('service', 'digital')


def clean(value, limit: int) -> str:
    """A stored value: line endings as a browser or a model sends them, trimmed, capped."""
    return str(value or '').replace('\r\n', '\n').replace('\r', '\n').strip()[:limit]


def is_web_url(value: str) -> bool:
    try:
        URLValidator(schemes=['http', 'https'])(value)
    except ValidationError:
        return False
    return True


def contact_href(value: str) -> str:
    """A link for an email address or a web address; '' for anything else."""
    value = (value or '').strip()
    if not value:
        return ''
    try:
        validate_email(value)
    except ValidationError:
        return value if is_web_url(value) else ''
    return f'mailto:{value}'


def stored(product) -> dict[str, str]:
    """The product's own safety details, ``{key: value}`` for each key it has."""
    if product is None or getattr(product, 'pk', None) is None:
        return {}
    from django.contrib.contenttypes.models import ContentType

    from plugins.installed.catalog.models import Product
    from plugins.installed.metafields.models import Metafield

    rows = Metafield.objects.filter(
        content_type=ContentType.objects.get_for_model(Product),
        object_id=str(product.pk),
        namespace=NAMESPACE,
        key__in=KEYS,
    ).values_list('key', 'value')
    return {key: value for key, value in rows if value}


def store_defaults() -> dict[str, str]:
    """The store's own details as manufacturer and responsible person (settings)."""
    from plugins.registry import app_registry

    plugin = app_registry.get('product_safety')
    if plugin is None:
        return {}
    config = plugin.get_config() or {}
    out = {}
    for key, _label, limit in MANUFACTURER + RESPONSIBLE:
        value = clean(config.get(key, ''), limit)
        if value:
            out[key] = value
    return out


def sells_goods(product) -> bool:
    """A product shipped to a shopper, the kind the store's details are claimed for."""
    return bool(product.requires_shipping) and product.product_type not in _NOT_GOODS


def _party(details: dict, fields) -> dict | None:
    name, address, contact = (details.get(key, '') for key, _label, _limit in fields)
    if not (name or address or contact):
        return None
    return {'name': name, 'address': address, 'contact': contact, 'href': contact_href(contact)}


def effective(product, own: dict | None = None) -> dict:
    """What the product's page shows: ``manufacturer``, ``responsible``, ``warnings``, ``safety_url``.

    A party is the product's own when it fills any of that party's fields, else the
    store's (for goods only), else None.
    """
    own = stored(product) if own is None else own
    defaults = store_defaults() if sells_goods(product) else {}
    out: dict = {}
    for party, fields in (('manufacturer', MANUFACTURER), ('responsible', RESPONSIBLE)):
        named = any(own.get(key) for key, _label, _limit in fields)
        out[party] = _party(own if named else defaults, fields)
    out['warnings'] = own.get('warnings', '')
    url = own.get('safety_url', '')
    out['safety_url'] = url if is_web_url(url) else ''
    return out


def shows_anything(info: dict) -> bool:
    return any(info.get(key) for key in ('manufacturer', 'responsible', 'warnings', 'safety_url'))


def set_details(product, values: dict) -> dict[str, str]:
    """Write the keys given ('' clears one); keys not given stay. Returns what is stored."""
    from plugins.installed.metafields.models import Metafield

    current = stored(product)
    limits = {key: limit for key, _label, limit in FIELDS}
    with transaction.atomic():
        for key in KEYS:
            if key not in values:
                continue
            value = clean(values[key], limits[key])
            if value == current.get(key, ''):
                continue
            if value:
                Metafield.objects.set(
                    product, namespace=NAMESPACE, key=key, value=value, value_type='string'
                )
            else:
                Metafield.objects.delete_for(product, namespace=NAMESPACE, key=key)
    return stored(product)


def save_from_form(product, post) -> None:
    """Save the product editor's "Product safety" card.

    Acts only when the card was on the page (``gpsr_submitted``), so a save from
    anywhere else never reads as "every field emptied".
    """
    if product is None or post is None or not post.get('gpsr_submitted'):
        return
    set_details(product, {key: post.get(f'gpsr_{key}', '') for key in KEYS})


def form_fields(product) -> list[dict]:
    """The editor card's inputs, with the store's details as each party's placeholder."""
    own = stored(product)
    defaults = store_defaults()
    return [
        {
            'name': key,
            'label': label,
            'value': own.get(key, ''),
            'placeholder': defaults.get(key, ''),
            'multiline': key == 'warnings',
            'maxlength': limit,
        }
        for key, label, limit in FIELDS
    ]
