"""Linda reads and writes a product's safety details (EU GPSR).

The write is an everyday catalog change on ``catalog.write``, like
``catalog.update_product``: Linda's own turn still waits for the merchant's yes
before any write, and leaving ``requires_approval`` off keeps a Worker able to fill a
catalogue (a Worker cannot resume an approved call). The store's own details are
app settings, which ``settings.set`` writes.
"""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool

_FIND = {
    'id': {'type': 'string'},
    'sku': {'type': 'string'},
    'slug': {'type': 'string'},
}


def _find(id: str, sku: str, slug: str):
    from django.core.exceptions import ValidationError

    from plugins.installed.catalog.models import Product

    try:
        product = (
            (id and Product.objects.filter(pk=id).first())
            or (sku and Product.objects.filter(sku=sku).first())
            or (slug and Product.objects.filter(slug=slug).first())
            or None
        )
    except (ValidationError, ValueError):
        product = None
    if product is None:
        raise ToolError('not found — pass id, sku or slug')
    return product


def _summary(product) -> tuple[dict, str]:
    from plugins.installed.product_safety.safety import (
        MANUFACTURER,
        RESPONSIBLE,
        effective,
        stored,
    )

    own = stored(product)
    shown = effective(product, own)
    parts = []
    for party, label, fields in (
        ('manufacturer', 'manufacturer', MANUFACTURER),
        ('responsible', 'EU responsible person', RESPONSIBLE),
    ):
        details = shown[party]
        if details:
            source = 'its own' if any(own.get(key) for key, _l, _m in fields) else "the store's"
            parts.append(f'{label} {details["name"] or details["contact"]} ({source})')
    if shown['warnings']:
        parts.append('warnings')
    if shown['safety_url']:
        parts.append('a safety sheet link')
    output = {'product': product.slug, 'own': own, 'shown': shown}
    display = f'{product.name}: ' + (
        ', '.join(parts) if parts else 'no product safety information on its page'
    )
    return output, display


@tool(
    name='products.safety_info',
    description=(
        "A product's safety information (EU GPSR): the manufacturer, the person "
        'responsible for it in the EU, warnings and a link to instructions or a '
        'safety sheet. `own` is what the product stores; `shown` is what its page '
        'shows, where a product that sells goods and names no manufacturer or '
        "responsible person shows the store's own details from the Product safety "
        'settings. Pass `id`, `sku` or `slug`.'
    ),
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': dict(_FIND)},
)
def products_safety_info_tool(*, id: str = '', sku: str = '', slug: str = '') -> ToolResult:
    output, display = _summary(_find(id, sku, slug))
    return ToolResult(output=output, display=display)


_TEXT = {'type': 'string'}


@tool(
    name='products.set_safety_info',
    description=(
        "Set a product's safety information (EU GPSR), shown on its page under the "
        'description. Pass `id`, `sku` or `slug` and any of: manufacturer_name, '
        'manufacturer_address (one line: street, postcode, city, country), '
        'manufacturer_contact (an email or https:// address), responsible_name, '
        'responsible_address, responsible_contact (the person responsible in the EU, '
        'needed when the manufacturer is outside it), warnings, safety_url (an https:// '
        'link to instructions or a safety sheet). "" clears a field; a field left out '
        "is kept. Leave a party empty to show the store's own details instead."
    ),
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            **_FIND,
            'manufacturer_name': _TEXT,
            'manufacturer_address': _TEXT,
            'manufacturer_contact': _TEXT,
            'responsible_name': _TEXT,
            'responsible_address': _TEXT,
            'responsible_contact': _TEXT,
            'warnings': _TEXT,
            'safety_url': _TEXT,
        },
    },
)
def products_set_safety_info_tool(
    *,
    id: str = '',
    sku: str = '',
    slug: str = '',
    manufacturer_name: str | None = None,
    manufacturer_address: str | None = None,
    manufacturer_contact: str | None = None,
    responsible_name: str | None = None,
    responsible_address: str | None = None,
    responsible_contact: str | None = None,
    warnings: str | None = None,
    safety_url: str | None = None,
) -> ToolResult:
    from plugins.installed.product_safety.safety import (
        CONTACT_KEYS,
        contact_href,
        is_web_url,
        set_details,
    )

    given = {
        'manufacturer_name': manufacturer_name,
        'manufacturer_address': manufacturer_address,
        'manufacturer_contact': manufacturer_contact,
        'responsible_name': responsible_name,
        'responsible_address': responsible_address,
        'responsible_contact': responsible_contact,
        'warnings': warnings,
        'safety_url': safety_url,
    }
    values = {key: str(value).strip() for key, value in given.items() if value is not None}
    if not values:
        raise ToolError('nothing to set — pass at least one field ("" clears one)')
    for key in CONTACT_KEYS:
        if values.get(key) and not contact_href(values[key]):
            raise ToolError(f'{key} must be an email address or an https:// address')
    if values.get('safety_url') and not is_web_url(values['safety_url']):
        raise ToolError('safety_url must be an http(s) address')
    product = _find(id, sku, slug)
    set_details(product, values)
    output, display = _summary(product)
    return ToolResult(output=output, display=display)
