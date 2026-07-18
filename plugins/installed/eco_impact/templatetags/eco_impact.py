"""Template tags for the eco_impact storefront blocks. Keep the block templates
logic-free and self-hiding: each tag returns None/empty when there's nothing to
show, so the surrounding ``{% if %}`` drops the block."""

from __future__ import annotations

from django import template

from plugins.installed.eco_impact import services

register = template.Library()


@register.simple_tag
def eco_impact_for(product):
    """Production-footprint dict for a PDP product, or None when the badge is
    turned off / the product isn't a book / it has no physical data."""
    if not services.show_on_pdp():
        return None
    return services.impact_for_product(product)


@register.simple_tag(takes_context=True)
def eco_optin_state(context):
    """State for the cart opt-in widget: whether the flat offset is applied and
    what it costs. Always renderable (the offer stands for any cart)."""
    request = context.get('request')
    if request is None:
        return None
    try:
        return {
            'applied': services.optin_active(request),
            'amount': services.surcharge_amount(),
        }
    except Exception:  # noqa: BLE001
        return None
