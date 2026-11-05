"""`{% load payments_express %}`: the cart page's wallet buttons."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def express_checkout(context) -> dict:
    """``express.cart_offer`` for the request being rendered, {} when there is none."""
    from plugins.installed.payments.express import cart_offer

    return cart_offer(context.get('request'))
