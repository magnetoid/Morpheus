"""{% variant %} templatetag — wraps services.variant_for.

Usage in any template:
    {% load experiments %}
    {% variant 'pdp_hero_v2' as v %}
    {% if v == 'treatment' %}
        ... new design ...
    {% else %}
        ... control ...
    {% endif %}
"""

from __future__ import annotations

from django import template

from plugins.installed.experiments.services import variant_for

register = template.Library()


@register.simple_tag(takes_context=True)
def variant(context, experiment_key: str) -> str:
    request = context.get('request')
    if request is None:
        return 'control'
    return variant_for(request, experiment_key)
