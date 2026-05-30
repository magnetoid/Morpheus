"""Template tags for the consent banner.

Two helpers:

  * ``{% consent_show as flag %}`` — True when the banner should render
    (visitor hasn't decided yet).
  * ``{% consent_current as decision %}`` — current dict from the cookie
    (defaults to necessary-only); used to pre-check the per-category
    boxes on the preferences page.
"""

from __future__ import annotations

from django import template

from plugins.installed.consent.services import (
    has_decided,
    read_consent_from_cookie,
)

register = template.Library()


@register.simple_tag(takes_context=True)
def consent_show(context) -> bool:
    request = context.get('request')
    if request is None:
        return False
    return not has_decided(request)


@register.simple_tag(takes_context=True)
def consent_current(context) -> dict:
    request = context.get('request')
    if request is None:
        return {'necessary': True, 'analytics': False, 'marketing': False, 'functional': False}
    return read_consent_from_cookie(request)
