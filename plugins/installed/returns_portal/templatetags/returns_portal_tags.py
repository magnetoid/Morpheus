"""Template tags of the returns portal (C4, v0.188.0)."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def order_can_return(order) -> bool:
    """Whether some line of ``order`` can still come back."""
    from plugins.installed.returns_portal.views_returns import order_return_action  # noqa: PLC0415

    return bool(order is not None and order_return_action(order))
